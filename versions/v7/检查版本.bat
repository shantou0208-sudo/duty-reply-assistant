@echo off
setlocal
cd /d "%~dp0"
echo 当前文件位置：
echo %CD%\duty_assistant.py
echo.
findstr /C:"BUILD_ID" duty_assistant.py
findstr /C:"7月28日更新" duty_assistant.py
echo.
echo 正确结果应包含：
echo BUILD_ID = "2026-07-28c"
echo.
pause
