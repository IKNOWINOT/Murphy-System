@echo off
setlocal enabledelayedexpansion
title Murphy Desktop — Installer
color 0A

echo.
echo   ============================================================
echo                MURPHY DESKTOP — INSTALLER v0.0.1
echo   ============================================================
echo.
echo   This installer will:
echo     1. Copy Murphy Desktop to %%LOCALAPPDATA%%\MurphyDesktop
echo     2. Install bundled Python runtime (no admin rights needed)
echo     3. Install required Python packages
echo     4. Create desktop and Start Menu shortcuts
echo.
echo   Press any key to begin, or close this window to cancel.
pause >nul

set INSTALL_DIR=%LOCALAPPDATA%\MurphyDesktop
set SOURCE_DIR=%~dp0

echo.
echo   [1/5] Creating install directory at %INSTALL_DIR%
if exist "%INSTALL_DIR%" (
    echo         Existing install found — preserving user data
    if exist "%INSTALL_DIR%\app" rmdir /s /q "%INSTALL_DIR%\app"
    if exist "%INSTALL_DIR%\python" rmdir /s /q "%INSTALL_DIR%\python"
)
mkdir "%INSTALL_DIR%" 2>nul
mkdir "%INSTALL_DIR%\app" 2>nul
mkdir "%INSTALL_DIR%\python" 2>nul

echo.
echo   [2/5] Installing Python runtime (one-time)
powershell -Command "Expand-Archive -Force '%SOURCE_DIR%payload\python-embed.zip' '%INSTALL_DIR%\python'"
if errorlevel 1 (
    echo         ERROR: Could not unpack Python.
    pause
    exit /b 1
)

REM Enable site-packages in embedded Python (needed for pip)
echo import site >> "%INSTALL_DIR%\python\python311._pth"
echo Lib\site-packages >> "%INSTALL_DIR%\python\python311._pth"

REM Install pip into embedded Python
echo         Installing pip...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%INSTALL_DIR%\python\get-pip.py'"
"%INSTALL_DIR%\python\python.exe" "%INSTALL_DIR%\python\get-pip.py" --no-warn-script-location --quiet
if errorlevel 1 (
    echo         ERROR: pip install failed. Check internet connection.
    pause
    exit /b 1
)

echo.
echo   [3/5] Copying Murphy Desktop files
xcopy /e /i /q /y "%SOURCE_DIR%payload\app\*" "%INSTALL_DIR%\app\" >nul
if errorlevel 1 (
    echo         ERROR: Could not copy app files.
    pause
    exit /b 1
)

echo.
echo   [4/5] Installing Python packages (requests, websocket-client, pillow)
"%INSTALL_DIR%\python\python.exe" -m pip install --no-warn-script-location --quiet -r "%INSTALL_DIR%\app\requirements.txt"
if errorlevel 1 (
    echo         ERROR: Package install failed.
    pause
    exit /b 1
)

echo.
echo   [5/5] Creating shortcuts
REM Launcher
> "%INSTALL_DIR%\MurphyDesktop.bat" (
    echo @echo off
    echo title Murphy Desktop
    echo cd /d "%INSTALL_DIR%\app"
    echo "%INSTALL_DIR%\python\python.exe" run.py
)

REM Chrome-with-debug launcher
> "%INSTALL_DIR%\Murphy-Chrome.bat" (
    echo @echo off
    echo title Chrome ^(Murphy-debuggable^)
    echo set CHROME_PATH=
    echo if exist "%%ProgramFiles%%\Google\Chrome\Application\chrome.exe" set CHROME_PATH=%%ProgramFiles%%\Google\Chrome\Application\chrome.exe
    echo if exist "%%ProgramFiles(x86^)%%\Google\Chrome\Application\chrome.exe" set CHROME_PATH=%%ProgramFiles(x86^)%%\Google\Chrome\Application\chrome.exe
    echo if "%%CHROME_PATH%%"=="" ^(echo Chrome not found ^& pause ^& exit /b 1^)
    echo start "" "%%CHROME_PATH%%" --remote-debugging-port=9222 --user-data-dir="%%USERPROFILE%%\.murphy-desktop\chrome-profile"
)

REM Uninstaller
> "%INSTALL_DIR%\Uninstall.bat" (
    echo @echo off
    echo echo Uninstalling Murphy Desktop...
    echo echo.
    echo echo This will REMOVE the app from %INSTALL_DIR%
    echo echo Your data at %%USERPROFILE%%\.murphy-desktop\ will be KEPT.
    echo echo.
    echo pause
    echo del "%%USERPROFILE%%\Desktop\Murphy Desktop.lnk" 2^>nul
    echo del "%%USERPROFILE%%\Desktop\Murphy Chrome.lnk" 2^>nul
    echo del "%%APPDATA%%\Microsoft\Windows\Start Menu\Programs\Murphy Desktop.lnk" 2^>nul
    echo timeout /t 1 /nobreak ^>nul
    echo cd /d "%%LOCALAPPDATA%%"
    echo rmdir /s /q "MurphyDesktop"
    echo echo Done.
    echo pause
)

REM Create Desktop shortcuts via PowerShell
powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Murphy Desktop.lnk'); ^
     $s.TargetPath = '%INSTALL_DIR%\MurphyDesktop.bat'; ^
     $s.WorkingDirectory = '%INSTALL_DIR%\app'; ^
     $s.IconLocation = '%INSTALL_DIR%\app\assets\logo.ico'; ^
     $s.WindowStyle = 7; ^
     $s.Save()"

powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Murphy Chrome.lnk'); ^
     $s.TargetPath = '%INSTALL_DIR%\Murphy-Chrome.bat'; ^
     $s.IconLocation = '%INSTALL_DIR%\app\assets\logo.ico'; ^
     $s.WindowStyle = 7; ^
     $s.Save()"

REM Start Menu
powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $s = $ws.CreateShortcut([Environment]::GetFolderPath('StartMenu') + '\Programs\Murphy Desktop.lnk'); ^
     $s.TargetPath = '%INSTALL_DIR%\MurphyDesktop.bat'; ^
     $s.WorkingDirectory = '%INSTALL_DIR%\app'; ^
     $s.IconLocation = '%INSTALL_DIR%\app\assets\logo.ico'; ^
     $s.WindowStyle = 7; ^
     $s.Save()"

echo.
echo   ============================================================
echo                       INSTALL COMPLETE
echo   ============================================================
echo.
echo   Murphy Desktop is installed at:
echo     %INSTALL_DIR%
echo.
echo   Shortcuts created:
echo     - Desktop: "Murphy Desktop" and "Murphy Chrome"
echo     - Start Menu: "Murphy Desktop"
echo.
echo   To launch: double-click "Murphy Desktop" on your desktop
echo.
echo   To uninstall: run %INSTALL_DIR%\Uninstall.bat
echo.
pause

REM Optionally launch right now
choice /C YN /N /M "  Launch Murphy Desktop now? [Y/N] "
if errorlevel 2 exit /b 0
start "" "%INSTALL_DIR%\MurphyDesktop.bat"
exit /b 0
