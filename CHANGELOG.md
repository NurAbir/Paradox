# Changelog

All notable changes to Paradox are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-27

### Added

- Local Kokoro TTS HTTP server (`server/server.py`) exposing `/health`,
  `/voices` and `/tts`, bound to `127.0.0.1` only.
- Self-contained Kokoro engine in `Kokoro-TTS/` (model loading, synthesis, voice
  listing, model downloader and desktop GUI), with no bundled model files.
- Chromium browser extension (`extension/`) that extracts a Novel Phoenix
  chapter, plays it, and advances to the next chapter in place.
- Control bar with previous / next / play / pause / stop and settings, plus a
  reading-progress indicator.
- Toolbar popup for reader options, voice, speed and server port.
- Portable setup: `setup.ps1` / `setup.bat` create `.venv`, install PyTorch
  (CUDA or CPU) and the Kokoro packages, download the model and run a self test.
- Convenience launchers: `Start server.bat`, `Kokoro TTS.bat`, `speak.bat`,
  `speak_clipboard.bat`.
- Documentation: `README.md`, `docs/SETUP.md`, `docs/USAGE.md`,
  `docs/ARCHITECTURE.md`, `CREDITS.md`, `CONTRIBUTING.md`.
- Project logo and generated extension icons (`assets/`, `extension/icons/`).

[1.0.0]: https://github.com/your-name/paradox/releases/tag/v1.0.0
