#!/usr/bin/env python
"""Fetch (or re-fetch) the Kokoro model files into the repository's models folder.

    .venv\\Scripts\\python Kokoro-TTS\\download_models.py          # v1.0 (default)
    .venv\\Scripts\\python Kokoro-TTS\\download_models.py --zh     # also Mandarin v1.1-zh
    .venv\\Scripts\\python Kokoro-TTS\\download_models.py --check  # verify what is on disk

Set KOKORO_MODELS_DIR to use a different folder.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODELS = Path(os.environ.get("KOKORO_MODELS_DIR", ROOT / "models")).expanduser()
os.environ.setdefault("HF_HOME", str(MODELS / "hf"))

REPOS = {
    "v1.0": ("hexgrad/Kokoro-82M", "Kokoro-82M"),
    "zh": ("hexgrad/Kokoro-82M-v1.1-zh", "Kokoro-82M-v1.1-zh"),
}


def human(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} GB"


def check() -> bool:
    ok = True
    for label, (_repo, folder) in REPOS.items():
        d = MODELS / folder
        weights = sorted(d.glob("kokoro-*.pth"))
        voices = sorted((d / "voices").glob("*.pt"))
        if weights and (d / "config.json").is_file():
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            print(f"[ok] {label:<4} {d}  {len(voices)} voices, {human(size)}")
        else:
            if label == "v1.0":
                ok = False
            print(f"[--] {label:<4} not installed in {d}")
    return ok


def fetch(key: str) -> None:
    from huggingface_hub import snapshot_download

    repo, folder = REPOS[key]
    dest = MODELS / folder
    print(f"Downloading {repo} -> {dest}")
    snapshot_download(
        repo_id=repo,
        local_dir=str(dest),
        allow_patterns=["config.json", "kokoro-*.pth", "voices/*.pt"],
        max_workers=8,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zh", action="store_true", help="also download the Mandarin v1.1-zh model")
    ap.add_argument("--check", action="store_true", help="only report what is installed")
    ap.add_argument("--all", action="store_true", help="download every supported model")
    args = ap.parse_args()

    if not check() and not args.check:
        fetch("v1.0")
    if (args.zh or args.all) and not args.check:
        fetch("zh")
    if not args.check:
        print()
        check()
    return 0


if __name__ == "__main__":
    sys.exit(main())