@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 -m pip install --upgrade pyinstaller
    py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name 34401A_NVRAM_Viewer_EN 34401A_NVRAM_Viewer_EN.pyw
    echo.
    echo Done. Check the dist folder for 34401A_NVRAM_Viewer_EN.exe
    pause
    exit /b
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python -m pip install --upgrade pyinstaller
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name 34401A_NVRAM_Viewer_EN 34401A_NVRAM_Viewer_EN.pyw
    echo.
    echo Done. Check the dist folder for 34401A_NVRAM_Viewer_EN.exe
    pause
    exit /b
)

echo Python 3 was not found.
echo Install Python 3.9 or newer, then run this file again.
pause
