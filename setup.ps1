<#
.SYNOPSIS
    Create the Python environment and download the Kokoro model files.

.DESCRIPTION
    Run from the repository root, or double-click setup.bat.
    Requires Python 3.12, or uv (uv can fetch Python 3.12 automatically).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1 -Cpu

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1 -SkipModels
#>
param(
    [switch]$Cpu,
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# The uv cache and the project may live on different drives. Copying is expected
# here and avoids uv's "failed to hardlink files" warning.
$env:UV_LINK_MODE = "copy"

$venv   = Join-Path $PSScriptRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$engine = Join-Path $PSScriptRoot "Kokoro-TTS"
$reqs   = Join-Path $engine "requirements.txt"

function Write-Step([string]$text) {
    Write-Host ""
    Write-Host "==> $text" -ForegroundColor Cyan
}

if (-not (Test-Path $reqs)) {
    throw "Kokoro-TTS/requirements.txt was not found. Run this script from the repository root."
}

$uv = Get-Command uv -ErrorAction SilentlyContinue

# --- virtual environment --------------------------------------------------- #
if (-not (Test-Path $python)) {
    Write-Step "Creating .venv (Python 3.12)"
    if ($uv) {
        & uv venv $venv --python 3.12
        & uv pip install --python $python pip
    } else {
        $py = Get-Command python -ErrorAction SilentlyContinue
        if (-not $py) {
            throw "Python 3.12 is required. Install it from https://www.python.org/downloads/ (or install uv) and run setup again."
        }
        $pyver = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        if ($pyver -ne "3.12") {
            throw "Python 3.12 is required (found $pyver). Install Python 3.12 or install uv, then run setup again."
        }
        & python -m venv $venv
        & $python -m pip install --upgrade pip
    }
} else {
    Write-Step "Using existing .venv"
}

$ver = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($ver -ne "3.12") {
    Write-Warning "Python $ver detected. The pinned packages are tested with Python 3.12."
}

# --- PyTorch --------------------------------------------------------------- #
$torchName  = if ($Cpu) { "CPU" } else { "CUDA 12.6" }
$torchIndex = if ($Cpu) { "https://download.pytorch.org/whl/cpu" } else { "https://download.pytorch.org/whl/cu126" }

Write-Step "Installing PyTorch ($torchName)"
if ($uv) {
    & uv pip install --python $python torch torchaudio --index-url $torchIndex
} else {
    & $python -m pip install torch torchaudio --index-url $torchIndex
}
if ($LASTEXITCODE -ne 0) {
    throw "PyTorch installation failed. Check the connection and try again."
}

# --- Kokoro packages ------------------------------------------------------- #
Write-Step "Installing Kokoro packages"
if ($uv) {
    & uv pip install --python $python -r $reqs
} else {
    & $python -m pip install -r $reqs
}
if ($LASTEXITCODE -ne 0) {
    throw "Package installation failed."
}

# --- model files ----------------------------------------------------------- #
if (-not $SkipModels) {
    Write-Step "Downloading Kokoro model files (about 300 MB)"
    & $python (Join-Path $engine "download_models.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Model download failed. See the message above."
    }

    Write-Step "Running a self test"
    & $python (Join-Path $engine "tts.py") --selftest
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Start the server:   Start server.bat"
Write-Host "  2. Load the extension: chrome://extensions  ->  Developer mode  ->  Load unpacked  ->  extension"
Write-Host "  3. Open a chapter at   https://novelphoenix.com/"
Write-Host ""