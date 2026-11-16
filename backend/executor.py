"""Local code runner with a live, line-oriented input/output console.

This executes trusted code with the server user's permissions; it is not a sandbox.
"""
from __future__ import annotations

import atexit
import codecs
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import weakref

LANGUAGE_CONFIG = {
    "Python": {"extension": ".py", "command": "python"},
    "C": {"extension": ".c", "compiler": "gcc"},
    "C++": {"extension": ".cpp", "compiler": "g++"},
    "Java": {"extension": ".java", "compiler": "javac"},
    "JavaScript": {"extension": ".js", "command": "node"},
}
_JOBS = weakref.WeakSet()
_JOBS_LOCK = threading.Lock()


def _find_command(name):
    return sys.executable if name == "python" else shutil.which(name)


def _terminate_tree(process):
    if process is None:
        return
    try:
        if os.name == "nt":
            # Only target this job's PID/tree, never all python.exe processes.
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def prepare_commands(language, code, directory):
    """Return compile/run commands without renaming Java classes/constructors."""
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"{language} is not supported.")
    if not code.strip():
        raise ValueError("Please enter code first.")
    cfg = LANGUAGE_CONFIG[language]
    directory = Path(directory)
    compile_command = None
    if language == "Java":
        javac, java = _find_command("javac"), _find_command("java")
        if not javac or not java:
            raise RuntimeError("Install a JDK with both java and javac on PATH to run Java.")
        # Preserve the public class name, constructors, and references.
        cleaned = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"', '', code, flags=re.S)
        match = re.search(r'\bpublic\s+(?:(?:final|abstract|sealed)\s+)*(?:class|record|enum)\s+(\w+)', cleaned)
        if not match:
            match = re.search(r'\bclass\s+(\w+)', cleaned)
        if not match:
            raise ValueError("Java code must declare a class containing public static void main(String[] args).")
        class_name = match.group(1)
        package = re.search(r'\bpackage\s+([\w.]+)\s*;', cleaned)
        entry = f"{package.group(1)}.{class_name}" if package else class_name
        source = directory / f"{class_name}.java"
        compile_command = [javac, "-encoding", "UTF-8", "-d", str(directory), str(source)]
        command = [java, "-Dfile.encoding=UTF-8", "-cp", str(directory), entry]
    else:
        source = directory / f"main{cfg['extension']}"
        if language in {"C", "C++"}:
            compiler = _find_command(cfg["compiler"])
            if not compiler:
                raise RuntimeError(f"Install GCC/MinGW with {cfg['compiler']} on PATH to run {language}.")
            executable = directory / ("program.exe" if os.name == "nt" else "program")
            # Pipe-based Windows/Linux consoles need C prompts flushed even
            # without a newline. GCC/MinGW's constructor runs before main().
            header = directory / "console_io.h"
            header.write_text('#include <stdio.h>\n__attribute__((constructor)) static void codepilot_console_init(void) { setvbuf(stdout, NULL, _IONBF, 0); setvbuf(stderr, NULL, _IONBF, 0); }\n', encoding="utf-8")
            compile_command = [compiler, str(source), "-O2", "-include", str(header), "-o", str(executable)]
            command = [str(executable)]
        else:
            runtime = _find_command(cfg["command"])
            if not runtime:
                raise RuntimeError(f"Install {cfg['command']} and add it to PATH to run {language}.")
            command = [runtime, "-u", str(source)] if language == "Python" else [runtime, str(source)]
    source.write_text(code, encoding="utf-8")
    return compile_command, command


