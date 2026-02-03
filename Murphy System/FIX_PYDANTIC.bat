@echo off
echo ============================================================
echo FIX CORRUPTED PYDANTIC INSTALLATION
echo ============================================================
echo.

echo Checking Python version...
python --version

echo.
echo Activating virtual environment...
if exist murphy_venv\Scripts\activate.bat (
    call murphy_venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo No virtual environment found, using system Python
)

echo.
echo Uninstalling pydantic and pydantic-core...
pip uninstall -y pydantic pydantic-core

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing pydantic fresh...
pip install pydantic==2.5.0

echo.
echo Verifying installation...
python -c "import pydantic; print('SUCCESS: pydantic version', pydantic.__version__)"

echo.
echo ============================================================
echo If you see SUCCESS above, restart the server!
echo ============================================================
pause