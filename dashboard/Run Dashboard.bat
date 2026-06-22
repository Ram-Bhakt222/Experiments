@echo off
setlocal
cd /d "%~dp0"

REM First run: create venv + install deps
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
    echo [setup] Copy .env.example -> .env (edit it after this run, then re-launch)
    copy /Y .env.example .env >nul
)

if not exist "users.json" (
    echo [setup] No users.json yet -- using SHARED_SECRET fallback as user "admin"
)

echo.
echo Dashboard starting at http://localhost:8900
echo Login user: admin   password: (your SHARED_SECRET in .env)
echo.
python server.py
endlocal
