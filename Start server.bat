@echo off
rem Paradox - start the local Kokoro TTS server used by the browser extension.
rem Usage:  "Start server.bat"                        (default port 8756)
rem         "Start server.bat" --port 8757 --voice bm_george
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo.
    echo The virtual environment was not found.
    echo Run setup.bat once to create it, then try again.
    echo.
    pause
    exit /b 1
)

"%PY%" "%~dp0server\server.py" %*
echo.
pause