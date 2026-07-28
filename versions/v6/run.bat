@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" duty_assistant.py
) else (
  py duty_assistant.py
)
if errorlevel 1 pause
