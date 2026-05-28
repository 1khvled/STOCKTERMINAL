@echo off
echo ============================================
echo      StockerAI Server Terminator
echo ============================================
echo.

echo [*] Attempting to terminate any running StockerAI servers...

:: 1. Terminate any python process specifically running server.py
wmic process where "name='python.exe' and commandline like '%%server.py%%'" call terminate >nul 2>&1

:: 2. Terminate any python process specifically running stock_analyzer.py (background tasks)
wmic process where "name='python.exe' and commandline like '%%stock_analyzer.py%%'" call terminate >nul 2>&1

:: 3. As a fallback, forcefully kill anything squatting on the server's default port (5001)
FOR /F "tokens=5" %%T IN ('netstat -a -n -o ^| findstr :5001') DO (
    if not "%%T"=="0" (
        taskkill /PID %%T /F >nul 2>&1
    )
)

echo [+] All terminal servers and background quant tasks should now be fully offline.
echo.
pause
