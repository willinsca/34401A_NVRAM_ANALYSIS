@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 -m pip install --user --upgrade pyserial
    if %ERRORLEVEL% NEQ 0 goto error
    echo.
    echo pyserial was installed or updated successfully.
    pause
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python -m pip install --user --upgrade pyserial
    if %ERRORLEVEL% NEQ 0 goto error
    echo.
    echo pyserial was installed or updated successfully.
    pause
    exit /b 0
)

:error
echo Python 3 was not found or pyserial could not be installed.
echo Install Python 3.9+ first, then run this file again.
pause
exit /b 1
