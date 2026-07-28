@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=py"
)
%PYTHON% -m pip install --upgrade pyinstaller
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name "值班回复助手_v6" duty_assistant.py
echo.
echo EXE 已生成到 dist 文件夹。
pause
