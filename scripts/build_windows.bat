@echo off
setlocal
call "%~dp0..\run.bat" --build %*
exit /b %errorlevel%
