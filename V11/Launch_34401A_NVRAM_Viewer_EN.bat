@echo off
setlocal
cd /d "%~dp0"

set "TARGET=%~1"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 goto use_py
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 goto use_python

echo Python 3 was not found.
echo Install Python 3.9 or newer, then run this file again.
pause
exit /b 1

:use_py
py -3 -c "import serial" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing pyserial for the Dump Reader...
    py -3 -m pip install --user --upgrade pyserial
    if %ERRORLEVEL% NEQ 0 goto dependency_error
)
if "%TARGET%"=="" (
    py -3 34401A_NVRAM_Viewer_EN.pyw
) else (
    py -3 34401A_NVRAM_Viewer_EN.pyw "%TARGET%"
)
exit /b %ERRORLEVEL%

:use_python
python -c "import serial" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing pyserial for the Dump Reader...
    python -m pip install --user --upgrade pyserial
    if %ERRORLEVEL% NEQ 0 goto dependency_error
)
if "%TARGET%"=="" (
    python 34401A_NVRAM_Viewer_EN.pyw
) else (
    python 34401A_NVRAM_Viewer_EN.pyw "%TARGET%"
)
exit /b %ERRORLEVEL%

:dependency_error
echo Could not install pyserial. Run Install_Dependencies.bat while connected to the internet.
pause
exit /b 1
