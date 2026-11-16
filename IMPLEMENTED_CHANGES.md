# Interactive console and reliability update

- Removed the standalone Standard Input and Timeout sections from Compiler.
- Added background compilation/execution with live line input, output, Stop,
  End Input and Clear Console; retained Python/C/C++/Java/JavaScript support.
- Preserved Java class names, constructors and package-qualified entry points.
- Used the current Python interpreter, unbuffered Python/C prompts, process-tree
  stopping, temporary-directory cleanup and internal output/duration limits.
- Added independent Local Ollama and Cloud AI APIs switches; both-enabled mode
  executes requests concurrently and labels both answers. One failure preserves
  the successful provider's answer.
- Fixed forgotten session-only API keys after saving; loaded .env from project root.
- Added configuration validation, per-provider connection checks, exact Ollama
  model-tag checks, documented OpenAI reasoning parameters and Gemini key headers.
- Kept usage writes atomic/nonfatal; fixed midnight rollover and malformed counters.
- Made vector RAG optional with local-notes retrieval fallback.
- Kept AI error messages after chat reruns and added recent-conversation context.
- Removed email/name-only password resets, protected unreadable account stores,
  reported account/settings write failures, and cleared session data on sign-out.
- Updated Windows installation/upgrade guides and automated regression coverage.

See UPGRADE_WINDOWS.md and VALIDATION_REPORT.txt for validation and limitations.
