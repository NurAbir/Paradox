#!/usr/bin/env python
"""Generate or verify SHA-256 checksum manifests.

Examples (from the repository root):

    .venv\\Scripts\\python tools\\checksums.py                  # print hashes for git-tracked files
    .venv\\Scripts\\python tools\\checksums.py --write SHA256SUMS
    .venv\\Scripts\\python tools\\checksums.py --check SHA256SUMS
    .venv\\Scripts\\python tools\\checksums.py dist\\Paradox.zip  # hash specific files

The manifest uses the standard ``sha256sum`` format (``<hash>  <path>``), so it
can also be checked with ``sha256sum -c`` on Linux/macOS or ``Get-FileHash`` on
Windows. Files are hashed in binary mode, so line endings matter: hash release
archives rather than a checkout if you need cross-platform results.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    """Hash a file in 1 MB blocks without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tracked_files() -> list[Path]:
    """Return the files git tracks, so ignored model/output data is skipped."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"could not list git files: {exc}")
    return [Path(p.decode("utf-8")) for p in out.split(b"\0") if p]


def manifest(paths: list[Path], skip: Path | None = None) -> list[str]:
    """Build manifest lines for every regular file, sorted by path."""
    lines: list[str] = []
    for path in sorted(paths, key=lambda p: p.as_posix()):
        if skip is not None and path.resolve() == skip.resolve():
            continue
        if not path.is_file():
            continue
        lines.append(f"{sha256(path)}  {path.as_posix()}")
    return lines


def verify(file: Path) -> bool:
    """Check a manifest, printing one line per file. Returns False on any miss."""
    ok = True
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, sep, name = line.partition("  ")
        if not sep:
            print(f"[!!] malformed line: {line}")
            ok = False
            continue
        target = Path(name)
        if not target.is_file():
            print(f"[--] missing {name}")
            ok = False
        elif sha256(target).lower() != digest.lower():
            print(f"[!!] mismatch {name}")
            ok = False
        else:
            print(f"[ok] {name}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate or verify SHA-256 checksums.")
    ap.add_argument("paths", nargs="*", type=Path, help="files to hash (default: git-tracked files)")
    ap.add_argument("--write", type=Path, metavar="FILE", help="write the manifest to FILE")
    ap.add_argument("--check", type=Path, metavar="FILE", help="verify an existing manifest")
    args = ap.parse_args()

    if args.check:
        return 0 if verify(args.check) else 1

    paths = args.paths or tracked_files()
    lines = manifest(paths, skip=args.write)
    text = "\n".join(lines) + ("\n" if lines else "")

    if args.write:
        args.write.write_text(text, encoding="utf-8")
        print(f"wrote {args.write} ({len(lines)} files)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())