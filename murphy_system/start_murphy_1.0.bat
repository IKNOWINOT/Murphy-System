@echo off
REM Murphy System 1.0 - Startup Script (Windows)
REM Copyright (C) 2020 Inoni Limited Liability Company
REM Creator: Corey Post
REM License: BSL 1.1 (Business Source License)

echo ================================================================================
echo                        MURPHY SYSTEM 1.0 - STARTUP
echo ================================================================================
echo.

REM Check Python version
echo Checking Python version...
python --version 2>nul
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.11 or higher.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION%
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Virtual environment not found. Creating...
    python -m venv venv
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Install/update dependencies
echo Installing dependencies...
python -m pip install --upgrade pip --quiet
echo Installing Murphy System requirements...
pip install -r requirements_murphy_1.0.txt 2>nul
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed to install.
    echo [INFO] Attempting to install core dependencies...
    pip install fastapi uvicorn pydantic aiohttp httpx --quiet
    echo [OK] Core dependencies installed
) else (
    echo [OK] Dependencies installed
)
echo.

REM Check environment variables
echo Checking environment variables...
if exist ".env" (
    echo [OK] .env file found
    for /f "usebackq tokens=*" %%a in (".env") do set %%a
) else (
    echo [WARNING] .env file not found. Using defaults.
)

REM Set default port if not set
if defined PORT (set MURPHY_PORT=%PORT%) else (if not defined MURPHY_PORT set MURPHY_PORT=8000)
echo [OK] Port: %MURPHY_PORT%
echo.

REM Create necessary directories
echo Creating directories...
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "modules" mkdir modules
if not exist "sessions" mkdir sessions
if not exist "repositories" mkdir repositories
echo [OK] Directories created
echo.

REM Start Murphy System
echo ================================================================================
echo                    STARTING MURPHY SYSTEM 1.0
echo ================================================================================
echo.
echo Starting Murphy System on port %MURPHY_PORT%...
echo API Documentation: http://localhost:%MURPHY_PORT%/docs
echo Health Check: http://localhost:%MURPHY_PORT%/api/health
echo System Status: http://localhost:%MURPHY_PORT%/api/status
echo System Info: http://localhost:%MURPHY_PORT%/api/info
echo.
echo Press Ctrl+C to stop
echo.

REM Run Murphy
python murphy_system_1.0_runtime.py

pause