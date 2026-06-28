@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 -m pip install --user --upgrade pyserial pyinstaller
    if %ERRORLEVEL% NEQ 0 goto error
    py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name 34401A_NVRAM_Viewer_v0.11_EN --collect-submodules serial 34401A_NVRAM_Viewer_EN.pyw
    if %ERRORLEVEL% NEQ 0 goto error
    echo.
    echo Done. Check the dist folder for 34401A_NVRAM_Viewer_v0.11_EN.exe
    pause
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python -m pip install --user --upgrade pyserial pyinstaller
    if %ERRORLEVEL% NEQ 0 goto error
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name 34401A_NVRAM_Viewer_v0.11_EN --collect-submodules serial 34401A_NVRAM_Viewer_EN.pyw
    if %ERRORLEVEL% NEQ 0 goto error
    echo.
    echo Done. Check the dist folder for 34401A_NVRAM_Viewer_v0.11_EN.exe
    pause
    exit /b 0
)

:error
echo Python 3 was not found or the build failed.
pause
exit /b 1
