#!/usr/bin/env python
"""Build the project logo assets and browser-extension icons.

Requires Pillow (development only):
    python -m pip install pillow
    python tools/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS = ROOT / "extension" / "icons"

# Region of assets/logo.jpg that contains the emblem (the "P" + book).
EMBLEM_BOX = (250, 0, 1010, 720)
CANVAS = 1024
RADIUS = 230


def build() -> None:
    logo = Image.open(ASSETS / "logo.jpg").convert("RGB")
    logo.save(ASSETS / "logo.png", optimize=True)

    emblem = logo.crop(EMBLEM_BOX)
    background = logo.getpixel((6, 6))

    canvas = Image.new("RGB", (CANVAS, CANVAS), background)
    scale = min(CANVAS * 0.92 / emblem.width, CANVAS * 0.92 / emblem.height)
    scaled = emblem.resize(
        (max(1, int(emblem.width * scale)), max(1, int(emblem.height * scale))),
        Image.LANCZOS,
    )
    canvas.paste(
        scaled,
        ((CANVAS - scaled.width) // 2, (CANVAS - scaled.height) // 2),
    )

    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, CANVAS - 1, CANVAS - 1], radius=RADIUS, fill=255
    )
    icon = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    icon.paste(canvas, (0, 0), mask)
    icon.save(ASSETS / "logo_icon.png", optimize=True)

    ICONS.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        icon.resize((size, size), Image.LANCZOS).save(ICONS / f"icon{size}.png")

    print(f"wrote {ASSETS / 'logo.png'}")
    print(f"wrote {ASSETS / 'logo_icon.png'}")
    for size in (16, 48, 128):
        print(f"wrote {ICONS / f'icon{size}.png'}")


if __name__ == "__main__":
    build()