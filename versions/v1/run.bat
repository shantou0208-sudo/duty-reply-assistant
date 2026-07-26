@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw duty_assistant.py
) else (
    python duty_assistant.py
)
