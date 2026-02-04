@echo off
REM Start Murphy System

if exist murphy_venv\Scripts\activate.bat (
    call murphy_venv\Scripts\activate.bat
)

echo Starting Murphy System...
python murphy_complete_integrated.py
pause