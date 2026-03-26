@echo off
REM Murphy System 1.0 - Quick Setup Script (Windows)
REM This script sets up Murphy System for first-time use
REM Copyright (c) 2020 Inoni Limited Liability Company
REM Creator: Corey Post
REM License: BSL 1.1 (Business Source License)

echo ================================================================================
echo                    MURPHY SYSTEM 1.0 - QUICK SETUP
echo ================================================================================
echo.

REM Step 1: Check Python version
echo Step 1/5: Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% detected
echo.

REM Step 2: Create virtual environment
echo Step 2/5: Setting up virtual environment...
if exist "venv" (
    echo [WARNING] Virtual environment already exists
    set /p RECREATE="Do you want to recreate it? (y/N): "
    if /i "%RECREATE%"=="y" (
        rmdir /s /q venv
        python -m venv venv
        echo [OK] Virtual environment recreated
    ) else (
        echo [INFO] Using existing virtual environment
    )
) else (
    python -m venv venv
    echo [OK] Virtual environment created
)
echo.

REM Step 3: Activate and install dependencies
echo Step 3/5: Installing dependencies...
call venv\Scripts\activate.bat

echo   Upgrading pip...
python -m pip install --upgrade pip -q

echo   Installing Murphy dependencies (this may take 2-3 minutes)...
pip install -r requirements_murphy_1.0.txt -q

echo [OK] Dependencies installed
echo.

REM Step 4: Create .env file
echo Step 4/5: Creating configuration file...

if exist ".env" (
    echo [WARNING] .env file already exists
    set /p OVERWRITE="Do you want to overwrite it? (y/N): "
    if not "%OVERWRITE%"=="y" (
        echo [INFO] Keeping existing .env file
        set SKIP_ENV=true
    )
)

if not "%SKIP_ENV%"=="true" (
    echo.
    echo To use Murphy, you need at least one LLM API key.
    echo Recommended: DeepInfra (primary) or Together AI (overflow^)
    echo.
    echo Get a DeepInfra API key at: https://deepinfra.com/
    echo Get a Together AI API key at: https://api.together.xyz/
    echo.
    set /p DEEPINFRA_KEY="Enter your DeepInfra API key (or press Enter to skip): "
    if "%DEEPINFRA_KEY%"=="" (
        set /p TOGETHER_KEY="Enter your Together AI API key (or press Enter to skip): "
    )
    echo.
    
    REM Create .env file
    (
        echo # Murphy System 1.0 - Configuration
        echo # Auto-generated on %date% %time%
        echo.
        echo # Core Configuration
        echo MURPHY_VERSION=1.0.0
        echo MURPHY_ENV=development
        echo MURPHY_PORT=8000
        echo.
        echo # LLM API Keys
    ) > .env
    
    if not "%DEEPINFRA_KEY%"=="" (
        echo DEEPINFRA_API_KEY=%DEEPINFRA_KEY% >> .env
        echo [OK] Configuration file created with DeepInfra API key
    ) else if not "%TOGETHER_KEY%"=="" (
        echo TOGETHER_API_KEY=%TOGETHER_KEY% >> .env
        echo [OK] Configuration file created with Together AI API key
    ) else (
        echo # DEEPINFRA_API_KEY=your_key_here >> .env
        echo # TOGETHER_API_KEY=your_key_here >> .env
        echo [WARNING] Configuration file created without API key
        echo [WARNING] You'll need to add DEEPINFRA_API_KEY to .env before starting Murphy
    )
    
    (
        echo.
        echo # Database (SQLite auto-created if not specified^)
        echo # DATABASE_URL=postgresql://user:pass@localhost:5432/murphy
        echo.
        echo # Cache (in-memory cache if not specified^)
        echo # REDIS_URL=redis://localhost:6379/0
        echo.
        echo # Security (auto-generated if not provided^)
        echo # JWT_SECRET=
        echo # ENCRYPTION_KEY=
        echo.
        echo # See .env.example for more configuration options
    ) >> .env
)

echo.

REM Step 5: Create necessary directories
echo Step 5/5: Creating directories...
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "modules" mkdir modules
if not exist "sessions" mkdir sessions
if not exist "repositories" mkdir repositories
echo [OK] Directories created
echo.

REM Final instructions
echo ================================================================================
echo                           SETUP COMPLETE!
echo ================================================================================
echo.

if "%DEEPINFRA_KEY%"=="" if "%TOGETHER_KEY%"=="" (
    echo [WARNING] IMPORTANT: You need to add an API key to .env before starting Murphy
    echo.
    echo 1. Get a DeepInfra API key: https://deepinfra.com/
    echo    Edit .env and add: DEEPINFRA_API_KEY=your_key_here
    echo    --- or ---
    echo 2. Get a Together AI API key: https://api.together.xyz/
    echo    Edit .env and add: TOGETHER_API_KEY=your_key_here
    echo 3. Save the file
    echo.
    echo Then start Murphy with:
) else (
    echo [OK] Murphy is ready to start!
    echo.
    echo Start Murphy with:
)

echo.
echo   start_murphy_1.0.bat
echo.
echo Once running, access:
echo   * API Documentation: http://localhost:8000/docs
echo   * Health Check:      http://localhost:8000/api/health
echo   * System Status:     http://localhost:8000/api/status
echo.
echo For more information:
echo   * See GETTING_STARTED.md for detailed instructions
echo   * See .env.example for all configuration options
echo   * Run demo: python scripts\quick_demo.py
echo.
echo Happy automating! 🚀
echo.

pause
