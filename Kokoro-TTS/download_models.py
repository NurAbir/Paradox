#!/usr/bin/env python
"""Fetch, verify and report the Kokoro model files.

The model weights are large (about 330 MB) and are intentionally not stored in
the repository. This script downloads them from the Hugging Face Hub into the
repository's ``models`` folder and checks the published SHA-256 hashes, so a
truncated or altered download is caught immediately.

    .venv\\Scripts\\python Kokoro-TTS\\download_models.py              # v1.0 (default)
    .venv\\Scripts\\python Kokoro-TTS\\download_models.py --zh         # also Mandarin v1.1-zh
    .venv\\Scripts\\python Kokoro-TTS\\download_models.py --check      # verify what is on disk
    .venv\\Scripts\\python Kokoro-TTS\\download_models.py --no-verify  # skip hashing

Set ``KOKORO_MODELS_DIR`` to use a different folder.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODELS = Path(os.environ.get("KOKORO_MODELS_DIR", ROOT / "models")).expanduser()
os.environ.setdefault("HF_HOME", str(MODELS / "hf"))

# Hugging Face repositories used by Kokoro. The key is the CLI name and the
# value is (repo_id, local folder name).
REPOS = {
    "v1.0": ("hexgrad/Kokoro-82M", "Kokoro-82M"),
    "zh": ("hexgrad/Kokoro-82M-v1.1-zh", "Kokoro-82M-v1.1-zh"),
}

# SHA-256 of the canonical v1.0 release files. These are fixed, published
# artifacts, so a mismatch means the download was corrupted or altered.
# Only the files required for the default install are listed.
KNOWN_SHA256 = {
    "Kokoro-82M/config.json": "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
    "Kokoro-82M/kokoro-v1_0.pth": "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4",
}


def human(nbytes: int) -> str:
    """Return a compact human-readable size such as ``339.0 MB``."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} GB"


def sha256(path: Path) -> str:
    """Hash a file in 1 MB blocks so a 330 MB weight file stays memory-light."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def installed(folder: str) -> bool:
    """True when a model folder has both the weights and a config file."""
    d = MODELS / folder
    return bool(sorted(d.glob("kokoro-*.pth"))) and (d / "config.json").is_file()


def verify() -> bool:
    """Check every known file that is present.

    Missing files are ignored here because ``check()`` already reports them;
    this function only answers "are the files we do have authentic?".
    """
    ok = True
    for rel, expected in KNOWN_SHA256.items():
        path = MODELS / rel
        if not path.is_file():
            continue
        actual = sha256(path)
        if actual.lower() == expected.lower():
            print(f"[ok] sha256 {rel}")
        else:
            ok = False
            print(f"[!!] sha256 mismatch for {rel}")
            print(f"     expected {expected}")
            print(f"     actual   {actual}")
    return ok


def check(verify_hashes: bool = True) -> bool:
    """Print what is installed and return True when the default model is usable."""
    ok = True
    for label, (_repo, folder) in REPOS.items():
        d = MODELS / folder
        if installed(folder):
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            voices = len(list((d / "voices").glob("*.pt")))
            print(f"[ok] {label:<4} {d}  {voices} voices, {human(size)}")
        else:
            if label == "v1.0":
                ok = False
            print(f"[--] {label:<4} not installed in {d}")
    if verify_hashes and not verify():
        ok = False
    return ok


def fetch(key: str) -> None:
    """Download one model repository into its local folder.

    ``snapshot_download`` resumes partial downloads, so re-running after a
    dropped connection only fetches the missing files.
    """
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
    ap = argparse.ArgumentParser(description="Download and verify the Kokoro model files.")
    ap.add_argument("--zh", action="store_true", help="also download the Mandarin v1.1-zh model")
    ap.add_argument("--check", action="store_true", help="only report what is installed")
    ap.add_argument("--all", action="store_true", help="download every supported model")
    ap.add_argument("--no-verify", action="store_true", help="do not check SHA-256 hashes")
    args = ap.parse_args()

    if args.check:
        return 0 if check(verify_hashes=not args.no_verify) else 1

    # Skip the default download only when the required files already exist.
    if not check(verify_hashes=False):
        fetch("v1.0")
    if args.zh or args.all:
        fetch("zh")

    print()
    return 0 if check(verify_hashes=not args.no_verify) else 1


if __name__ == "__main__":
    sys.exit(main())