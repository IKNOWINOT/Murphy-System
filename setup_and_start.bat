@echo off
REM ============================================================================
REM Murphy System - One-Step Setup and Start (Windows)
REM
REM Usage (from repo root):
REM   setup_and_start.bat
REM
REM Copyright (c) 2020 Inoni Limited Liability Company
REM Creator: Corey Post | License: BSL 1.1
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ================================================================
echo          Murphy System - Setup and Start
echo              One-Step Install and Launch
echo ================================================================
echo.

REM ---- locate repo root ----------------------------------------------------
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if exist "%SCRIPT_DIR%\murphy_system_1.0_runtime.py" (
    set "REPO_ROOT=%SCRIPT_DIR%"
) else (
    echo [ERROR] Cannot locate Murphy System files.
    echo         Run this script from the repository root.
    pause
    exit /b 1
)

set "MURPHY_DIR=%REPO_ROOT%"

if not exist "%MURPHY_DIR%\murphy_system_1.0_runtime.py" (
    echo [ERROR] murphy_system_1.0_runtime.py not found.
    echo         Please run from the Murphy-System repository root.
    pause
    exit /b 1
)

echo [INFO] Repository root: %REPO_ROOT%
echo.

REM ---- step 1: prerequisites -----------------------------------------------
echo [1/5] Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org/downloads
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION%
echo.

REM ---- step 2: virtual environment -----------------------------------------
echo [2/5] Setting up Python virtual environment...

set "VENV_DIR=%MURPHY_DIR%\venv"

if exist "%VENV_DIR%" (
    echo [INFO] Reusing existing virtual environment
) else (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] venv activation failed.
    pause
    exit /b 1
)
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] venv activation failed - pip not found in venv.
    pause
    exit /b 1
)
python -m pip install --upgrade pip -q >nul 2>&1
echo [OK] Virtual environment ready and activated
echo.

REM ---- step 3: install dependencies ----------------------------------------
echo [3/5] Installing all dependencies (this may take 1-3 minutes)...

cd /d "%MURPHY_DIR%"

if exist "requirements_murphy_1.0.txt" (
    echo [INFO] Installing from requirements_murphy_1.0.txt...
    pip install -q -r requirements_murphy_1.0.txt 2>nul
    if errorlevel 1 (
        echo [WARNING] Some optional dependencies may have failed.
        echo [INFO] Installing core dependencies...
        pip install -q fastapi uvicorn pydantic aiohttp httpx rich textual pyyaml python-dotenv requests 2>nul
    )
)

if exist "requirements.txt" (
    pip install -q -r requirements.txt 2>nul
)

REM Ensure extras that users commonly need
pip install -q watchdog matplotlib 2>nul

echo [OK] All dependencies installed
REM NOTE: pip may report dependency conflicts for optional packages (e.g. weasyprint/tinycss2).
REM These are non-fatal — Murphy falls back to alternative renderers automatically.
echo.

REM ---- step 4: configuration -----------------------------------------------
echo [4/5] Configuring Murphy...

if not defined MURPHY_PORT set MURPHY_PORT=8000

if not exist "%MURPHY_DIR%\.env" (
    (
        echo # Murphy System 1.0 - Auto-generated
        echo MURPHY_VERSION=1.0.0
        echo MURPHY_ENV=development
        echo MURPHY_PORT=%MURPHY_PORT%
        echo.
        echo # LLM provider - set to groq, openai, or anthropic once you add a key below
        echo # Defaults to local ^(onboard LLM, no API key required^)
        echo MURPHY_LLM_PROVIDER=local
        echo.
        echo # The onboard LLM works without any API key.
        echo # Add an external key below for enhanced quality ^(optional^).
        echo # GROQ_API_KEY=gsk_your_key_here
    ) > "%MURPHY_DIR%\.env"
    echo [OK] Created default .env (onboard LLM active - no key required)
) else (
    echo [OK] .env already exists - keeping your configuration
)

REM Create runtime directories
if not exist "%MURPHY_DIR%\logs" mkdir "%MURPHY_DIR%\logs"
if not exist "%MURPHY_DIR%\data" mkdir "%MURPHY_DIR%\data"
if not exist "%MURPHY_DIR%\modules" mkdir "%MURPHY_DIR%\modules"
if not exist "%MURPHY_DIR%\sessions" mkdir "%MURPHY_DIR%\sessions"
if not exist "%MURPHY_DIR%\repositories" mkdir "%MURPHY_DIR%\repositories"
echo [OK] Runtime directories ready
echo.

REM ---- step 5: launch ------------------------------------------------------
echo [5/5] Ready to start Murphy System
echo.
echo ================================================================
echo   [OK] All requirements installed
echo   [OK] Virtual environment activated
echo   [OK] Configuration ready
echo   [OK] Ready to run!
echo ================================================================
echo.
echo   API Docs:    http://localhost:%MURPHY_PORT%/docs
echo   Health:      http://localhost:%MURPHY_PORT%/api/health
echo   Status:      http://localhost:%MURPHY_PORT%/api/status
echo.
echo   Unified Terminal (Admin / Multi-role hub): %MURPHY_DIR%\terminal_unified.html
echo.

REM Determine primary terminal path (fall back to Architect Terminal if Unified is absent)
set TERMINAL_FILE=%MURPHY_DIR%\terminal_unified.html
if not exist "%TERMINAL_FILE%" set TERMINAL_FILE=%MURPHY_DIR%\terminal_architect.html

REM Offer choice: backend server vs terminal UI
if exist "%MURPHY_DIR%\murphy_terminal.py" (
    echo How would you like to start Murphy?
    echo   1^) Start backend server  (API + all web dashboards in browser)
    echo   2^) Start terminal UI     (interactive natural-language terminal in shell)
    echo.
    set /p LAUNCH_CHOICE="Enter choice [1]: "
    if "!LAUNCH_CHOICE!"=="" set LAUNCH_CHOICE=1
) else (
    set LAUNCH_CHOICE=1
)

echo.
cd /d "%MURPHY_DIR%"

if "!LAUNCH_CHOICE!"=="2" (
    echo Starting Murphy Terminal UI...
    echo Press Ctrl+C to stop
    echo.
    python murphy_terminal.py
) else (
    echo Starting Murphy System backend on port %MURPHY_PORT%...
    echo Open the Unified Terminal (Admin / Multi-role hub) in your browser:
    echo   %TERMINAL_FILE%
    echo Other web interfaces (role-specific terminals, canvas, visualiser, etc.):
    echo   %MURPHY_DIR%\murphy_landing_page.html
    echo   %MURPHY_DIR%\terminal_architect.html
    echo   http://localhost:%MURPHY_PORT%/docs  (Swagger API docs)
    echo Press Ctrl+C to stop
    echo.
    REM Start backend in foreground — health check prompt is printed before launch
    REM (CMD has no reliable background+wait; backend runs until user presses Ctrl+C)
    python murphy_system_1.0_runtime.py
)

pause
