@echo off
rem Paradox - one-time environment setup.
rem   setup.bat            CUDA build (recommended when a supported GPU is present)
rem   setup.bat -Cpu       CPU-only build
rem   setup.bat -SkipModels
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause