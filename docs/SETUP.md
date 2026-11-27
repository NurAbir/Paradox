# Setup

This guide builds Paradox from scratch, including in a **new folder** or on
another PC. Nothing in the repository depends on a fixed drive letter.

---

## 1. Requirements

| Requirement | Notes |
| --- | --- |
| Windows 10 or 11 | The launchers (`.bat`) and the desktop GUI are Windows-oriented. |
| Python 3.12 | Install from [python.org](https://www.python.org/downloads/), or let `uv` fetch it. |
| ~3 GB free disk | PyTorch + Kokoro packages + the model (about 330 MB). |
| Chromium browser | Chrome, Edge, Brave or Opera. |
| NVIDIA GPU | Optional. CUDA is used automatically when available; otherwise the CPU runs the model. |
| FFmpeg | Optional. Enables small MP3 output; without it the server returns WAV. |

> **Python 3.12 specifically.** The package pins are tested on 3.12. If you use
> `uv`, `setup.ps1` can create a 3.12 environment even when another version is
> installed.

---

## 2. Get the files

Clone the repository, or copy the whole project folder:

```bat
git clone <repository-url> paradox
cd paradox
```

The folder can be anywhere — `C:\Paradox`, `D:\tools\paradox`, a network share.
Do **not** copy `.venv`, `models` or `output` between machines; they are rebuilt.

---

## 3. One-step setup

Double-click **`setup.bat`**, or from a terminal:

```bat
setup.bat
```

This runs `setup.ps1`, which:

1. creates a Python 3.12 virtual environment in `.venv\`;
2. installs **PyTorch** — CUDA 12.6 by default, or CPU with `-Cpu`;
3. installs the Kokoro runtime from `Kokoro-TTS\requirements.txt`;
4. downloads the model and voices into `models\Kokoro-82M\`;
5. runs a short self test and prints the result.

Options:

```bat
setup.bat -Cpu          :: force CPU-only PyTorch (no GPU, smaller download)
setup.bat -SkipModels   :: stop before the model download
```

When it finishes you should see `Setup complete.` and a `self-test passed`
line with a realtime factor.

### What gets installed

| Package | Why |
| --- | --- |
| `torch`, `torchaudio` | Model runtime and tensor operations |
| `kokoro==0.9.4` | `KModel`, `KPipeline` — the model loader |
| `misaki[en,zh]==0.9.4` | Grapheme-to-phoneme front end |
| `soundfile==0.14.0` | Audio file output |
| `numpy==2.3.5` | Audio buffers (pinned below 2.5 for torch compatibility) |
| `huggingface_hub` | Model download |

---

## 4. Start the server

Double-click **`Start server.bat`**. Keep the window open while you read.

```
==============================================================
  Paradox - TTS server for Novel Phoenix
==============================================================
  Engine : ...\Kokoro-TTS
  Listen : http://127.0.0.1:8756
  Voice  : af_heart   Speed: 1.0   Format: mp3
  Keep this window open while you read.  Press Ctrl+C to stop.
==============================================================
[..:..:..] Loading Kokoro model ...
[..:..:..] Model ready on CUDA in 3.9s
[..:..:..] Warm-up done in 2.9s
```

Options can be passed through:

```bat
"Start server.bat" --port 8757 --voice bm_george --speed 0.95
"Start server.bat" --device cpu
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--port` | `8756` | HTTP port (also `NP_TTS_PORT`) |
| `--device` | `auto` | `auto`, `cuda` or `cpu` (also `KOKORO_DEVICE`) |
| `--voice` | `af_heart` | Default voice (also `NP_TTS_VOICE`) |
| `--speed` | `1.0` | Default speed (also `NP_TTS_SPEED`) |
| `--format` | `mp3` | `mp3` or `wav` (also `NP_TTS_FORMAT`) |

If you change the port, set the same port in the extension popup.

---

## 5. Load the extension

1. Open `chrome://extensions` (or `edge://extensions`).
2. Turn on **Developer mode**.
3. Click **Load unpacked**.
4. Select the **`extension`** folder inside the project.
5. Pin **Paradox** to the toolbar (optional).

No build step is needed — the extension is plain HTML/CSS/JavaScript.

---

## 6. Verify

Open a chapter, for example:

```
https://novelphoenix.com/novel/shadow-slave/chapter-1
```

The **Paradox** bar should appear bottom-right and start generating. If the
browser blocks autoplay, press **▶** once.

A command-line check is also available:

```bat
.venv\Scripts\python tools\check_server.py --speak "Paradox is online."
```

---

## 7. Building in a new folder or on another PC

The project is intentionally portable:

1. Copy or clone the repository **without** `.venv`, `models` and `output`.
2. Install Python 3.12 (or `uv`) on the target machine.
3. Run `setup.bat` in the new folder. It creates a fresh `.venv` and downloads
   the model relative to the new location.
4. Load the `extension` folder from the new location in the browser.
5. Start `Start server.bat`.

Nothing needs editing. Paths are resolved from the script's own location, and
these environment variables can override them if required:

| Variable | Affects | Default |
| --- | --- | --- |
| `TTS_HOME` | Folder containing the engine (`tts.py`) | `.\Kokoro-TTS` |
| `KOKORO_MODELS_DIR` | Model download/target folder | `.\models` |
| `KOKORO_MODEL_DIR` | A specific model sub-folder | `.\models\Kokoro-82M` |
| `KOKORO_VOICES_DIR` | Extra voice packs | `.\voices` |
| `KOKORO_OUTPUT_DIR` | Generated audio | `.\output` |
| `KOKORO_DEVICE` | `auto`, `cuda`, `cpu` | `auto` |
| `NP_TTS_PORT` | Server port | `8756` |
| `HF_HOME` | Hugging Face cache | `<models>\hf` |

### Moving an existing install

If you already have a working `models` folder, you can skip the download:

```bat
mkdir models
xcopy /E /I "D:\old\paradox\models\Kokoro-82M" "models\Kokoro-82M"
setup.bat -SkipModels
```

---

## 8. Manual setup (no script)

If you prefer to install by hand:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip

:: CUDA build (use the CPU index for a CPU-only machine)
.venv\Scripts\python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126

.venv\Scripts\python -m pip install -r Kokoro-TTS\requirements.txt
.venv\Scripts\python Kokoro-TTS\download_models.py
.venv\Scripts\python Kokoro-TTS\tts.py --selftest
```

---

## 9. Updating

```bat
git pull
.venv\Scripts\python -m pip install -r Kokoro-TTS\requirements.txt
```

Then press **Reload** on the extension card in `chrome://extensions`.

---

## 10. Removing Paradox

1. Remove the extension in `chrome://extensions`.
2. Delete the project folder. That also removes `.venv` and the downloaded
   model inside it.

The model is **not** stored anywhere else except the Hugging Face cache under
`models\hf`, which is inside the project.

---

## Troubleshooting setup

| Problem | Solution |
| --- | --- |
| `Python 3.12 is required` | Install Python 3.12, or install [uv](https://docs.astral.sh/uv/) and rerun `setup.bat`. |
| PyTorch download is slow or fails | Retry, or use `setup.bat -Cpu` for a smaller download. |
| `Model download failed` | Check the connection and rerun `setup.bat`; it resumes. |
| `No module named torch` | The PyTorch step did not finish; rerun `setup.bat`. |
| CUDA out of memory | Start the server with `--device cpu`, or close GPU-heavy apps. |
| `ffmpeg not found` | Optional. Install FFmpeg and add it to `PATH` for MP3; otherwise WAV is used. |
| `Failed to hardlink files` (`uv`) | Benign. The uv cache and the project are on different drives, so uv copies instead. `setup.ps1` sets `UV_LINK_MODE=copy`, which silences it. |
| `You are sending unauthenticated requests to the HF Hub` | Benign. It only means no Hugging Face token is stored, which is fine for these public model downloads. A token is never required. |
| `sha256 mismatch` after downloading the model | The download is incomplete or corrupt. Delete `models\Kokoro-82M` and rerun `setup.bat`; the loader resumes and re-verifies. See [`CHECKSUMS.md`](CHECKSUMS.md). |