<div align="center">

<img src="assets/logo_icon.png" width="120" alt="Paradox logo">

# Paradox

**Read web novels out loud with your own local voice.**

A local text-to-speech server and a browser extension that read
[Novel Phoenix](https://novelphoenix.com/) chapters with the open
**Kokoro-82M** model. Click **Next** and it keeps reading — no page reload,
no cloud service, no account.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Kokoro](https://img.shields.io/badge/Model-Kokoro--82M-7c6cff.svg)](https://huggingface.co/hexgrad/Kokoro-82M)
[![Chrome](https://img.shields.io/badge/Chrome%20%7C%20Edge-Extension-4285F4.svg)](https://www.google.com/chrome/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-orange.svg)](CHANGELOG.md)
[![CI](https://github.com/NurAbir/Paradox/actions/workflows/ci.yml/badge.svg)](https://github.com/NurAbir/Paradox/actions/workflows/ci.yml)

</div>

---

## Contents

- [Description](#description)
- [Features](#features)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [The control bar](#the-control-bar)
- [Standalone text-to-speech](#standalone-text-to-speech)
- [Project layout](#project-layout)
- [Documentation](#documentation)
- [Command-line check](#command-line-check)
- [Troubleshooting](#troubleshooting)
- [Verifying downloads](#verifying-downloads)
- [Credits](#credits)
- [License](#license)

## Description

**Paradox** turns a reading session into a listening session. A tiny server on
your machine runs the **Kokoro-82M** text-to-speech model, and a browser
extension feeds it the chapter you are looking at. The server returns a
finished audio file that plays in the tab.

Because everything runs locally, there are no tokens, sign-ups or network calls
to a service. When a chapter ends, Paradox can move to the next one and keep
playing, so you can listen hands-free.

> Paradox is a reading aid. It is **not affiliated** with Novel Phoenix or any
> other site, and it only reads text already shown in your browser.

## Features

- **Whole-chapter audio.** The full chapter is synthesized in one request and
  cached while it plays, so playback is smooth.
- **Seamless next / previous.** The extension loads the neighbouring chapter in
  place, updating the page and the address bar without a reload.
- **Auto-advance.** Finish a chapter and the next one starts by itself.
- **54 voices, 8 languages.** Every Kokoro voice pack, selectable from the
  toolbar popup or the on-page control bar.
- **Speed control.** 0.5×–2.0×, adjustable while you listen.
- **Local and private.** The server binds to `127.0.0.1`; nothing is uploaded.
- **Portable.** Point it at any folder and rebuild it with one script.
- **Also a standalone TTS app.** The same engine ships with a desktop GUI and a
  command-line tool for reading text files, notes or the clipboard.

## How it works

```
 Chrome / Edge                              Your machine
+---------------------------+   POST      +-------------------------------+
| novelphoenix.com chapter  |  chapter    | server/server.py              |
|  - extension/content.js   | ----------> |  -> Kokoro-TTS (Kokoro-82M)   |
|  - on-page control bar    |             |  -> audio/mpeg or audio/wav   |
|  - <audio> playback       | <---------- | http://127.0.0.1:8756         |
+---------------------------+   audio     +-------------------------------+
```

1. The content script lifts the chapter text out of the page.
2. It POSTs the text to the local server's `/tts` endpoint.
3. The server runs the Kokoro model and returns an audio file.
4. The page plays it; on **Next**, the script fetches the next chapter and
   starts the cycle again without reloading.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the details.

## Requirements

- **Windows 10/11** (the launchers and the desktop GUI target Windows).
- **Python 3.12**, or [uv](https://docs.astral.sh/uv/) to fetch it for you.
- An **NVIDIA GPU is optional** — CUDA is used when present, otherwise the CPU
  runs the model. A GPU makes chapter generation much faster.
- A **Chromium browser**: Chrome, Edge, Brave or Opera.
- **Optional:** FFmpeg on `PATH` for smaller MP3 output. Without it the server
  returns lossless WAV.

## Quick start

```bat
:: 1. Build the environment (once). Creates .venv, installs packages,
::    downloads the model into models/ and runs a self test.
setup.bat

:: 2. Start the local TTS server. Keep the window open while you read.
"Start server.bat"

:: 3. Load the extension:
::    chrome://extensions  ->  Developer mode  ->  Load unpacked  ->  extension
```

Then open any chapter, for example
`https://novelphoenix.com/novel/shadow-slave/chapter-1`. A **Paradox** bar
appears in the bottom-right corner and begins generating the chapter. If the
browser blocks autoplay the first time, press **▶** once; after that, **Next**
keeps reading on its own.

Full, step-by-step instructions — including building the project in a different
folder — are in [`docs/SETUP.md`](docs/SETUP.md).

## The control bar

| Button | Action |
| --- | --- |
| ⏮ / ⏭ | Previous / next chapter (loaded in place) |
| ▶ / ❚❚ | Play / pause |
| ■ | Stop and reset |
| ⚙ | Settings (also in the toolbar popup) |

A thin bar under the controls shows how far into the chapter you are.

### Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Reader enabled | on | Show the control bar at all |
| Read when a chapter opens | on | Generate and try to play on load |
| Continue to next chapter | on | Auto-advance when audio ends |
| Switch chapters in place | on | Intercept Next / Prev instead of reloading |
| Voice | `af_heart` | Any of the 54 Kokoro voices |
| Speed | `1.0` | 0.5 – 2.0 |
| Port | `8756` | Must match the server |

## Standalone text-to-speech

The engine is useful on its own, without the extension:

```bat
:: Speak text and play it immediately
speak.bat "Hello from Paradox"

:: Read the clipboard out loud
speak_clipboard.bat

:: Open the desktop app
"Kokoro TTS.bat"

:: Command line, any language or voice
.venv\Scripts\python Kokoro-TTS\tts.py -f chapter.txt -o output\chapter.mp3 -v bm_george --play
.venv\Scripts\python Kokoro-TTS\tts.py --list-voices
.venv\Scripts\python Kokoro-TTS\tts.py --selftest
```

More in [`docs/USAGE.md`](docs/USAGE.md).

## Project layout

```
paradox/
├─ README.md                  this file
├─ LICENSE                    MIT licence
├─ SECURITY.md                how to report a vulnerability
├─ CREDITS.md                 attribution for Kokoro and the libraries used
├─ CHANGELOG.md               release history
├─ CONTRIBUTING.md            how to help and build from source
├─ .editorconfig              shared editor settings
├─ .gitattributes             line-ending rules
├─ .gitignore                 ignores models, voices, output and .venv
├─ .github/
│  ├─ workflows/ci.yml        syntax and manifest checks on every push
│  └─ ISSUE_TEMPLATE/         bug report and feature request forms
├─ setup.bat / setup.ps1      one-time environment + model setup
├─ "Start server.bat"         run the local TTS server
├─ "Kokoro TTS.bat"           desktop GUI
├─ speak.bat                  speak a string or file from the command line
├─ speak_clipboard.bat        read the clipboard out loud
├─ requirements.txt           root convenience: -r Kokoro-TTS/requirements.txt
│
├─ Kokoro-TTS/                the TTS engine (no model files)
│  ├─ tts.py                  synthesis, voices, audio I/O and CLI
│  ├─ gui.py                  small tkinter desktop app
│  ├─ download_models.py      fetch + SHA-256 verify model and voices
│  └─ requirements.txt        runtime package pins
│
├─ server/
│  └─ server.py               local HTTP server (/health, /voices, /tts)
│
├─ extension/                 load this folder in Chrome / Edge
│  ├─ manifest.json           Manifest V3 definition
│  ├─ background.js           service worker (CORS-free fallback fetch)
│  ├─ content.js              chapter extraction, control bar, playback
│  ├─ popup.html / popup.js   toolbar settings popup
│  └─ icons/                  icon16.png, icon48.png, icon128.png
│
├─ tools/
│  ├─ check_server.py         command-line smoke test
│  ├─ checksums.py            generate / verify SHA-256 manifests
│  └─ make_icons.py           regenerate the logo assets and icons
│
├─ docs/                      SETUP, USAGE, ARCHITECTURE, CHECKSUMS
├─ assets/                    logo.jpg (artwork) and the generated PNGs
│
├─ models/                    downloaded model files   (ignored by git)
├─ voices/                    extra voice packs        (ignored by git)
└─ output/                    generated audio          (ignored by git)
```

The repository ships **no model files**. `models/`, `voices/` and `output/` are
empty placeholders (`.gitkeep`) that `setup.bat` fills in — the 330 MB Kokoro
weights are downloaded and SHA-256 verified, never committed.

## Documentation

| Document | What it covers |
| --- | --- |
| [`docs/SETUP.md`](docs/SETUP.md) | Build from scratch, including in a new folder |
| [`docs/USAGE.md`](docs/USAGE.md) | Reading with the extension and the standalone tools |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the engine, server and extension fit together |
| [`docs/CHECKSUMS.md`](docs/CHECKSUMS.md) | Model SHA-256 values and archive verification |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development setup, checks and pull-request flow |
| [`CREDITS.md`](CREDITS.md) | Attribution for Kokoro and the libraries used |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability |

## Command-line check

```bat
:: Is the server up, and can it make audio?
.venv\Scripts\python tools\check_server.py

:: Also synthesize a custom line
.venv\Scripts\python tools\check_server.py --speak "Hello from Paradox"
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Bar says **Server offline** | Run `Start server.bat` and wait for *Model ready*. Check the port matches (default `8756`). |
| Server prints **Kokoro engine not found** | Run `setup.bat` first, or set `TTS_HOME` to the folder containing `tts.py`. |
| **Could not import the Kokoro engine** | The install is incomplete. Run `.venv\Scripts\python Kokoro-TTS\tts.py --selftest`. |
| **Could not listen on port 8756** | Something else uses it. Start with `--port 8757` and set `8757` in the popup. |
| Audio never starts ("Press ▶") | Browser autoplay policy — click **▶** once; later chapter changes then play automatically. |
| First chapter is slow | The model is loading and warming up. Later chapters are far faster. |
| No sound at all | Check the Windows output device, then test with `tools\check_server.py`. |
| Extension menu missing on the page | Reload the extension in `chrome://extensions`, then reload the tab. Confirm the URL is `novelphoenix.com`. |
| Voice list is empty | The server was offline when the popup opened. Start it, then press **Check**. |

## Verifying downloads

Model files are checked automatically during setup. To re-check them at any
time:

```bat
.venv\Scripts\python Kokoro-TTS\download_models.py --check
```

The canonical SHA-256 values, and how to verify a release archive, are in
[`docs/CHECKSUMS.md`](docs/CHECKSUMS.md). A general checksum tool is available
as `tools/checksums.py`.

## Credits

Paradox would not exist without the open Kokoro project. The engine in
`Kokoro-TTS/` is adapted from
[**hexgrad/Kokoro-TTS**](https://huggingface.co/spaces/hexgrad/Kokoro-TTS)
and uses the [**hexgrad/Kokoro-82M**](https://huggingface.co/hexgrad/Kokoro-82M)
model. See [`CREDITS.md`](CREDITS.md) for the full list of projects and
libraries.

## License

Released under the [MIT License](LICENSE). Third-party components keep their
own licenses.
