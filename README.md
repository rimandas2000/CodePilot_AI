# CodePilot AI — Interactive Coding Workspace

A Streamlit coding mentor with local Ollama, optional OpenAI/Gemini/Groq APIs,
local knowledge retrieval, and an interactive code console.

## What's updated

- Removed the Generate Tests section.
- Added automatic detection of recognizable C, C++, Python, Java and JavaScript code in Compiler, Debug & Fix, Explain Code, Improve Code and Convert Code.
- In Convert Code, pasting source automatically updates the source-language dropdown; choose the desired target separately.
- If a snippet is too short or ambiguous to identify reliably, select its language manually.
- Uploaded source files use their extension to help identify their language.
- Language choices are retained when navigating between Compiler, Debug, Explain, Improve and Convert: the application stores the preference separately from Streamlit widget state and uses recognizable editor code when re-entering a page.

**Existing installation:** follow `UPGRADE_WINDOWS.md` to update the backend and
packages while keeping your account, settings, API keys and progress.

## Start a fresh installation

Install Python 3.11 or 3.12, then in this project's folder:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run backend\app.py
```

Open the address printed by Streamlit, normally http://localhost:8501.
You can also use `start_windows.bat`. Create an account or sign into your existing
local account. Set up your AI providers in Settings.

## AI modes

- Local Ollama on, Cloud AI APIs off: local answer only.
- Local Ollama off, Cloud AI APIs on: selected cloud answer only.
- Both on: independent parallel answers from Ollama and your cloud provider.
- Both off: configuration cannot be saved.

Enter the correct model, URL and API key, then Save Settings and Test Enabled
Connections. Cloud calls need an accessible API account, available model and quota.
If you choose not to remember API keys, they stay available only in the current
session or can be supplied through `.env` copied from `.env.example`.

## Compiler

Choose Python, C, C++, Java or JavaScript. Run / Compile starts a program; the
Live Console accepts input while it runs. Send each requested value, use End Input
for EOF, and Stop to end a run. No separate stdin or timeout section is shown.
Requires GCC/G++ for C/C++, a full JDK for Java, or Node.js for JavaScript. Python
uses CodePilot's own interpreter. The console supports line input, not raw TTY or
GUI interactions. Runs have internal duration/output limits.

## Other pages

Home, AI Mentor Chat, Debug & Fix, Explain Code, Improve Code, Generate Tests,
Convert Code, Dashboard, Recent Activity, Settings and About. Editors use Ace
when available and fall back to native Streamlit text areas.

## Optional vector RAG

Without ChromaDB, RAG uses keyword-matched local notes from `backend/knowledge`.
To enable ChromaDB embeddings and rebuild its index:

```bat
python -m pip install -r requirements-rag.txt
python backend/ingest.py
```

The embedding model may require a first-time internet download.

## Tests and operating limits

```bat
python -m unittest discover -s tests -v
```

See `VALIDATION_REPORT.txt` and `UPGRADE_WINDOWS.md` for tested cases and remaining
limits. Usage writes cannot stop chat when statistics cannot be saved. Use a single
server for this personal JSON-backed workspace. Local code execution is trusted
code execution with your user's permissions, not a public multi-user sandbox.
Cloud prompts and retrieved context are sent to the enabled cloud provider. Saved
keys are plain local configuration when remembering keys is enabled. New passwords
are stored as salted PBKDF2 hashes; no verified email password recovery is provided.
