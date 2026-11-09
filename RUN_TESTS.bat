@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo [ERROR] Python 3 not found & pause & exit /b 1)
if not exist venv python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
python -m pytest -v
pause
