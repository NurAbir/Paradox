# Contributing to Paradox

Thanks for taking the time to help. Paradox is a small, self-contained project:
a local TTS server plus a browser extension. Bug reports, fixes and focused
features are all welcome.

## Ways to help

- **Report a bug** — open an issue with what you did, what you expected, and
  what happened. Server console output and the browser's extension console
  (`chrome://extensions` → *Errors*) are very useful.
- **Suggest a feature** — describe the reading problem you want solved before
  the implementation.
- **Send a fix** — small, focused pull requests are easiest to review and merge.

## Development setup

See [`docs/SETUP.md`](docs/SETUP.md) to build the environment from scratch.
The short version:

```bat
setup.bat
```

That creates `.venv`, installs PyTorch and the Kokoro packages, downloads the
model into `models/` and runs a self test.

## Project layout

| Path | What lives there |
| --- | --- |
| `Kokoro-TTS/` | The engine: synthesis, voices, downloader, desktop GUI |
| `server/` | The local HTTP server the extension talks to |
| `extension/` | The Chromium MV3 extension |
| `tools/` | Small helper scripts (`check_server.py`, `make_icons.py`) |
| `docs/` | User and developer documentation |
| `assets/` | Logo artwork |

## Guidelines

1. **Keep it portable.** No absolute paths such as `C:\...` or `F:\...` in code,
   scripts or docs. Use repository-relative paths and the environment variables
   `KOKORO_MODELS_DIR`, `KOKORO_OUTPUT_DIR`, `KOKORO_VOICES_DIR` and `TTS_HOME`
   when a location must be configurable.
2. **Do not commit generated data.** `.venv/`, `models/`, voices, `output/` and
   logs are ignored on purpose; see `.gitignore`.
3. **Match the surrounding style.** Plain, neutral code and comments. No
   hardware-specific or conversational notes.
4. **Check before you push.**
   ```bat
   .venv\Scripts\python -m py_compile server\server.py Kokoro-TTS\tts.py Kokoro-TTS\gui.py Kokoro-TTS\download_models.py
   node --check extension\content.js
   node --check extension\background.js
   node --check extension\popup.js
   ```
5. **One topic per commit.** Write a short imperative subject line.

## Scope

Paradox reads text that is already on the page, for personal use. Please do not
add features that scrape, bypass paywalls, or send reading data anywhere. The
server must stay bound to `127.0.0.1`.

## License

By contributing, you agree that your work is released under the project's
[MIT License](LICENSE).
