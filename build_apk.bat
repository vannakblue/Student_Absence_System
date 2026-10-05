@echo off
setlocal
cd /d "%~dp0"
title Student Absence System - Android APK Builder
chcp 65001 >nul 2>&1

echo ========================================================================
echo   Student Absence System - Android APK Builder
echo   Package Android APK File for Mobile Installation
echo ========================================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not found in system PATH!
    echo Please install Python 3 and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

echo [*] Launching APK Packaging Engine...
python build_apk.py
set BUILD_STATUS=%ERRORLEVEL%

echo.
if %BUILD_STATUS% EQU 0 (
    echo [SUCCESS] Android APK created successfully!
) else (
    echo [FAILED] Failed to create APK. Error code: %BUILD_STATUS%
)

echo.
pause
exit /b %BUILD_STATUS%
