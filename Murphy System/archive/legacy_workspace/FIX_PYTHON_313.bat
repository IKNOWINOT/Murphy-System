@echo off
echo ============================================================
echo FIX FOR PYTHON 3.13 - Installing aiohttp without compiler
echo ============================================================
echo.

echo Your Python version:
python --version

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing aiohttp with pre-built wheel...
python -m pip install --only-binary :all: aiohttp

echo.
echo If that failed, trying alternative method...
python -m pip install aiohttp --prefer-binary

echo.
echo Verifying installation...
python -c "import aiohttp; print('SUCCESS: aiohttp version', aiohttp.__version__)" 2>nul

if errorlevel 1 (
    echo.
    echo ============================================================
    echo AIOHTTP STILL FAILED - Using alternative Groq client
    echo ============================================================
    echo.
    echo Installing official Groq SDK instead...
    python -m pip install groq
    echo.
    echo You'll need to use the official Groq client instead of groq_client.py
)

echo.
pause