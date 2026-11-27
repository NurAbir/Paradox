#!/usr/bin/env python
"""Kokoro-82M text-to-speech engine (local, offline after setup).

Quick start (from the repository root):
    .venv\\Scripts\\python Kokoro-TTS\\tts.py "Hello! This is Kokoro running locally."
    .venv\\Scripts\\python Kokoro-TTS\\tts.py "Hello!" -v bm_george -s 0.95 --play
    .venv\\Scripts\\python Kokoro-TTS\\tts.py -f book.txt -o output\\book.mp3
    .venv\\Scripts\\python Kokoro-TTS\\tts.py --list-voices
    .venv\\Scripts\\python Kokoro-TTS\\tts.py --selftest

Model: hexgrad/Kokoro-82M (v1.0), 82M parameters, 24 kHz, 54 voices, 8 languages.
Runs on CUDA when available and falls back to the CPU automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent          # Kokoro-TTS/
ROOT = HERE.parent                              # repository root

# Data lives outside the source folder so it can be kept out of version control.
MODELS_DIR = Path(os.environ.get("KOKORO_MODELS_DIR", ROOT / "models")).expanduser()
OUTPUT_DIR = Path(os.environ.get("KOKORO_OUTPUT_DIR", ROOT / "output")).expanduser()
VOICES_DIR = Path(os.environ.get("KOKORO_VOICES_DIR", ROOT / "voices")).expanduser()
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import warnings  # noqa: E402

import numpy as np  # noqa: E402

# Third-party chatter that does not affect output.
warnings.filterwarnings("ignore", message="dropout option adds dropout.*")
warnings.filterwarnings("ignore", message="`torch.nn.utils.weight_norm` is deprecated.*")
warnings.filterwarnings("ignore", message="`torch.jit.script` is deprecated.*")
warnings.filterwarnings("ignore", message=".*Defaulting repo_id.*")

SAMPLE_RATE = 24_000
DEFAULT_MODEL_DIR = MODELS_DIR / "Kokoro-82M"
DEFAULT_VOICE = "af_heart"

LANG_NAMES = {
    "a": "American English",
    "b": "British English",
    "e": "Spanish",
    "f": "French",
    "h": "Hindi",
    "i": "Italian",
    "j": "Japanese",
    "p": "Brazilian Portuguese",
    "z": "Mandarin Chinese",
}
GENDER = {"f": "female", "m": "male"}

AUDIO_FORMATS = ("wav", "flac", "ogg", "mp3")


class TTSError(RuntimeError):
    """User-facing error (missing model, unsupported language, ...)."""


# --------------------------------------------------------------------------- #
# Paths and voice metadata
# --------------------------------------------------------------------------- #
def model_dir(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("KOKORO_MODEL_DIR")
    return Path(env).expanduser().resolve() if env else DEFAULT_MODEL_DIR


def voice_dirs(mdir: Path) -> list[Path]:
    dirs = [mdir / "voices", VOICES_DIR]
    return [d for d in dirs if d.is_dir()]


def voice_lang(name: str) -> str:
    lang = name[:1].lower()
    return lang if lang in LANG_NAMES else "a"


def voice_label(name: str) -> str:
    """'af_heart' -> 'Heart (US female)'."""
    stem = name[1:] if name[:1] in LANG_NAMES else name
    nick = stem.split("_", 1)[-1].replace("_", " ").strip().title() or name
    gender = GENDER.get(name[1:2].lower()) if len(name) > 1 else None
    region = LANG_NAMES.get(voice_lang(name), "")
    bits = [b for b in (region, gender) if b]
    return f"{nick} ({', '.join(bits)})" if bits else nick


def list_voices(mdir: Optional[Path] = None) -> dict[str, list[str]]:
    mdir = mdir or model_dir()
    found: dict[str, str] = {}
    for d in voice_dirs(mdir):
        for f in sorted(d.glob("*.pt")):
            found.setdefault(f.stem, str(f))
    grouped: dict[str, list[str]] = {}
    for name in sorted(found):
        grouped.setdefault(voice_lang(name), []).append(name)
    return grouped


def find_voice(name: str, mdir: Optional[Path] = None) -> Path:
    for d in voice_dirs(mdir or model_dir()):
        p = d / f"{name}.pt"
        if p.is_file():
            return p
    raise TTSError(
        f"Voice '{name}' not found in {', '.join(str(d) for d in voice_dirs(mdir or model_dir()))}.\n"
        "Run:  .venv\\Scripts\\python Kokoro-TTS\\download_models.py   (or --list-voices to see what is available)"
    )


def pick_device(pref: str = "auto") -> str:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - broken install
        raise TTSError(f"PyTorch failed to import: {exc}") from exc
    if pref == "cpu":
        return "cpu"
    if pref in ("cuda", "auto") and torch.cuda.is_available():
        return "cuda"
    if pref == "cuda":
        raise TTSError("CUDA was requested but torch.cuda.is_available() is False.")
    return "cpu"


# --------------------------------------------------------------------------- #
# Audio helpers
# --------------------------------------------------------------------------- #
def _as_numpy(audio) -> np.ndarray:
    if audio is None:
        return np.zeros(0, dtype=np.float32)
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    return np.asarray(audio, dtype=np.float32).reshape(-1)


def save_audio(audio: np.ndarray, path: Path) -> Path:
    """Write audio; format comes from the suffix (wav, flac, ogg, mp3)."""
    import soundfile as sf

    audio = _as_numpy(audio)
    path = Path(path).expanduser()
    if not path.suffix:
        path = path.with_suffix(".wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower().lstrip(".") not in AUDIO_FORMATS:
        raise TTSError(f"Unsupported audio format '{path.suffix}'. Use one of: {', '.join(AUDIO_FORMATS)}")
    if path.suffix.lower() == ".mp3" and shutil.which("ffmpeg"):
        # ffmpeg gives noticeably better MP3 quality than libsndfile's default.
        tmp = path.with_suffix(".tmp.wav")
        sf.write(str(tmp), audio, SAMPLE_RATE)
        try:
            subprocess_ffmpeg(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        return path
    try:
        sf.write(str(path), audio, SAMPLE_RATE)
    except Exception:
        if path.suffix.lower() != ".mp3":
            raise
        # Fall back to ffmpeg for MP3 if libsndfile lacks MPEG support.
        tmp = path.with_suffix(".tmp.wav")
        sf.write(str(tmp), audio, SAMPLE_RATE)
        try:
            subprocess_ffmpeg(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    return path


def subprocess_ffmpeg(src: Path, dst: Path) -> None:
    import subprocess

    exe = shutil.which("ffmpeg")
    if not exe:
        raise TTSError("MP3 output needs ffmpeg on PATH (or save as .wav instead).")
    subprocess.run(
        [exe, "-y", "-loglevel", "error", "-i", str(src), "-codec:a", "libmp3lame", "-qscale:a", "2", str(dst)],
        check=True,
    )


def play_audio(audio: np.ndarray, block: bool = True) -> None:
    """Play through the default Windows output device."""
    try:
        import winsound
    except ImportError:
        print("Playback is only supported on Windows; audio saved to file instead.", file=sys.stderr)
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkstemp(prefix="kokoro_", suffix=".wav", dir=OUTPUT_DIR)[1])
    try:
        save_audio(audio, tmp)
        winsound.PlaySound(str(tmp), winsound.SND_FILENAME | (0 if block else winsound.SND_ASYNC))
    finally:
        if block:
            tmp.unlink(missing_ok=True)


def stop_playback() -> None:
    try:
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def clean_text(text: str) -> str:
    """Normalise line endings and collapse noisy whitespace before synthesis."""
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class KokoroEngine:
    """Loads Kokoro once and keeps the model warm on the chosen device."""

    def __init__(self, device: str = "auto", mdir: Optional[str] = None, log: Optional[Callable[[str], None]] = None):
        self._log = log or (lambda _msg: None)
        self.dir = model_dir(mdir)
        self.config_path = self.dir / "config.json"
        weights = sorted(self.dir.glob("kokoro-*.pth"))
        if not self.config_path.is_file() or not weights:
            raise TTSError(
                f"Model files are missing in {self.dir}.\n"
                "Run:  .venv\\Scripts\\python Kokoro-TTS\\download_models.py"
            )
        self.weights_path = weights[0]
        self.device = pick_device(device)
        self._pipelines: dict[str, object] = {}
        self._lock = threading.RLock()
        self._load_model()

    # -- model ------------------------------------------------------------- #
    def _load_model(self) -> None:
        import torch
        from kokoro import KModel

        t0 = time.time()
        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        model = KModel(repo_id=f"local/{self.dir.name}", config=cfg, model=str(self.weights_path))
        model = model.to(self.device).eval()
        for p in model.parameters():
            p.requires_grad_(False)
        self.model = model
        self._log(f"Kokoro loaded on {self.device.upper()} in {time.time() - t0:.1f}s")

    def pipeline(self, lang: str):
        """Return (and cache) a KPipeline for a language code."""
        lang = lang.lower()[:1]
        if lang not in LANG_NAMES:
            raise TTSError(f"Unknown language code '{lang}'. Supported: {', '.join(sorted(LANG_NAMES))}")
        with self._lock:
            pipe = self._pipelines.get(lang)
            if pipe is None:
                from kokoro import KPipeline

                try:
                    pipe = KPipeline(
                        lang_code=lang,
                        repo_id=f"local/{self.dir.name}",
                        model=self.model,
                        device=self.device,
                    )
                except ImportError as exc:
                    extra = {"j": "misaki[ja]", "z": "misaki[zh]"}.get(lang, "misaki[en]")
                    raise TTSError(
                        f"Language '{LANG_NAMES[lang]}' needs extra packages ({exc}).\n"
                        f"Install with:  .venv\\Scripts\\python -m pip install \"{extra}\""
                    ) from exc
                self._pipelines[lang] = pipe
            return pipe

    def _preload_voice(self, pipe, voice: str) -> None:
        """Load voice packs from disk so the pipeline does not fetch them."""
        import torch

        for name in voice.split(","):
            name = name.strip()
            if not name or name in pipe.voices:
                continue
            pack = torch.load(find_voice(name, self.dir), map_location="cpu", weights_only=True)
            pipe.voices[name] = pack

    # -- synthesis --------------------------------------------------------- #
    def synth(
        self,
        text: str,
        voice: str = DEFAULT_VOICE,
        speed: float = 1.0,
        lang: Optional[str] = None,
        progress: Optional[Callable[[int, float], None]] = None,
        cancel: Optional[threading.Event] = None,
    ) -> np.ndarray:
        """Synthesize text and return one float32 NumPy array at 24 kHz."""
        text = clean_text(text)
        if not text:
            return np.zeros(0, dtype=np.float32)
        lang = (lang or voice_lang(voice)).lower()[:1]
        pipe = self.pipeline(lang)
        self._preload_voice(pipe, voice)
        chunks: list[np.ndarray] = []
        generated = 0
        with self._lock:
            for index, result in enumerate(pipe(text, voice=voice, speed=float(speed))):
                if cancel is not None and cancel.is_set():
                    break
                audio = _as_numpy(result.audio)
                if audio.size == 0:
                    continue
                chunks.append(audio)
                generated += audio.size
                if progress:
                    progress(index, generated / SAMPLE_RATE)
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def warmup(self, voice: str = DEFAULT_VOICE) -> None:
        """Run one short synthesis so the first real request is fast."""
        try:
            self.synth("Ready.", voice=voice, speed=1.0)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_text(args) -> str:
    if args.file:
        if args.file == "-":
            return sys.stdin.read()
        return Path(args.file).expanduser().read_text(encoding="utf-8-sig")
    if args.text:
        return " ".join(args.text)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _default_output(fmt: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return OUTPUT_DIR / f"speech_{stamp}.{fmt}"


def _print_voices(mdir: Path) -> None:
    grouped = list_voices(mdir)
    if not grouped:
        print(f"No voice files found in {mdir / 'voices'} - run Kokoro-TTS\\download_models.py")
        return
    print(f"Kokoro voices ({sum(len(v) for v in grouped.values())} found in {mdir}):\n")
    for lang in sorted(grouped):
        print(f"{LANG_NAMES.get(lang, lang)}  [{lang}]")
        for name in grouped[lang]:
            print(f"  {name:<12} {voice_label(name)}")
        print()
    print("Default: af_heart (best overall). Mix voices with 'af_heart,af_bella'.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tts.py",
        description="Kokoro-82M local text-to-speech (CUDA accelerated).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  python tts.py "Hello from Kokoro."\n'
            '  python tts.py "Hello!" -v bm_george -s 0.95 --play\n'
            "  python tts.py -f chapter.txt -o output/chapter.mp3\n"
            "  python tts.py --list-voices\n"
            "  python tts.py --selftest"
        ),
    )
    p.add_argument("text", nargs="*", help="text to speak (or omit to read stdin)")
    p.add_argument("-f", "--file", help="read text from this UTF-8 file ('-' = stdin)")
    p.add_argument("-o", "--out", help="output file (.wav .flac .ogg .mp3); default output/speech_<time>.wav")
    p.add_argument("-v", "--voice", default=DEFAULT_VOICE, help=f"voice name (default {DEFAULT_VOICE})")
    p.add_argument("-s", "--speed", type=float, default=1.0, help="speaking speed 0.5-2.0 (default 1.0)")
    p.add_argument("-l", "--lang", choices=sorted(LANG_NAMES), help="language code (default: inferred from voice)")
    p.add_argument("-d", "--device", choices=("auto", "cuda", "cpu"), default="auto", help="compute device (default auto)")
    p.add_argument("--model-dir", help="alternative model folder (e.g. models\\Kokoro-82M-v1.1-zh)")
    p.add_argument("--format", choices=AUDIO_FORMATS, default="wav", help="format when -o has no suffix (default wav)")
    p.add_argument("--play", action="store_true", help="play the result through the speakers")
    p.add_argument("--list-voices", action="store_true", help="show available voices and exit")
    p.add_argument("--selftest", action="store_true", help="synth a test line, report speed, then exit")
    p.add_argument("-q", "--quiet", action="store_true", help="only print the output path")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    mdir = model_dir(args.model_dir)

    if args.list_voices:
        _print_voices(mdir)
        return 0

    selftest = args.selftest
    text = "Kokoro is ready. This sentence is a speed test." if selftest else _read_text(args)
    if not text.strip():
        build_parser().print_help()
        print("\nNo text given. Pass text, use -f FILE, or pipe text on stdin.")
        return 2

    speed = min(max(float(args.speed), 0.5), 2.0)
    try:
        engine = KokoroEngine(args.device, args.model_dir, log=(lambda m: None if args.quiet else print(m, file=sys.stderr)))
        started = time.perf_counter()
        audio = engine.synth(text, voice=args.voice, speed=speed, lang=args.lang)
        elapsed = time.perf_counter() - started
        if selftest:
            # Discard the cold-start pass (kernel autotune) before timing.
            engine.warmup(args.voice)
            started = time.perf_counter()
            audio = engine.synth(text, voice=args.voice, speed=speed, lang=args.lang)
            elapsed = time.perf_counter() - started
    except TTSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130

    if audio.size == 0:
        print("error: nothing was synthesized (text may contain no speakable characters).", file=sys.stderr)
        return 1

    duration = audio.size / SAMPLE_RATE
    if args.out:
        out = Path(args.out).expanduser()
        if not out.suffix:
            out = out.with_suffix("." + args.format)
    elif selftest:
        out = OUTPUT_DIR / "_selftest.wav"
    else:
        out = _default_output(args.format)
    try:
        out = save_audio(audio, out)
    except TTSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"{args.voice} on {engine.device}: {duration:.2f}s audio -> {out}", file=sys.stderr)
        if selftest:
            rtf = duration / elapsed if elapsed else 0
            print(
                f"self-test passed: {elapsed:.2f}s to generate {duration:.2f}s "
                f"({rtf:.0f}x realtime, {audio.size} samples @ {SAMPLE_RATE} Hz)",
                file=sys.stderr,
            )
    print(out)

    if args.play:
        try:
            play_audio(audio)
        except KeyboardInterrupt:
            stop_playback()
    return 0


if __name__ == "__main__":
    sys.exit(main())