@echo off
rem Paradox - open the standalone Kokoro desktop app (no console window).
setlocal
cd /d "%~dp0"

set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYW%" (
    echo.
    echo The virtual environment was not found.
    echo Run setup.bat once to create it, then try again.
    echo.
    pause
    exit /b 1
)

start "" "%PYW%" "%~dp0Kokoro-TTS\gui.py"