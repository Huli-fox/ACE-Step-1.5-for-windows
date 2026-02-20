@echo off
REM ============================================================
REM  ACE-Step — Single-Click Launcher with Loading Screen
REM  Opens browser immediately, then launches the existing
REM  PowerShell scripts that are known to work.
REM ============================================================
setlocal
chcp 65001 >nul 2>&1

cd /d "%~dp0"

REM Tell start.bat not to open a browser — our loading page handles that
set "ACESTEP_NO_BROWSER=1"

echo.
REM Read frontend port from .env
set "VITE_PORT=3000"
if exist "ace-step-ui\.env" (
    for /f "tokens=2 delims==" %%a in ('findstr /b "VITE_PORT" "ace-step-ui\.env"') do set "VITE_PORT=%%a"
)

echo =============================================
echo   ACE-Step One-Click Launcher
echo =============================================
echo.

REM ---- Step 1: Open loading page in browser immediately ----
echo [1/4] Opening loading screen...
echo var VITE_PORT = '%VITE_PORT%'; > "%~dp0loading-config.js"
start "" "%~dp0loading.html"
echo   Done.
echo.

REM ---- Step 2: Check UI dependencies ----
echo [2/4] Checking UI dependencies...
if not exist "ace-step-ui\node_modules" (
    echo   Installing frontend dependencies...
    cd ace-step-ui
    call npm install
    cd ..
)
if not exist "ace-step-ui\server\node_modules" (
    echo   Installing server dependencies...
    cd ace-step-ui\server
    call npm install
    cd ..\..
)
echo   Done.
echo.

REM ---- Step 2b: Rebuild server TypeScript ----
echo [2b/4] Building server...
cd ace-step-ui\server
call npx tsc 2>nul
cd ..\..
echo   Done.
echo.

REM ---- Step 3: Start Python API server via existing PS1 script ----
echo [3/4] Starting Python API server...
start /min "ACE-Step Python API" powershell -ExecutionPolicy Bypass -Command "Set-Location '%~dp0'; & '.\3、run_server.ps1'"
echo   Started.
echo.

REM ---- Step 4: Start UI via existing PS1 script ----
echo [4/4] Starting UI servers...
start /min "ACE-Step UI" powershell -ExecutionPolicy Bypass -Command "Set-Location '%~dp0'; & '.\4、run_npmgui.ps1'"
echo   Started (minimized window).
echo.

REM ---- Done ----
echo =============================================
echo   All services starting up!
echo =============================================
echo.
echo   The loading screen is open in your browser.
echo   It will auto-redirect to ACE-Step once
echo   all services are ready.
echo.
echo   Python API:  http://localhost:8001
echo   Backend:     http://localhost:3001
echo   Frontend:    http://localhost:%VITE_PORT%
echo.
echo   Two minimized windows are running:
echo     - Python API (run_server.ps1)
echo     - UI servers  (run_npmgui.ps1)
echo.
echo   Close those windows to stop the services.
echo =============================================
echo.
echo Press any key to close this launcher window...
echo (Services will keep running in the background)
pause >nul
