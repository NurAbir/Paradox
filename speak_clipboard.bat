@echo off
rem Read the current clipboard out loud with Kokoro.
setlocal
cd /d "%~dp0"
set "CLIP=%TEMP%\kokoro_clipboard.txt"
powershell -NoProfile -Command "Get-Clipboard -Raw | Set-Content -Path '%CLIP%' -Encoding UTF8"
if errorlevel 1 (
    echo Could not read the clipboard.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "Kokoro-TTS\tts.py" -f "%CLIP%" --play
del "%CLIP%" >nul 2>&1
if errorlevel 1 pause