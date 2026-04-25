@echo off
cd /d "%~dp0"
title HALO - Hair Analysis
color 0A
echo.
echo  ============================================================
echo                  HALO - Personal Style Analysis
echo  ============================================================
echo.
echo  Starting up...
echo.
taskkill /F /IM python.exe >nul 2>&1
python -m pip install --quiet --disable-pip-version-check flask openai httpx fal-client
if errorlevel 1 (
  echo  ERROR: Could not install dependencies.
  echo  Install Python 3.9+ from https://www.python.org/downloads/
  pause
  exit /b 1
)
timeout /t 1 /nobreak > nul
start "" http://localhost:8765/?v=%RANDOM%%RANDOM%
echo.
echo  Server running. Browser opening at http://localhost:8765
echo  Close this window or press Ctrl+C to stop.
echo.
echo  ============================================================
echo.
python server.py
pause