class InteractiveRun:
    """One background run retained across Streamlit reruns; never calls UI APIs."""
    def __init__(self, language, code, max_runtime=300, max_output=100_000):
        self.language = language
        self.code = code
        self.max_runtime = max(0.1, float(max_runtime))
        self.max_output = max(1024, int(max_output))
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self.done = threading.Event()
        self._input = queue.Queue(maxsize=32)
        self._process = None
        self._output = ""
        self._bytes_seen = 0
        self._reason = ""
        self._status = "Starting"
        self._ready = False
        self._input_closed = False
        self.returncode = None
        self.work_directory = None
        with _JOBS_LOCK:
            _JOBS.add(self)
        self._thread = threading.Thread(target=self._work, daemon=True, name="codepilot-run")
        self._thread.start()

    def _append(self, text):
        with self._lock:
            self._bytes_seen += len(text)
            self._output = (self._output + text)[-self.max_output:]
            if self._bytes_seen > self.max_output and not self._reason:
                self._reason = "Output limit reached"
                self._cancel.set()

    def _read_output(self, pipe):
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                chunk = os.read(pipe.fileno(), 4096)
                if not chunk:
                    break
                self._append(decoder.decode(chunk))
            self._append(decoder.decode(b"", final=True))
        except (OSError, ValueError):
            pass
        finally:
            pipe.close()

    def _spawn(self, command, directory, interactive):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        with self._lock:
            if self._cancel.is_set():
                return None
            process = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE if interactive else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                                       env=env, shell=False, **kwargs)
            self._process = process
            self._ready = interactive
        return process

    def _write_input(self, process):
        while not self._cancel.is_set() and process.poll() is None:
            try:
                line = self._input.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if line is None:
                    process.stdin.close()
                    return
                self._append(f"\n> {line}\n")
                payload = memoryview((line + "\n").encode("utf-8"))
                while payload:
                    written = process.stdin.write(payload)
                    if not written:
                        raise BrokenPipeError("Program closed its input")
                    payload = payload[written:]
                process.stdin.flush()
            except (OSError, ValueError):
                return

    def _execute(self, command, directory, interactive, limit):
        process = self._spawn(command, directory, interactive)
        if process is None:
            return -1
        reader = threading.Thread(target=self._read_output, args=(process.stdout,), daemon=True)
        reader.start()
        writer = None
        if interactive:
            writer = threading.Thread(target=self._write_input, args=(process,), daemon=True)
            writer.start()
        deadline = time.monotonic() + limit
        while process.poll() is None:
            if time.monotonic() >= deadline:
                with self._lock:
                    self._reason = "Execution time limit reached" if interactive else "Compilation time limit reached"
                    self._cancel.set()
            if self._cancel.wait(0.025):
                _terminate_tree(process)
                break
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate_tree(process)
            process.wait(timeout=5)
        # Reap any remaining descendants before readers/temporary-file cleanup.
        _terminate_tree(process)
        reader.join(timeout=2)
        if process.stdin and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        if writer:
            writer.join(timeout=1)
        with self._lock:
            self._ready = False
        return process.returncode

    def _work(self):
        try:
            with tempfile.TemporaryDirectory(prefix="codepilot_") as folder:
                self.work_directory = folder
                compile_command, command = prepare_commands(self.language, self.code, folder)
                if compile_command:
                    with self._lock:
                        self._status = "Compiling"
                    code = self._execute(compile_command, folder, False, 45)
                    if code != 0 or self._cancel.is_set():
                        self.returncode = code
                        with self._lock:
                            self._status = self._reason or "Compilation error"
                        return
                with self._lock:
                    self._status = "Running — send input below if requested"
                self.returncode = self._execute(command, folder, True, self.max_runtime)
                with self._lock:
                    self._status = self._reason or ("Success" if self.returncode == 0 else "Runtime error")
        except Exception as exc:
            self._append(f"\n{exc}\n")
            with self._lock:
                self._status = self._reason or "Could not run code"
        finally:
            with self._lock:
                self._ready = False
            self.done.set()

    def send_input(self, line):
        line = str(line)
        if len(line.encode("utf-8")) > 4096:
            raise ValueError("Send at most 4096 bytes of input at a time.")
        with self._lock:
            if not self._ready or self.done.is_set() or self._input_closed:
                raise ValueError("The program is not accepting input. Start it or wait for compilation to finish.")
            try:
                self._input.put_nowait(line)
            except queue.Full as exc:
                raise ValueError("Input queue is full. Wait for the program to read previous inputs.") from exc

    def close_input(self):
        with self._lock:
            if not self._ready or self._input_closed:
                return
            try:
                self._input.put_nowait(None)
            except queue.Full as exc:
                raise ValueError("Wait for queued inputs before ending input.") from exc
            self._input_closed = True

    def stop(self):
        with self._lock:
            if self.done.is_set():
                return
            if not self._reason:
                self._reason = "Stopped"
            self._cancel.set()
            process = self._process
        _terminate_tree(process)

    def snapshot(self):
        with self._lock:
            return {"status": self._status, "stdout": self._output, "stderr": "",
                    "returncode": self.returncode, "finished": self.done.is_set(),
                    "accepts_input": self._ready and not self._input_closed and not self.done.is_set(),
                    "success": self.done.is_set() and self.returncode == 0 and not self._reason}


def run_code(language, code, stdin_text="", timeout=5):
    """Compatibility API for batch callers/tests, implemented by the live runner."""
    run = InteractiveRun(language, code, max_runtime=timeout)
    while not run.done.wait(0.01):
        if run.snapshot()["accepts_input"]:
            for line in stdin_text.splitlines():
                run.send_input(line)
            run.close_input()
            break
    run.done.wait(55 + float(timeout))
    if not run.done.is_set():
        run.stop()
        run.done.wait(6)
    return run.snapshot()


def _shutdown():
    with _JOBS_LOCK:
        jobs = list(_JOBS)
    for job in jobs:
        job.stop()


atexit.register(_shutdown)
