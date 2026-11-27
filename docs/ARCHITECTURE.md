# Architecture

Paradox is split into four small, independent pieces: the **engine**, the
**server**, the **extension**, and the **tools** around them. Each can be used
on its own; together they form the reading experience.

---

## Components

```
+-----------------------------+        +-----------------------------------+
| Browser (Chromium)          |        | This machine                      |
|                             |        |                                   |
|  extension/content.js       |  HTTP  |  server/server.py                 |
|   - chapter extraction      | -----> |   - /health  /voices  /tts       |
|   - in-place navigation     |        |   - CORS + Private Network Access |
|   - control bar             | <----- |   - background model load         |
|   - <audio> element         |  audio |            |                      |
|                             |        |            v                      |
|  extension/background.js    |        |  Kokoro-TTS/tts.py                |
|  extension/popup.*          |        |   - KokoroEngine (KModel)         |
+-----------------------------+        |   - KPipeline, voices, audio I/O  |
                                       |            |                      |
                                       |            v                      |
                                       |  models/  voices/  output/        |
                                       +-----------------------------------+
```

| Piece | Entry point | Responsibility |
| --- | --- | --- |
| Engine | `Kokoro-TTS/tts.py` | Load Kokoro, synthesize text to a NumPy array, write audio files, list voices |
| Desktop GUI | `Kokoro-TTS/gui.py` | Optional tkinter front end over the engine |
| Server | `server/server.py` | HTTP API, request validation, audio encoding, CORS |
| Extension | `extension/` | Page integration, chapter extraction, playback, settings |
| Tools | `tools/` | Smoke test and icon/asset generation |

---

## Data flow

1. **Load.** The content script runs on `novelphoenix.com` at `document_idle`
   and injects the control bar.
2. **Extract.** It locates the chapter container, strips scripts, styles and
   known promo lines, and joins the paragraphs into plain text.
3. **Request.** The script `POST`s JSON to `http://127.0.0.1:8756/tts`:

   ```json
   { "text": "chapter text ...", "voice": "af_heart", "speed": 1.0, "format": "mp3" }
   ```

4. **Synthesize.** The server waits for the model if it is still loading, runs
   `KokoroEngine.synth`, and encodes the samples to MP3 (or WAV).
5. **Respond.** The audio bytes are returned with `audio/mpeg` or `audio/wav`
   and two informational headers: `X-Audio-Seconds` and `X-Synth-Seconds`.
6. **Play.** The script creates an object URL and plays it through an `<audio>`
   element. A `timeupdate` listener drives the progress bar.
7. **Advance.** On `Next`, or automatically when playback ends, the script
   fetches the neighbouring chapter URL, parses it in the page, swaps in the new
   text and URL, and repeats from step 3 — without a page reload.

The page never uploads anything. The only network traffic is the chapter HTML
that the browser already requests from the site.

---

## Server API

Bound to `127.0.0.1` only. The default port is `8756`.

### `GET /health`

```json
{
  "ok": true,
  "service": "paradox",
  "version": "1.0",
  "model_ready": true,
  "device": "cuda",
  "voice": "af_heart",
  "speed": 1.0,
  "format": "mp3",
  "uptime_seconds": 42.5
}
```

`model_ready` turns true as soon as the model is loaded; a first-run warm-up may
still be finishing. `GET /` is an alias.

### `GET /voices`

```json
{
  "grouped": { "a": ["af_heart", "af_bella"], "b": ["bf_emma"] },
  "flat": ["af_heart", "af_bella", "bf_emma"]
}
```

### `POST /tts`

Request body (JSON):

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `text` | string | — | Required. Up to 400,000 characters. |
| `voice` | string | `af_heart` | Any installed voice |
| `speed` | number | `1.0` | Clamped to 0.5 – 2.0 |
| `format` | string | server default | `mp3` or `wav` |

Response: `200` with the audio bytes. Errors return JSON with an `error` field
(`400` bad request, `413` too large, `500` synthesis failure).

Request bodies are capped at 6 MB, which is far more than a long chapter needs.

### CORS and Private Network Access

The server echoes the caller's `Origin` (page or `chrome-extension://…`) and
sends `Access-Control-Allow-Private-Network: true`, so Chrome permits a public
page to reach a loopback server. Preflight `OPTIONS` returns `204`.

---

## Extension

Manifest V3, no build step.

| File | Role |
| --- | --- |
| `manifest.json` | Permissions, host matches, content script, popup, icons |
| `content.js` | Chapter extraction, in-place navigation, control bar, playback, settings sync |
| `background.js` | Service worker; localhost fallback fetch and message plumbing |
| `popup.html` / `popup.js` | Toolbar settings UI and server check |

Permissions are deliberately small: `storage`, plus host access to Novel Phoenix
and to loopback (`127.0.0.1`, `localhost`). The extension asks for nothing else.

---

## Engine internals

`Kokoro-TTS/tts.py` is the only module that touches PyTorch or the model.

- `KokoroEngine` loads `config.json` and `kokoro-*.pth` from the model folder
  once, moves the model to the selected device, and reuses it.
- `KPipeline` is created per language code and cached, so switching between
  English and another language does not reload the model.
- `synth()` cleans the text, chunks it through the pipeline, concatenates the
  audio, and returns a float32 NumPy array at 24 kHz.
- `save_audio()` writes WAV/FLAC/OGG via `soundfile`, and MP3 via FFmpeg when it
  is available (with a graceful fallback).
- `list_voices()` / `find_voice()` read `*.pt` voice packs from the model's
  `voices/` folder and the repository's `voices/` folder.

### Paths

All paths are relative to the source files and can be overridden by environment
variables, so the project can live in any folder:

| Variable | Default |
| --- | --- |
| `KOKORO_MODELS_DIR` | `<repo>/models` |
| `KOKORO_MODEL_DIR` | `<models>/Kokoro-82M` |
| `KOKORO_VOICES_DIR` | `<repo>/voices` |
| `KOKORO_OUTPUT_DIR` | `<repo>/output` |
| `HF_HOME` | `<models>/hf` |
| `TTS_HOME` | `<repo>/Kokoro-TTS` (server only) |
| `KOKORO_DEVICE` | `auto` |

---

## Startup sequence

1. `Start server.bat` launches `.venv\Scripts\python server\server.py`.
2. The server imports the engine from `Kokoro-TTS/` and opens the socket
   immediately, so `/health` answers while the model loads.
3. A background thread loads the model, sets `model_ready`, then warms up one
   voice.
4. `/tts` waits for `model_ready` (up to 300 s) before synthesizing, so the
   first chapter is not rejected while the model is still loading.

---

## Design choices

- **Whole-chapter requests.** One request per chapter keeps the browser simple
  and avoids stitching gaps at paragraph boundaries.
- **In-place navigation.** Swapping text instead of reloading preserves the
  `<audio>` element and user gesture, which keeps autoplay working.
- **No model in git.** Model and voice files are large; `setup.ps1` fetches
  them. The repository stays small and clone-friendly.
- **Loopback only.** The server is not reachable from other machines, and the
  extension sends nothing to a third party.

---

## Extending

- **Another reading site.** Add its URL to `host_permissions` and
  `content_scripts.matches` in `manifest.json`, then add a chapter extractor in
  `content.js`.
- **Another voice model.** Point `--model-dir` (or `KOKORO_MODEL_DIR`) at a
  compatible Kokoro folder.
- **Another client.** Any program can use the HTTP API; see the endpoints above.