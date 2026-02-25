@echo off
echo ============================================================
echo MANUAL FIX - Installing aiohttp
echo ============================================================
echo.

echo Current directory:
cd

echo.
echo Installing aiohttp...
python -m pip install aiohttp==3.9.1

echo.
echo Installing nest-asyncio...
python -m pip install nest-asyncio==1.5.8

echo.
echo Verifying installation...
python -c "import aiohttp; print('SUCCESS: aiohttp version', aiohttp.__version__)"

echo.
echo ============================================================
echo If you see SUCCESS above, restart the server!
echo ============================================================
pause