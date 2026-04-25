@echo off
cd /d "%~dp0"
title HALO -> Ram-Bhakt222/Experiments
color 0A
echo.
echo  ============================================================
echo                  PUSH HALO -> Experiments REPO
echo  ============================================================
echo  Target: https://github.com/Ram-Bhakt222/Experiments
echo  Adds:   halo-hair-analysis/
echo  ============================================================
echo.

REM Check git is installed
where git >nul 2>&1
if errorlevel 1 (
  echo  ERROR: Git is not installed.
  echo  Download: https://git-scm.com/download/win
  pause
  exit /b 1
)

set REPO_URL=https://github.com/Ram-Bhakt222/Experiments.git
set CLONE_DIR=%~dp0..\Experiments
set SUBDIR=%CLONE_DIR%\halo-hair-analysis

REM 1) Clone or pull the existing repo
if exist "%CLONE_DIR%\.git" (
  echo  [1/5] Found local clone, pulling latest...
  pushd "%CLONE_DIR%"
  git pull --rebase
  popd
) else (
  echo  [1/5] Cloning %REPO_URL% to a sibling folder...
  if exist "%CLONE_DIR%" rmdir /S /Q "%CLONE_DIR%"
  git clone "%REPO_URL%" "%CLONE_DIR%"
  if errorlevel 1 (
    echo  Clone failed. Check that you can access the repo and you are signed in.
    pause
    exit /b 1
  )
)

REM 2) Wipe any stale halo subfolder so we replace cleanly
if exist "%SUBDIR%" (
  echo  Refreshing existing halo-hair-analysis subfolder...
  rmdir /S /Q "%SUBDIR%"
)
mkdir "%SUBDIR%"

REM 3) Copy HALO files into the subfolder (excluding secrets and runtime artifacts)
echo  [2/5] Copying HALO into Experiments/halo-hair-analysis/ ...
xcopy /E /I /Y /Q ".\*" "%SUBDIR%\" >nul
del /Q "%SUBDIR%\.env" 2>nul
del /Q "%SUBDIR%\leads.csv" 2>nul
del /Q "%SUBDIR%\Push to GitHub.bat" 2>nul
if exist "%SUBDIR%\__pycache__" rmdir /S /Q "%SUBDIR%\__pycache__"
if exist "%SUBDIR%\.git" rmdir /S /Q "%SUBDIR%\.git"

REM 4) Make sure parent .gitignore excludes secrets across all experiments
cd /d "%CLONE_DIR%"
findstr /M /C:".env" .gitignore >nul 2>&1
if errorlevel 1 (
  >> ".gitignore" echo.
  >> ".gitignore" echo # halo-hair-analysis safety
  >> ".gitignore" echo .env
  >> ".gitignore" echo leads.csv
  >> ".gitignore" echo __pycache__/
)

git config user.email "jeanelle@wombhealthfm.com"
git config user.name "Jeanelle"

echo  [3/5] Staging changes...
git add .
git status --short
echo.

echo  [4/5] Verifying no secrets staged...
git ls-files | findstr /I /R "\\.env$ leads\.csv$" >nul
if not errorlevel 1 (
  echo  ERROR: .env or leads.csv made it into staging. Aborting.
  pause
  exit /b 1
)

echo  Committing...
git commit -m "Add/update halo-hair-analysis"
echo.

echo  [5/5] Pushing to GitHub...
git push
if errorlevel 1 (
  echo.
  echo  Push failed. From the Experiments folder, you can retry:
  echo    cd "%CLONE_DIR%"
  echo    git push
  pause
  exit /b 1
)

echo.
echo  ============================================================
echo  DONE - https://github.com/Ram-Bhakt222/Experiments/tree/main/halo-hair-analysis
echo  ============================================================
echo.
pause
