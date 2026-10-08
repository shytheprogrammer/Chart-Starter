@echo off
cd /d "%~dp0"
if exist "Windows\ChartStarter.exe" (
    start "" "Windows\ChartStarter.exe"
    exit /b
)
python app.py
if errorlevel 1 pause
