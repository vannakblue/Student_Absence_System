@echo off
setlocal
cd /d "%~dp0"
title Deploy KKHS Student Absence System to Firebase Hosting

python deploy.py
if %ERRORLEVEL% neq 0 (
    echo.
    pause
    exit /b %ERRORLEVEL%
)

pause
