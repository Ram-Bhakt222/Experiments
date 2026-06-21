@echo off
REM Stops Flask + ngrok.
echo.
echo  Stopping ngrok ...
taskkill /F /IM ngrok.exe >nul 2>&1

echo  Stopping Flask (anything listening on port 8765) ...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8765 .*LISTENING"') do (
  echo   Killing PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo.
echo  Done.
timeout /t 2 /nobreak >nul
