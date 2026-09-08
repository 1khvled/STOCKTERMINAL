@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo      StockerAI Standalone Classic Terminal
echo ============================================
echo.

:: Check for virtual environment
IF EXIST "venv\Scripts\activate.bat" GOTO activate_venv

echo [*] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [-] Error: Failed to create virtual environment. 
    echo     Please ensure Python is installed and added to your PATH.
    pause
    exit /b 1
)

:activate_venv

echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

echo [*] Checking requirements...
if exist requirements.txt (
  pip show flask >nul 2>&1 || pip install -r requirements.txt
)

echo.
echo [*] Starting the terminal server...
python -u -m app.server

pause
