@echo off
:: ============================================================
::  AttendX Activity Agent — Windows Launcher
::  STEP 1: Edit SERVER_URL and EMPLOYEE_ID below
::  STEP 2: Put this .bat file next to activity_agent.py
::  STEP 3: Double-click this file to start
:: ============================================================

set SERVER_URL=http://192.168.29.20:8000
set EMPLOYEE_ID=EMP0001

title AttendX Activity Agent — %EMPLOYEE_ID%

echo ============================================
echo   AttendX Activity Agent
echo ============================================
echo   Server   : %SERVER_URL%
echo   Employee : %EMPLOYEE_ID%
echo ============================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Install required packages if missing
echo Checking dependencies...
pip show pynput >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing pynput...
    pip install pynput
)
pip show psutil >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing psutil...
    pip install psutil
)
pip show requests >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing requests...
    pip install requests
)

echo.
echo All dependencies ready.
echo Starting agent... Press Ctrl+C to stop.
echo.

python activity_agent.py --server %SERVER_URL% --employee %EMPLOYEE_ID%

echo.
echo Agent stopped.
pause
