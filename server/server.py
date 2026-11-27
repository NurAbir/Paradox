#!/usr/bin/env python
"""Paradox - local Kokoro TTS server for the browser extension.

It imports the engine from the repository's Kokoro-TTS folder. The browser
extension POSTs chapter text here and receives a finished audio file to play.

Run it with:
    Start server.bat
or:
    .venv\\Scripts\\python server\\server.py

Endpoints (bound to 127.0.0.1 only):
    GET  /health   -> JSON status (server up, model ready, device, voices)
    GET  /voices   -> JSON { grouped, flat }
    POST /tts      -> JSON {text, voice, speed, format} -> audio/mpeg or audio/wav
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# --------------------------------------------------------------------------- #
# Locate the existing Kokoro install (override with TTS_HOME if you move it).
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent          # server/
PROJECT = HERE.parent                           # repository root
TTS_HOME = Path(os.environ.get("TTS_HOME", PROJECT / "Kokoro-TTS")).expanduser().resolve()

DEFAULT_PORT = 8756
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
DEFAULT_FORMAT = "mp3"          # mp3 if ffmpeg is present, otherwise wav
MAX_BODY = 6 * 1024 * 1024      # 6 MB of JSON is plenty for one chapter
MAX_TEXT = 400_000              # hard cap on characters synthesised per request

if not TTS_HOME.is_dir():
    sys.stderr.write(
        f"\n[error] Kokoro engine not found at {TTS_HOME}\n"
        "Set the TTS_HOME environment variable to the folder that contains tts.py,\n"
        "or run setup.ps1 first.\n\n"
    )
    raise SystemExit(1)

sys.path.insert(0, str(TTS_HOME))
try:
    import tts as kokoro  # noqa: E402
except Exception:  # pragma: no cover - import problems are shown clearly
    sys.stderr.write(
        f"\n[error] Could not import the Kokoro engine from {TTS_HOME}.\n"
        "Run  .venv\\Scripts\\python Kokoro-TTS\\tts.py --selftest  to check the install.\n\n"
    )
    traceback.print_exc()
    raise SystemExit(1)


# --------------------------------------------------------------------------- #
# Engine (loaded once, in the background, then reused for every request)
# --------------------------------------------------------------------------- #
_engine = None
_engine_error: str | None = None
_engine_ready = threading.Event()
_started_at = time.time()


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_engine(device: str) -> None:
    global _engine, _engine_error
    try:
        _log("Loading Kokoro model ...")
        t0 = time.time()
        engine = kokoro.KokoroEngine(device=device, log=_log)
        _engine = engine
        _log(f"Model ready on {engine.device.upper()} in {time.time() - t0:.1f}s")
    except Exception as exc:  # pragma: no cover
        _engine_error = str(exc)
        _log(f"Model failed to load: {exc}")
        traceback.print_exc()
    finally:
        # Health can report the model as soon as it is loaded; the (possibly
        # slow) first-run warm-up happens next and /tts waits for it via the
        # engine's own lock, so the first chapter is fast once it is done.
        _engine_ready.set()

    if _engine is not None:
        try:
            t0 = time.time()
            _engine.warmup(os.environ.get("KOKORO_WARMUP_VOICE", DEFAULT_VOICE))
            _log(f"Warm-up done in {time.time() - t0:.1f}s")
        except Exception as exc:
            _log(f"Warm-up skipped: {exc}")


def get_engine(timeout: float = 300.0):
    if not _engine_ready.wait(timeout):
        raise RuntimeError("TTS model is still loading, try again in a moment.")
    if _engine is None:
        raise RuntimeError(f"TTS model failed to start: {_engine_error}")
    return _engine


def synth_to_bytes(text: str, voice: str, speed: float, fmt: str):
    """Synthesise text and return (bytes, mime, audio_seconds, synth_seconds)."""
    engine = get_engine()
    speed = max(0.5, min(2.0, float(speed or DEFAULT_SPEED)))
    t0 = time.time()
    audio = engine.synth(text, voice=voice or DEFAULT_VOICE, speed=speed)
    synth_seconds = time.time() - t0
    if audio is None or getattr(audio, "size", 0) == 0:
        raise ValueError("nothing speakable in this text")

    audio_seconds = audio.size / kokoro.SAMPLE_RATE
    tmpdir = Path(tempfile.mkdtemp(prefix="np_tts_"))
    try:
        fmt = (fmt or DEFAULT_FORMAT).lower()
        if fmt == "mp3":
            out = tmpdir / "chapter.mp3"
            try:
                kokoro.save_audio(audio, out)
            except Exception:
                # No ffmpeg / no MPEG support -> silently use wav instead.
                fmt, out = "wav", tmpdir / "chapter.wav"
                kokoro.save_audio(audio, out)
        else:
            fmt, out = "wav", tmpdir / "chapter.wav"
            kokoro.save_audio(audio, out)
        data = out.read_bytes()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    mime = "audio/mpeg" if fmt == "mp3" else "audio/wav"
    return data, mime, audio_seconds, synth_seconds


# --------------------------------------------------------------------------- #
# HTTP server / handler
# --------------------------------------------------------------------------- #
class QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        # Browsers routinely close keep-alive sockets early; that is not an error.
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Paradox/1.0"

    # -- helpers ----------------------------------------------------------- #
    def _cors(self) -> None:
        # Echo the caller's origin (works for novelphoenix.com and for the
        # chrome-extension:// origin) instead of a wildcard.
        origin = self.headers.get("Origin")
        self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Chrome Private Network Access (public page -> 127.0.0.1)
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, code: int, body: bytes, mime: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        for k, v in (extra or {}).items():
            self.send_header(k, str(v))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # keep the console tidy
        _log(f"{self.address_string()} {fmt % args}")

    # -- verbs ------------------------------------------------------------- #
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/"):
            info = {
                "ok": True,
                "service": "paradox",
                "version": "1.0",
                "model_ready": _engine_ready.is_set() and _engine is not None,
                "device": getattr(_engine, "device", None),
                "voice": DEFAULT_VOICE,
                "speed": DEFAULT_SPEED,
                "format": DEFAULT_FORMAT,
                "uptime_seconds": round(time.time() - _started_at, 1),
            }
            if _engine_error:
                info["error"] = _engine_error
            self._send_json(200, info)
            return
        if path == "/voices":
            try:
                grouped = kokoro.list_voices()
                flat = [name for names in grouped.values() for name in names]
                self._send_json(200, {"grouped": grouped, "flat": flat})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/tts":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._send_json(400, {"ok": False, "error": "empty body"})
            return
        if length > MAX_BODY:
            self._send_json(413, {"ok": False, "error": "chapter too large"})
            return

        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": f"bad JSON: {exc}"})
            return

        text = (payload.get("text") or "").strip()
        if not text:
            self._send_json(400, {"ok": False, "error": "no text"})
            return
        if len(text) > MAX_TEXT:
            self._send_json(413, {"ok": False, "error": f"text longer than {MAX_TEXT} chars"})
            return

        voice = payload.get("voice") or DEFAULT_VOICE
        speed = payload.get("speed") or DEFAULT_SPEED
        fmt = payload.get("format") or DEFAULT_FORMAT

        _log(f"/tts  {len(text):,} chars  voice={voice}  speed={speed}  fmt={fmt}")
        try:
            data, mime, audio_s, synth_s = synth_to_bytes(text, voice, speed, fmt)
        except Exception as exc:
            _log(f"/tts  failed: {exc}")
            self._send_json(500, {"ok": False, "error": str(exc)})
            return

        _log(
            f"/tts  done: {audio_s:.1f}s audio in {synth_s:.1f}s "
            f"({len(data) / 1024:.0f} KB)"
        )
        self._send_bytes(
            200,
            data,
            mime,
            {
                "X-Audio-Seconds": f"{audio_s:.2f}",
                "X-Synth-Seconds": f"{synth_s:.2f}",
            },
        )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    global DEFAULT_VOICE, DEFAULT_SPEED, DEFAULT_FORMAT

    ap = argparse.ArgumentParser(description="Paradox - local Kokoro TTS server for the Novel Phoenix extension.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("NP_TTS_PORT", DEFAULT_PORT)))
    ap.add_argument("--device", default=os.environ.get("KOKORO_DEVICE", "auto"),
                    choices=("auto", "cuda", "cpu"))
    ap.add_argument("--voice", default=os.environ.get("NP_TTS_VOICE", DEFAULT_VOICE))
    ap.add_argument("--speed", type=float, default=float(os.environ.get("NP_TTS_SPEED", DEFAULT_SPEED)))
    ap.add_argument("--format", default=os.environ.get("NP_TTS_FORMAT", DEFAULT_FORMAT),
                    choices=("mp3", "wav"))
    args = ap.parse_args(argv)

    DEFAULT_VOICE, DEFAULT_SPEED, DEFAULT_FORMAT = args.voice, args.speed, args.format

    print("=" * 62)
    print("  Paradox - TTS server for Novel Phoenix")
    print("=" * 62)
    print(f"  Engine : {TTS_HOME}")
    print(f"  Listen : http://127.0.0.1:{args.port}")
    print(f"  Voice  : {args.voice}   Speed: {args.speed}   Format: {args.format}")
    print("  Keep this window open while you read.  Press Ctrl+C to stop.")
    print("=" * 62, flush=True)

    threading.Thread(target=load_engine, args=(args.device,), daemon=True).start()

    try:
        httpd = QuietServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        sys.stderr.write(
            f"\n[error] Could not listen on port {args.port}: {exc}\n"
            "Another program may be using it. Try:  Start server.bat --port 8757\n"
            "then set the same port in the extension popup.\n\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())