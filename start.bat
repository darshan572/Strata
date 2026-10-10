@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Strata Search Engine Launcher (Local ^& Network)
echo ========================================================
echo.

:: Detect valid working Python executable
set "PYTHON_CMD="

if exist "%~dp0sylvasearch\backend\.venv\Scripts\python.exe" (
    "%~dp0sylvasearch\backend\.venv\Scripts\python.exe" -c "exit(0)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD="%~dp0sylvasearch\backend\.venv\Scripts\python.exe""
    )
)

if not defined PYTHON_CMD (
    python -c "exit(0)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    if exist "C:\Program Files\Python313\python.exe" (
        set "PYTHON_CMD="C:\Program Files\Python313\python.exe""
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] No working Python installation was found.
    echo Please make sure Python is installed and added to PATH.
    pause
    exit /b 1
)

echo [OK] Using Python: %PYTHON_CMD%

:: Verify Node.js installation for frontend
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js was not found in PATH.
    echo Please install Node.js from https://nodejs.org/ to run the Strata frontend.
    pause
    exit /b 1
)

:: Redirect npm cache to project drive to prevent ENOSPC if drive C is full
set "npm_config_cache=%~dp0.npm-cache"

:: Ensure node_modules exists
if not exist "%~dp0node_modules" (
    echo [INFO] node_modules not found. Installing frontend dependencies...
    call npm install --cache "%~dp0.npm-cache"
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
)

:: Detect local network IPv4 address
set "LOCAL_IP=127.0.0.1"
for /f "delims=" %%i in ('%PYTHON_CMD% -c "import socket; print(socket.gethostbyname(socket.gethostname()))" 2^>nul') do (
    set "LOCAL_IP=%%i"
)

:: Ensure ports 8000 and 5173 are free from any previous orphan processes
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":8000[ ]" ^| findstr LISTENING') do (
    if not "%%a"=="0" if not "%%a"=="4" (
        echo Freeing port 8000 from previous process PID %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":5173[ ]" ^| findstr LISTENING') do (
    if not "%%a"=="0" if not "%%a"=="4" (
        echo Freeing port 5173 from previous process PID %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)
echo.

echo [1/3] Starting Backend Engine (FastAPI) on 0.0.0.0:8000 ...
start "Strata Engine - Backend (FastAPI :8000)" cmd /k "title Strata Engine - Backend (FastAPI :8000) && cd /d "%~dp0sylvasearch\backend" && %PYTHON_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/3] Starting Frontend Interface (Vite React) on 0.0.0.0:5173 ...
if exist "%~dp0node_modules\vite\bin\vite.js" (
    start "Strata Interface - Frontend (Vite :5173)" cmd /k "title Strata Interface - Frontend (Vite :5173) && cd /d "%~dp0" && node "%~dp0node_modules\vite\bin\vite.js" --host 0.0.0.0 --port 5173"
) else (
    start "Strata Interface - Frontend (Vite :5173)" cmd /k "title Strata Interface - Frontend (Vite :5173) && cd /d "%~dp0" && npm run dev -- --host 0.0.0.0 --port 5173"
)

echo [3/3] Waiting for servers to initialize...
ping 127.0.0.1 -n 4 >nul 2>&1

echo Opening browser at http://localhost:5173 ...
start http://localhost:5173

echo.
echo ========================================================
echo   Services are running!
echo.
echo   Local Access:
echo     - Frontend: http://localhost:5173
echo     - Backend:  http://localhost:8000
echo     - Swagger:  http://localhost:8000/docs
echo.
echo   Network Access (Any device on your Wi-Fi / LAN):
echo     - Frontend: http://%LOCAL_IP%:5173
echo     - Backend:  http://%LOCAL_IP%:8000
echo     - Swagger:  http://%LOCAL_IP%:8000/docs
echo ========================================================
echo   Keep the two terminal windows open while working.
echo.
pause
