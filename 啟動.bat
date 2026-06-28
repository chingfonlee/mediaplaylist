@echo off
cd /d "%~dp0"

python launcher.py
if %errorlevel%==0 goto end

py launcher.py
if %errorlevel%==0 goto end

echo.
echo  ERROR: Python not found.
echo  Please install Python from https://www.python.org/
echo  Make sure to check "Add Python to PATH" during install.
echo.
pause

:end
