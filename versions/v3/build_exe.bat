@echo off
cd /d "%~dp0"
set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
echo Installing PyInstaller...
%PYTHON_CMD% -m pip install --upgrade pyinstaller
if errorlevel 1 goto error

echo Building EXE...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name "值班回复助手" duty_assistant.py
if errorlevel 1 goto error

echo.
echo Build completed: dist\值班回复助手.exe
pause
exit /b 0

:error
echo.
echo Build failed. Please check that Python is installed and added to PATH.
pause
exit /b 1
