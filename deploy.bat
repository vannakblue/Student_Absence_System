@echo off
chcp 65001 >nul
title Deploy KKHS Student Absence System to Firebase Hosting
cd /d "%~dp0"

echo ============================================================
echo   🚀 កំពុងដំណើរការ Deploy KKHS Student Absence System...
echo ============================================================
echo.

echo [1/2] ធ្វើបច្ចុប្បន្នភាពទិន្នន័យ (Sync Data to Firebase RTDB)...
python sync_to_firebase.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Sync ទិន្នន័យមានបញ្ហា ប៉ុន្តែនឹងបន្ត Deploy Frontend...
)
echo.

echo [2/2] Deploying Frontend to Firebase Hosting (https://school-timetable-67972.web.app)...
call firebase deploy --only hosting
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] ការ Deploy ទៅកាន់ Firebase Hosting បរាជ័យ!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   🎉 DEPLOY TO FIREBASE HOSTING COMPLETED SUCCESSFULLY!
echo   🌐 Live URL: https://school-timetable-67972.web.app
echo ============================================================
echo.
start https://school-timetable-67972.web.app
pause
