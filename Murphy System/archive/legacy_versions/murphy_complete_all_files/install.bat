@echo off
REM Murphy System - Windows Installation Script

echo ============================================================
echo Murphy System - Installation Script (Windows)
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM Check if pip is installed
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not installed
    echo Installing pip...
    python -m ensurepip --upgrade
)

echo [OK] pip found

REM Ask about virtual environment
echo.
set /p CREATE_VENV="Create virtual environment? (recommended) [Y/n]: "
if "%CREATE_VENV%"=="" set CREATE_VENV=Y

if /i "%CREATE_VENV%"=="Y" (
    echo Creating virtual environment...
    python -m venv murphy_venv
    call murphy_venv\Scripts\activate.bat
    echo [OK] Virtual environment created and activated
)

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing Python dependencies...
echo Installing core packages...
pip install flask==3.0.0
pip install flask-cors==4.0.0
pip install flask-socketio==5.3.5
pip install python-socketio==5.10.0
pip install groq==0.4.1
pip install requests==2.31.0
pip install aiohttp==3.9.1
pip install psutil==5.9.6
pip install "pydantic>=2.5.0"

echo Installing asyncio fix...
pip install nest-asyncio==1.5.8

echo Installing optional packages...
pip install python-dotenv==1.0.0

echo [OK] All dependencies installed

REM Check for API keys
echo.
echo ============================================================
echo API Keys Setup
echo ============================================================

if not exist groq_keys.txt (
    echo [WARNING] groq_keys.txt not found
    echo Creating groq_keys.txt...
    (
        echo # Add your Groq API keys here (one per line^)
        echo # Get free keys at: https://console.groq.com/keys
        echo # Example:
        echo # REDACTED_GROQ_KEY_PLACEHOLDER
    ) > groq_keys.txt
    echo [WARNING] Please add your Groq API keys to groq_keys.txt
) else (
    echo [OK] groq_keys.txt found
)

if not exist aristotle_key.txt (
    echo Creating aristotle_key.txt (optional^)...
    echo # Add your Aristotle API key here (optional^) > aristotle_key.txt
)

REM Create .env file
echo.
echo Creating .env file...
if not exist .env (
    (
        echo # Murphy System Configuration
        echo FLASK_ENV=development
        echo FLASK_DEBUG=False
        echo SECRET_KEY=your-secret-key-change-this
        echo DATABASE_URL=sqlite:///murphy.db
        echo PORT=3002
        echo HOST=0.0.0.0
    ) > .env
    echo [OK] .env file created
) else (
    echo [WARNING] .env file already exists, skipping
)

REM Create startup script
echo.
echo Creating startup script...
(
    echo @echo off
    echo REM Start Murphy System
    echo.
    echo if exist murphy_venv\Scripts\activate.bat (
    echo     call murphy_venv\Scripts\activate.bat
    echo ^)
    echo.
    echo echo Starting Murphy System...
    echo python murphy_complete_integrated.py
    echo pause
) > start_murphy.bat

echo [OK] Startup script created (start_murphy.bat^)

REM Create stop script
(
    echo @echo off
    echo REM Stop Murphy System
    echo echo Stopping Murphy System...
    echo taskkill /F /IM python.exe /FI "WINDOWTITLE eq murphy*"
    echo echo Murphy stopped.
    echo pause
) > stop_murphy.bat

echo [OK] Stop script created (stop_murphy.bat^)

REM Final instructions
echo.
echo ============================================================
echo Installation Complete!
echo ============================================================
echo.
echo Next steps:
echo.
echo 1. Add your Groq API keys to groq_keys.txt
echo    Get free keys at: https://console.groq.com/keys
echo.
echo 2. Start Murphy:
echo    start_murphy.bat
echo.
echo 3. Access Murphy:
echo    Dashboard: http://localhost:3002
echo    API: http://localhost:3002/api/status
echo.
echo 4. Stop Murphy:
echo    stop_murphy.bat
echo.
echo 5. Run tests:
echo    python real_test.py
echo.
echo ============================================================
echo.

if /i "%CREATE_VENV%"=="Y" (
    echo Note: Virtual environment is activated.
    echo To deactivate: deactivate
    echo To reactivate: murphy_venv\Scripts\activate.bat
    echo.
)

echo Happy automating! 🚀
echo.
pause