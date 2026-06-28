@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 34401A_NVRAM_Viewer.pyw
    exit /b %ERRORLEVEL%
)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python 34401A_NVRAM_Viewer.pyw
    exit /b %ERRORLEVEL%
)
echo Python 3 was not found.
echo Install Python 3.9+ from python.org, then run this file again.
pause
