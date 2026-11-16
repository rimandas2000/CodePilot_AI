@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment. Make sure Python is installed and on PATH.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package installation failed. Check the error above before starting CodePilot.
  pause
  exit /b 1
)
echo Use Settings to select a cloud AI provider and enter its API key.
echo.
echo Starting CodePilot AI...
python -m streamlit run backend\app.py
pause
