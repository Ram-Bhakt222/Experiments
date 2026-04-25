@echo off
cd /d "%~dp0"
echo ============================================================
echo  HALO - Personal Style Analysis
echo ============================================================
echo.
echo Killing any old python servers...
taskkill /F /IM python.exe >nul 2>&1
echo.
echo Installing dependencies (first run only, ~30s)...
python -m pip install --quiet --disable-pip-version-check flask openai httpx fal-client
if errorlevel 1 (
  echo Failed to install dependencies. Make sure Python 3.9+ is installed.
  pause
  exit /b 1
)
echo Dependencies ready.
echo.
echo Opening browser with cache-busting URL...
timeout /t 2 /nobreak > nul
start "" http://localhost:8765/?v=%RANDOM%%RANDOM%
echo.
echo Starting server (press Ctrl+C to stop)...
echo ============================================================
echo.
python server.py
pause
