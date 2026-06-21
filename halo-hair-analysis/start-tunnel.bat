@echo off
REM Starts HALO Flask server + ngrok tunnel.
REM Both run in the background. Close this window — they stay running.
REM To stop them, run stop-tunnel.bat.
cd /d "%~dp0"
title HALO + ngrok tunnel
color 0A

echo.
echo  ============================================================
echo                HALO LIVE TUNNEL STARTUP
echo  ============================================================
echo.

REM 1) Kill any old Flask / ngrok processes on this port
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8765 .*LISTENING"') do (
  echo  Killing stale Flask PID %%P
  taskkill /F /PID %%P >nul 2>&1
)
taskkill /F /IM ngrok.exe >nul 2>&1

REM 2) Start Flask in the background
echo  [1/2] Starting Flask server on http://localhost:8765 ...
start "HALO Flask" /B /MIN cmd /c "python server.py > flask.stdout.log 2> flask.stderr.log"

REM Wait until Flask is listening (max 20s)
set /a wait=0
:waitloop
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":8765 .*LISTENING" >nul
if errorlevel 1 (
  set /a wait+=1
  if %wait% LSS 20 goto waitloop
  echo   Flask did not start in 20s. Check flask.stderr.log.
  pause
  exit /b 1
)
echo   Flask is up.

REM 3) Start ngrok in the background
echo  [2/2] Starting ngrok tunnel ...
start "ngrok" /B /MIN cmd /c "ngrok http 8765 --log stdout --log-format logfmt > ngrok.stdout.log 2> ngrok.stderr.log"
timeout /t 5 /nobreak >nul

REM 4) Pull the public URL from ngrok's local API
echo.
echo  Fetching public URL ...
powershell -NoProfile -Command "$api = Invoke-RestMethod -Uri http://127.0.0.1:4040/api/tunnels -TimeoutSec 10; $u = $api.tunnels[0].public_url; Write-Host ''; Write-Host '  ============================================================' -ForegroundColor Cyan; Write-Host ('  PUBLIC URL:  ' + $u) -ForegroundColor Green; Write-Host '  ============================================================' -ForegroundColor Cyan; Write-Host ''; Write-Host '  ngrok dashboard: http://127.0.0.1:4040  (see live requests)'; Write-Host ''; $u | Set-Clipboard; Write-Host '  URL copied to clipboard.' -ForegroundColor Yellow"

echo.
echo  Tunnel is live. Close this window — Flask + ngrok keep running.
echo  Run stop-tunnel.bat to stop both.
echo.
pause
