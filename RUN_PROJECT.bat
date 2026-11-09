@echo off
setlocal
cd /d "%~dp0"
echo ==== Event Registration System ====
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3 is not installed or not on PATH. Install from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause & exit /b 1
)
if not exist venv (
  echo Creating virtual environment...
  python -m venv venv || (echo [ERROR] Could not create venv & pause & exit /b 1)
)
call venv\Scripts\activate.bat
echo Installing requirements...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt || (echo [ERROR] pip install failed & pause & exit /b 1)
if not exist .env copy .env.example .env >nul
echo Initialising and seeding database if needed...
python -m database.seed_data || (echo [ERROR] Database setup failed & pause & exit /b 1)
echo.
echo Open http://127.0.0.1:5000 in your browser  (Ctrl+C to stop)
python -m backend.app
pause
