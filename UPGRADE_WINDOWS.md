# CodePilot AI — Interactive Console Upgrade

## Update your existing installation

1. Press **Ctrl+C** in every terminal running CodePilot.
2. Back up your existing project folder. Extract this ZIP into a separate folder.
3. Copy the extracted project's entire `backend` folder, `requirements.txt`,
   `requirements-rag.txt`, `start_windows.bat`, and `examples` folder into your
   existing `C:\Users\Hp\Downloads\CodePilot_AI` folder, replacing matching files.
   The new `backend/json_storage.py` is required.
4. Keep your existing `data`, `.env`, `.venv`, and `chroma_db` folders/files.
   These contain your accounts, settings, progress, environment and knowledge.
5. In a terminal opened in the existing project folder, run:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run backend\app.py
```

If you run through Anaconda instead of `.venv`, replace
`.venv\Scripts\python.exe` with `python` from your normal Anaconda environment.
Refresh the browser after restarting. Upgrading packages is required because
this version uses the tested Streamlit release for its live console.

## Run code and enter input

1. Open **Compiler / Run Code**, choose your language and paste your code.
2. Click **Run / Compile**. The **Live Console** displays the program's output.
3. When the program asks for a value, type it into **Program input** and press
   Enter or **Send Input**. Repeat for subsequent questions. Blank input is valid.
4. Use **End Input (EOF)** when finished entering data for a program that reads
   until the input stream ends. This is also useful for Node.js programs whose
   input stream stays open after `readline.close()`.
5. Use **Stop** to terminate a run. Clear Console stops the run and removes its
   display. Leaving the compiler page or signing out stops its program.

The former **Standard Input (optional)** and **Timeout (seconds)** sections are
removed. This is a line-based console, not a shell or a terminal for raw keypress,
TTY, password/getch, curses, or GUI programs. Programs have an internal five-minute
limit (including time spent waiting for input), compilation has a 45-second limit,
and excessive output stops the run. These limits prevent abandoned programs from
running indefinitely without an extra settings section on the compiler page.

Python uses the same interpreter as CodePilot. For other languages install the
corresponding tools and put them on PATH: GCC for C, G++ for C++, a full JDK with
both java and javac for Java, and Node.js for JavaScript. Java class names,
constructors and packages are preserved. Compilation/runtime diagnostics appear
in the console rather than raising an app exception.

**Magic-number example:** open `examples/magic_number.py`, paste it into the
compiler, click Run / Compile, then send `1729`. The program uses repeated digit
sum equal to 1 as the definition and prints `1729 is a magic number.`

## Ollama, cloud API, or both

Open Settings. The two switches are independent:

| Local Ollama | Cloud AI APIs | Behavior after Save Settings |
|---|---|---|
| On | Off | One answer from your local Ollama model; no API key needed |
| Off | On | One answer from the selected OpenAI, Gemini or Groq API; Ollama is not contacted |
| On | On | Same request sent to both in parallel; answers shown separately with provider labels |
| Off | Off | Saving is blocked with a clear configuration message |

For local use, start Ollama, choose its server URL, and install the exact selected
model, for example `ollama pull qwen2.5-coder:7b`. A reachable server with a
different model tag is not treated as proof that the selected model is installed.

For Gemini, this package includes `.env` and `.env.example` with
`GEMINI_MODEL=gemini-3.8-flash`. Add your real `GEMINI_API_KEY` locally. If you
already have a `.env`, edit only its `GEMINI_MODEL` line and retain your keys.
Restart CodePilot after editing environment configuration, select Gemini in
Settings, and test the connection to verify model access for your account.

For cloud use, select a provider and enter a valid API key and a model your API
account can access. Save Settings, then **Test Enabled Connections**. The test
reports each enabled backend separately and makes a small cloud inference request.
Configured status on ordinary pages is not proof of successful connectivity.

With both switches on, a failed backend appears as unavailable while the other
answer remains. If both fail, the app shows the error. No silent fallback to a
provider you disabled is performed. Combined mode sends the same prompt/context
to the selected cloud service and uses its API quota as well as local resources.
It produces two answers rather than one fused answer. Code conversion's
"use converted code" action selects the first returned code block; review it
before using it when two providers answered.

When **Remember API keys locally** is unchecked, the key remains usable throughout
the current browser session but is omitted from saved settings. Re-enter it after
a new session or provide it in `.env`. `.env` is loaded from this project's folder
regardless of the directory from which the app is launched. Do not share real keys.
Model names stay editable; availability and quota are controlled by your provider.

## Other repairs

- Usage JSON writes have unique temporary files, atomic replacement, short lock
  retries and nonfatal error handling. Locked/unwritable statistics cannot discard
  a successful AI answer. Session statistics are retried on subsequent updates.
- Daily usage rolls over when an open session crosses midnight. Invalid stored
  numeric/activity fields no longer crash Dashboard or Home.
- Optional ChromaDB is imported only when used. Without vector dependencies,
  enabled RAG uses keyword-matched local notes. For vector RAG, install
  `python -m pip install -r requirements-rag.txt`, then run `python backend/ingest.py`.
  Its initial embedding download needs internet. Both local and cloud AI can use RAG.
- Settings disk failures are shown without claiming success. Local account writes
  report failures; unreadable account files are not overwritten with an empty store.
- Password recovery based only on email/display name has been removed. This local
  app has no verified email-recovery service; the installation owner must restore
  access from a trusted backup.
- Signing out clears the previous user's chat/settings session. AI errors remain
  visible after automatic chat reruns; recent messages are included in follow-up
  prompts. The Windows launcher stops when package installation fails.

## Verification and limits

Run `python -m unittest discover -s tests -v` after installing requirements.
The bundled report records the tested environment and exact result. It covers
real Streamlit workflows, live Python/C/C++/Node input, provider request fixtures,
combined-provider concurrency/failures, settings persistence, usage locks and
runner cleanup. Java command preparation is tested; native Java execution requires
an installed JDK. Windows process behavior and live paid API/Ollama inference have
not been tested on your computer. Use Test Enabled Connections for your credentials,
models and network. No project can be guaranteed free of all possible bugs.

Usage is still a whole-workspace JSON snapshot; multiple independent server
sessions do not merge counters transactionally. Run one server for this personal
workspace. The runner executes trusted code as the server user; it is not a secure
sandbox for public deployment.

Provider references used for API compatibility checks:
- https://developers.openai.com/api/reference/resources/chat
- https://ai.google.dev/api/generate-content
- https://console.groq.com/docs/api-reference
- https://docs.ollama.com/api/tags
