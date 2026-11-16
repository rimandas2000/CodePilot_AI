"""Regression checks; standard library only, no API key or AI server needed."""
import ast
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from contextlib import nullcontext
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
import json_storage
from executor import run_code


def process_write(path, value):
    json_storage.atomic_write_json(Path(path), {"value": value})


class Session(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "usage.json"
        self.path.write_text('{"original": true}', encoding="utf-8")

    def test_legacy_temp_path_is_never_used(self):
        # A directory occupying the old filename would break the old code.
        (self.path.parent / "usage.tmp").mkdir()
        json_storage.atomic_write_json(self.path, {"name": "বাংলা"})
        self.assertEqual(json.loads(self.path.read_text()), {"name": "বাংলা"})
        self.assertEqual(list(self.path.parent.glob(".usage.json.*.tmp")), [])

    def test_concurrent_threads_leave_complete_json(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: process_write(str(self.path), i), range(48)))
        self.assertIn(json.loads(self.path.read_text())["value"], range(48))
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_concurrent_processes_use_distinct_temp_files(self):
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
            list(pool.map(process_write, [str(self.path)] * 24, range(24)))
        self.assertIn(json.loads(self.path.read_text())["value"], range(24))
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_transient_replace_lock_recovers(self):
        real_replace = json_storage.os.replace
        sources = []

        def sometimes_locked(source, target):
            sources.append(source)
            if len(sources) < 3:
                raise PermissionError("Simulated Windows sharing violation")
            return real_replace(source, target)

        with patch.object(json_storage.os, "replace", side_effect=sometimes_locked), patch.object(json_storage.time, "sleep"):
            json_storage.atomic_write_json(self.path, {"saved": True})
        self.assertEqual(len(set(sources)), 3)
        self.assertEqual(json.loads(self.path.read_text()), {"saved": True})
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_persistent_replace_lock_preserves_existing_data(self):
        with patch.object(json_storage.os, "replace", side_effect=PermissionError("locked")) as replace, patch.object(json_storage.time, "sleep"):
            with self.assertRaises(PermissionError):
                json_storage.atomic_write_json(self.path, {"lost": True})
        self.assertEqual(replace.call_count, 5)
        self.assertEqual(json.loads(self.path.read_text()), {"original": True})
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_temp_creation_denied_retries_without_damaging_usage(self):
        with patch.object(json_storage.tempfile, "NamedTemporaryFile", side_effect=PermissionError("denied")) as create, patch.object(json_storage.time, "sleep"):
            with self.assertRaises(PermissionError):
                json_storage.atomic_write_json(self.path, {})
        self.assertEqual(create.call_count, 5)
        self.assertEqual(json.loads(self.path.read_text()), {"original": True})

    def test_other_disk_error_preserves_existing_data(self):
        with patch.object(json_storage.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                json_storage.atomic_write_json(self.path, {})
        self.assertEqual(json.loads(self.path.read_text()), {"original": True})
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def app_functions(self):
        # Run the actual functions without launching Streamlit or an AI model.
        names = {"save_usage", "track_active_time", "record_usage", "add_activity", "active_settings", "safe_ai", "run_general_chat"}
        tree = ast.parse((BACKEND / "app.py").read_text(encoding="utf-8"))
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        session = Session(usage={"last_seen": 0, "questions": 0}, settings={})
        ui = SimpleNamespace(session_state=session, warning=Mock(), error=Mock(), spinner=lambda *a: nullcontext())
        import time
        from datetime import datetime
        env = {"st": ui, "atomic_write_json": Mock(side_effect=PermissionError("denied")),
               "USAGE_FILE": self.path, "SYSTEM_PROMPT": "test", "time": time, "datetime": datetime,
               "active_provider": lambda _: "Test", "active_model": lambda _: "test-model",
               "load_settings": lambda: {}, "generate_text": Mock(return_value="Here is your input-based code.")}
        exec(compile(tree, str(BACKEND / "app.py"), "exec"), env)
        return env, ui

    def test_heartbeat_survives_permission_error_and_warns_once(self):
        env, ui = self.app_functions()
        env["track_active_time"]()
        env["track_active_time"]()
        self.assertEqual(ui.warning.call_count, 1)
        self.assertGreater(ui.session_state.usage["last_seen"], 0)

    def test_ai_answer_survives_usage_permission_error(self):
        env, ui = self.app_functions()
        answer = env["run_general_chat"]("Write magic-number code using user input")
        self.assertEqual(answer, "Here is your input-based code.")
        self.assertEqual(ui.session_state.usage["questions"], 1)
        self.assertEqual(ui.session_state.usage["ai_uses"], 1)
        self.assertEqual(len(ui.session_state.usage["activity"]), 1)
        ui.error.assert_not_called()

    def test_next_update_saves_retained_usage_after_recovery(self):
        env, ui = self.app_functions()
        env["record_usage"]("questions")
        env["atomic_write_json"] = json_storage.atomic_write_json
        env["record_usage"]("questions")
        self.assertEqual(json.loads(self.path.read_text())["questions"], 2)
        self.assertFalse(ui.session_state.usage_save_warning_shown)

    def test_magic_number_accepts_standard_input(self):
        source = (BACKEND.parent / "examples" / "magic_number.py").read_text()
        for value, expected in [("1729\n", "1729 is a magic number."), ("123\n", "123 is not a magic number."), ("0\n", "Please enter a positive integer."), ("hello\n", "Invalid input."), ("", "No input received.")]:
            with self.subTest(value=value):
                result = run_code("Python", source, value)
                self.assertTrue(result["success"], result)
                self.assertIn(expected, result["stdout"])


if __name__ == "__main__":
    unittest.main()
