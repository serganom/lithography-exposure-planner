@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\bootstrap.py %*
) else (
    py -3.12 scripts\bootstrap.py %*
)
if errorlevel 1 goto :error
exit /b 0

:error
echo The application could not start. Install Python 3.12 x64 and check docs\CROSS_PLATFORM.md.
echo Building gdspy from source requires Visual Studio Build Tools with C++ and a Windows SDK.
pause
exit /b 1
