@echo off
title P03 - Delivery Agent System (CS311 SE Lab)
color 0b

echo ======================================================================
echo    P03: DELIVERY AGENT SYSTEM - LIGHTWEIGHT PROTOTYPE
echo    CS311 Software Engineering Lab - IIIT Bhagalpur
echo ======================================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH! Please ensure Python is installed.
    pause
    exit /b 1
)

echo [1/3] Python environment detected.
echo [2/3] Checking dependencies...
python -m pip install -r "%~dp0requirements.txt" --quiet

echo [3/3] Initializing database and starting server...
echo.
echo ======================================================================
echo    The web application is launching at: http://127.0.0.1:5000
echo    Press Ctrl+C in this window to stop the server anytime.
echo ======================================================================
echo.

:: Automatically launch default web browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5000"

:: Start the Flask app
python "%~dp0app.py"

pause
