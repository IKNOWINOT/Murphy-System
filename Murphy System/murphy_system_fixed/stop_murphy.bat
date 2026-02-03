@echo off
REM Stop Murphy System
echo Stopping Murphy System...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq murphy*"
echo Murphy stopped.
pause