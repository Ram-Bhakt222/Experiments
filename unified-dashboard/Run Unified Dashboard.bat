@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating .venv ...
    py -3 -m venv .venv || python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

if not exist ".env" (
    copy /Y .env.example .env >nul
)

echo.
echo Unified Dashboard starting at http://localhost:8910
echo.
start "" http://localhost:8910
python server.py
endlocal
