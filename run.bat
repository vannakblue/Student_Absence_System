@echo off
setlocal
cd /d "%~dp0"
title Student and Teacher Absence Management System
chcp 65001 >nul 2>&1

echo ========================================================================
echo   Student and Teacher Absence Management System (SchoolSM)
echo   Local Web Server and Browser Runner
echo ========================================================================
echo.

set PYTHON_CMD=

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

if exist "venv\Scripts\python.exe" (
    set "PYTHON_CMD=venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
    goto :PYTHON_FOUND
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py"
    goto :PYTHON_FOUND
)

echo [ERROR] Python is not installed or not found in system PATH!
echo Please download and install Python 3 from https://www.python.org/
echo Make sure to check the box "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:PYTHON_FOUND
echo [*] Using Python: %PYTHON_CMD%

%PYTHON_CMD% -c "import flask" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [*] Installing required packages from requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo [*] Starting web server and opening default browser...
echo.

%PYTHON_CMD% run.py %*
set RUN_STATUS=%ERRORLEVEL%

if %RUN_STATUS% neq 0 (
    echo.
    echo [ERROR] Server terminated with error code %RUN_STATUS%!
    pause
)

exit /b %RUN_STATUS%
