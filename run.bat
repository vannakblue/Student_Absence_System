@echo off
setlocal
cd /d "%~dp0"
title Student and Teacher Absence Management System
color 0b

echo =========================================================================
echo   Student and Teacher Absence Management System (SchoolSM)
echo   Database: SQLite (attendance.db)
echo =========================================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 goto :NO_PYTHON

echo Starting Application Server on http://localhost:5000...
echo Web browser will open automatically in a moment.
echo Press Ctrl+C in this window to stop the server anytime.
echo -------------------------------------------------------------------------

python run.py
goto :END

:NO_PYTHON
echo [ERROR] Python is not installed or not in PATH!
echo Please install Python from https://www.python.org/
pause

:END
pause
