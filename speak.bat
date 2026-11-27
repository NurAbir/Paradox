@echo off
rem Speak text from the command line and play it.
rem   speak.bat "Hello world"
rem   speak.bat "Hello" -v bm_george -s 0.9
rem   speak.bat -f notes.txt
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" "Kokoro-TTS\tts.py" --play %*