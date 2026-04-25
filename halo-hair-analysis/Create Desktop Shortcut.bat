@echo off
cd /d "%~dp0"
echo Creating Desktop shortcut to HALO...
powershell -NoProfile -Command ^
  "$WshShell = New-Object -comObject WScript.Shell; ^
   $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\HALO Hair Analysis.lnk'); ^
   $Shortcut.TargetPath = '%~dp0Run HALO.bat'; ^
   $Shortcut.WorkingDirectory = '%~dp0'; ^
   $Shortcut.Description = 'AI Hair + Color Analysis'; ^
   $Shortcut.IconLocation = 'C:\Windows\System32\shell32.dll,77'; ^
   $Shortcut.Save()"
echo.
echo  Done! Look on your Desktop for "HALO Hair Analysis"
echo.
pause
