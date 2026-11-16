# CodePilot AI — Interactive Coding Workspace

CodePilot AI is a Streamlit coding mentor with **cloud API providers only**: OpenAI, Gemini, or Groq. It also includes local programming notes (RAG), an interactive code console, debugging, explanations, code improvement, and code conversion.

## Run locally on Windows

1. Install Python 3.11 or 3.12.
2. Open a terminal in the `CodePilot_AI` project folder.
3. Create an environment, install dependencies, and launch the app:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run backend\app.py
```

4. Open the local address Streamlit prints, usually `http://localhost:8501`.
5. Create an account or sign in. Open **Settings**, choose OpenAI, Gemini, or Groq, enter the provider's API key and model, then select **Save Settings** and **Test Enabled Connections**.

You can also launch the app with `start_windows.bat`.

## API key setup

Choose one cloud provider in **Settings**. The key must be valid for that provider and the selected model must be available to your account. CodePilot sends prompts and retrieved context to the selected cloud provider.

For local runs, you can enter the key in Settings or put it in a local `.env` file copied from `.env.example`. Set the matching `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `GROQ_API_KEY` variable. Never commit a real `.env` file or API key to GitHub. On the hosted app, configure the key in CodePilot's Settings after signing in.

## Deploy on Streamlit Community Cloud

1. Push the project files to a GitHub repository. Keep `requirements.txt` at the repository root.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and choose **Create app** → **Deploy from repo**.
3. Select your GitHub repository and branch. Set **Main file path** to `backend/app.py`.
4. Select **Deploy**. Streamlit installs `requirements.txt` and starts CodePilot.
5. Open the app URL, create an account or sign in, and configure the cloud provider in **Settings** as described above.

The current CodePilot deployment uses `rimandas2000/CodePilot_AI`, branch `main`, and `backend/app.py`.

## Use CodePilot

- **Home / AI Mentor Chat:** ask a coding question or request help with a concept.
- **Compiler / Run Code:** choose Python, C, C++, Java, or JavaScript, enter code, and run it. The Live Console accepts program input; use **End Input** for EOF or **Stop** to end a run.
- **Debug & Fix, Explain Code, Improve Code, Convert Code:** paste or upload code and follow the page prompts. If language detection is uncertain, choose the language manually.
- **Settings:** choose the cloud provider, manage the API key and model, test the connection, and turn local RAG knowledge on or off.
- **Dashboard, Recent Activity, About:** review usage and app information.

C and C++ require GCC/G++, Java requires a JDK, and JavaScript requires Node.js on the host running the app. Python uses the app's Python environment. Code execution has runtime and output limits and should be used only with trusted code.

## Optional vector RAG

Local keyword-based retrieval works without extra packages. To enable ChromaDB embeddings and rebuild the index:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-rag.txt
.venv\Scripts\python.exe backend\ingest.py
```

The embedding model may need an internet connection for its first download.

## Tests and operating notes

Run the included checks with:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See `VALIDATION_REPORT.txt` and `UPGRADE_WINDOWS.md` for tested cases and known limits. Accounts, usage, and settings use local JSON files in the app environment; use one server for this personal workspace. Passwords are stored as salted PBKDF2 hashes. Verified email password recovery is not provided.
