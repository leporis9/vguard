@echo off
REM ==============================================================
REM Local Startup Script (Windows)
REM Starts SSH tunnel to remote server, then launches frontend
REM ==============================================================
setlocal enabledelayedexpansion

echo ========================================
echo  VGuard Frontend — Local Startup
echo ========================================

REM ---- Config ----
set LOCAL_PORT=8089
set FRONTEND_PORT=5173

REM ---- SSH Tunnel ----
echo.
echo Starting SSH tunnel: localhost:%LOCAL_PORT% -^> vguard_prod
start "VGuard SSH Tunnel" ssh -L %LOCAL_PORT%:localhost:8000 vguard_prod -N -f

REM Wait for tunnel
echo Waiting for SSH tunnel...
timeout /t 3 /nobreak >nul

REM ---- Check backend ----
echo.
echo Checking backend connectivity...
curl -s http://localhost:%LOCAL_PORT%/api/v1/health >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Backend not reachable. Make sure deploy-remote.sh is running on server.
) else (
    echo Backend is reachable.
)

REM ---- Start frontend ----
echo.
echo Starting frontend dev server on port %FRONTEND_PORT%...
cd /d "%~dp0frontend"
call npm run dev

echo.
echo Frontend stopped. You can close the SSH tunnel window.
pause
