@echo off
setlocal
cd /d "%~dp0"

set "TARGET=%~1"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    if "%TARGET%"=="" (
        py -3 34401A_NVRAM_Viewer_EN.pyw
    ) else (
        py -3 34401A_NVRAM_Viewer_EN.pyw "%TARGET%"
    )
    exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    if "%TARGET%"=="" (
        python 34401A_NVRAM_Viewer_EN.pyw
    ) else (
        python 34401A_NVRAM_Viewer_EN.pyw "%TARGET%"
    )
    exit /b %ERRORLEVEL%
)

echo Python 3 was not found.
echo Install Python 3.9 or newer, then run this file again.
pause
