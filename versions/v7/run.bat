@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" duty_assistant.py
) else (
  start "" pyw.exe duty_assistant.py
)
