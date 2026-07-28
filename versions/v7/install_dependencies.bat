@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
  py -m pip install -r requirements.txt
)
echo.
echo 安装完成。以后双击“启动助手.vbs”即可无黑框运行。
pause
