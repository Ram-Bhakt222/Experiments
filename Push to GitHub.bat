@echo off
cd /d "%~dp0"
title HALO - Push to GitHub
color 0A
echo.
echo  ============================================================
echo                  PUSH HALO TO GITHUB
echo  ============================================================
echo.

REM Check git is installed
where git >nul 2>&1
if errorlevel 1 (
  echo  ERROR: Git is not installed.
  echo  Download: https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

REM Step 1: clean any leftover .git
if exist ".git" (
  echo  Cleaning previous .git folder...
  rmdir /S /Q .git 2>nul
)

REM Step 2: init + configure
echo  [1/5] Initializing repo...
git init -q
git config user.email "jeanelle@wombhealthfm.com"
git config user.name "Jeanelle"
git branch -M main 2>nul

REM Step 3: stage and commit
echo  [2/5] Staging files (secrets excluded by .gitignore)...
git add .

echo.
echo  Staged files:
git status --short
echo.

echo  [3/5] Verifying .env and leads.csv are NOT staged...
git ls-files | findstr /I /R "^\.env$ ^leads.csv$" >nul
if not errorlevel 1 (
  echo  ERROR: .env or leads.csv made it into the commit!
  echo  Aborting for safety. Check .gitignore.
  pause
  exit /b 1
)
echo  OK - no secrets staged.
echo.

echo  [4/5] Committing...
git commit -q -m "Initial commit: HALO AI Hair and Color Analysis"
git log --oneline -1
echo.

REM Step 4: get the remote URL
echo  ============================================================
echo  STEP 1 of 2: Create the repo on GitHub.com
echo  ============================================================
echo.
echo  This will open GitHub in your browser. Create a NEW repo:
echo    - Name: halo-hair-analysis  (or whatever you want)
echo    - Privacy: Private (recommended - protects API costs)
echo    - Do NOT initialize with README, .gitignore, or license
echo  After clicking 'Create repository', copy the HTTPS URL
echo  (looks like: https://github.com/yourname/halo-hair-analysis.git)
echo.
echo  Press any key to open GitHub...
pause >nul
start "" https://github.com/new
echo.

echo  ============================================================
echo  STEP 2 of 2: Paste the repo URL below
echo  ============================================================
set /p REPO_URL="  Paste the HTTPS URL: "

if "%REPO_URL%"=="" (
  echo  No URL provided. Aborting.
  pause
  exit /b 1
)

echo.
echo  [5/5] Pushing to %REPO_URL% ...
git remote add origin %REPO_URL%
git push -u origin main

if errorlevel 1 (
  echo.
  echo  Push failed. Common fixes:
  echo    1. Check the URL is correct and the repo exists.
  echo    2. If credentials prompt failed, run: git push -u origin main
  echo       and sign in to GitHub when prompted.
  echo.
  pause
  exit /b 1
)

echo.
echo  ============================================================
echo  DONE - HALO is on GitHub.
echo  View at: %REPO_URL:.git=%
echo  ============================================================
echo.
pause
