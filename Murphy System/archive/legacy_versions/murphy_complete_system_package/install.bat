@echo off
REM Murphy System Installation Script
REM Copyright (C) 2020 Inoni Limited Liability Company. All rights reserved.
REM Created by: Corey Post

echo ==========================================
echo Murphy System Installation
echo Copyright (C) 2020 Inoni Limited Liability Company
echo Created by: Corey Post
echo ==========================================

REM Check Python version
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ==========================================
echo Installation Complete!
echo ==========================================
echo.
echo To start the Murphy Runtime System:
echo   1. Activate virtual environment: venv\Scripts\activate.bat
echo   2. Run: python murphy_runtime\murphy_complete_integrated.py
echo.
echo To use Phase 1-5 implementations:
echo   1. Activate virtual environment: venv\Scripts\activate.bat
echo   2. Run: python -m murphy_implementation.main
echo.
pause
