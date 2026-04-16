@echo off
REM ============================================================================
REM Murphy System — ONE-BUTTON RUN (Windows)
REM
REM Usage:  double-click run.bat   OR   run.bat   in Command Prompt
REM
REM Copyright (c) 2020 Inoni Limited Liability Company
REM Creator: Corey Post | License: BSL 1.1
REM ============================================================================

echo.
echo ================================================================
echo   Murphy System -- One-Button Run
echo ================================================================
echo.

REM ---- Check Python ----------------------------------------------------------
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10+ is required. Install from https://python.org/downloads
    pause
    exit /b 1
)

python --version 2>&1 | findstr /R "3\.1[0-9] 3\.[2-9][0-9]" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Python 3.10+ is recommended. You may encounter issues with an older version.
)
echo [OK] Python found

REM ---- Virtual environment ---------------------------------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [OK] Virtual environment active

REM ---- Install dependencies --------------------------------------------------
echo [INFO] Installing core dependencies...
pip install --upgrade pip -q 2>nul
pip install -q -r requirements_core.txt 2>nul
pip install -q bcrypt python-multipart 2>nul
echo [OK] Dependencies installed

REM ---- .env ------------------------------------------------------------------
if not exist ".env" (
    echo # Murphy System -- Auto-generated .env for development> .env
    echo MURPHY_VERSION=1.0.0>> .env
    echo MURPHY_ENV=development>> .env
    echo MURPHY_PORT=8000>> .env
    echo MURPHY_LLM_PROVIDER=local>> .env
    echo LOG_LEVEL=INFO>> .env
    echo [OK] Created .env (development mode)
) else (
    echo [OK] .env exists
)

REM ---- Create directories ----------------------------------------------------
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist ".murphy_persistence" mkdir .murphy_persistence

REM ---- Launch ----------------------------------------------------------------
echo.
echo ================================================================
echo   Ready! Starting Murphy System on port 8000
echo ================================================================
echo.
echo   Landing Page:  http://localhost:8000/
echo   Forge Demo:    http://localhost:8000/landing  (scroll to "Build Something")
echo   API Docs:      http://localhost:8000/docs  (Swagger interactive docs)
echo.
echo   To test the deliverable forge:
echo     1. Open http://localhost:8000/ in your browser
echo     2. Scroll to the "Build Something" / forge section
echo     3. Type: create a compliance automation plan
echo     4. Click Build and watch the agent swarm
echo     5. Download the generated deliverable
echo.
echo   Press Ctrl+C to stop
echo.

REM Open browser after short delay
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000/"

python murphy_production_server.py
