@echo off
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8765/test_page.html"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m http.server 8765
) else (
    py -m http.server 8765
)
