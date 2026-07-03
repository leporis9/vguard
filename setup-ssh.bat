@echo off
REM ==============================================================
REM VGuard SSH Setup - Install key and configure SSH
REM ==============================================================
setlocal enabledelayedexpansion

echo ========================================
echo  VGuard SSH Setup
echo ========================================

set SSH_DIR=%USERPROFILE%\.ssh
set KEY_FILE=vguard_rsa

if not exist ".\%KEY_FILE%" (
    echo ERROR: vguard_rsa not found in current directory
    echo Please place the key file from admin in the project folder and retry.
    pause
    exit /b 1
)

if not exist "%SSH_DIR%" mkdir "%SSH_DIR%"

copy /Y ".\%KEY_FILE%" "%SSH_DIR%\%KEY_FILE%" >nul 2>&1
echo Key installed to %SSH_DIR%\%KEY_FILE%

findstr /C:"Host vguard_prod" "%SSH_DIR%\config" >nul 2>&1
if %errorlevel% neq 0 (
    echo. >> "%SSH_DIR%\config"
    echo Host vguard_prod >> "%SSH_DIR%\config"
    echo     HostName 10.204.111.54 >> "%SSH_DIR%\config"
    echo     User gxy >> "%SSH_DIR%\config"
    echo     Port 9002 >> "%SSH_DIR%\config"
    echo     IdentityFile %SSH_DIR:\=/%/%KEY_FILE% >> "%SSH_DIR%\config"
    echo     ServerAliveInterval 60 >> "%SSH_DIR%\config"
    echo SSH config added
)

echo.
echo ========================================
echo  Setup complete. Run start-local.bat
echo ========================================
pause
