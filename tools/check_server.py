#!/usr/bin/env python
"""Quick check that the local TTS server is up and can make audio.

    .venv\\Scripts\\python tools\\check_server.py
    .venv\\Scripts\\python tools\\check_server.py --speak "Hello there"

Start the server first (Start server.bat).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as res:
        return res.status, res.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8756)
    ap.add_argument("--speak", default="Paradox is online.")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--out", default="tools/_test.wav")
    args = ap.parse_args()

    root = f"http://127.0.0.1:{args.port}"
    print(f"GET {root}/health")
    try:
        status, body = get(f"{root}/health")
    except Exception as exc:
        print(f"  server not reachable: {exc}")
        print("  Start it with  Start server.bat")
        return 1
    info = json.loads(body)
    print(f"  HTTP {status}  {json.dumps(info, indent=2)}")

    payload = json.dumps(
        {"text": args.speak, "voice": args.voice, "speed": args.speed, "format": "wav"}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{root}/tts", data=payload, headers={"Content-Type": "application/json"}
    )
    print(f"POST {root}/tts  ({len(args.speak)} chars)")
    with urllib.request.urlopen(req, timeout=600) as res:
        audio = res.read()
        print(f"  HTTP {res.status}  {res.headers.get('Content-Type')}  {len(audio)} bytes")

    with open(args.out, "wb") as fh:
        fh.write(audio)
    print(f"  saved {args.out}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())