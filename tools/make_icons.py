#!/usr/bin/env python
"""Build the project logo assets and browser-extension icons.

The artwork in ``assets/logo.jpg`` is a single square image with two parts:
the emblem (the "P" and the book) on top and the "Paradox" wordmark below it.
This script

* saves the untouched artwork as ``assets/logo.png``,
* crops just the emblem, centres it on a square canvas and rounds the corners
  to produce ``assets/logo_icon.png`` (used by the README and the store), and
* derives the 16 / 48 / 128 px browser-extension icons from that emblem.

The emblem is located automatically, so re-running the script after the
artwork changes keeps every size centred and uncropped.

Requires Pillow (development only):

    python -m pip install pillow
    python tools/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS = ROOT / "extension" / "icons"

CANVAS = 1024          # size of the rounded icon canvas, in pixels
FILL = 0.90            # emblem occupies this fraction of the canvas
RADIUS = 224           # corner radius of the rounded icon
THRESHOLD = 24         # per-pixel difference that counts as "not background"
ICON_SIZES = (16, 48, 128)


def foreground_mask(image: Image.Image) -> Image.Image:
    """Return a binary mask of everything that differs from the background.

    The artwork sits on a near-uniform near-black background, so a pixel is
    treated as foreground when it differs from the corner colour by more than
    ``THRESHOLD``. That avoids relying on the exact background value.
    """
    background = image.getpixel((6, 6))
    flat = Image.new("RGB", image.size, background)
    diff = ImageChops.difference(image, flat).convert("L")
    return diff.point(lambda p: 255 if p > THRESHOLD else 0)


def emblem_box(image: Image.Image, mask: Image.Image) -> tuple[int, int, int, int]:
    """Return the bounding box of the emblem, excluding the wordmark below it.

    The wordmark is the lowest block of artwork and is separated from the
    emblem by a blank horizontal band. The emblem is everything above the
    widest blank band found in the lower part of the image.
    """
    full = mask.getbbox()
    if full is None:  # empty image: fall back to the whole canvas
        return (0, 0, image.width, image.height)

    x0, y0, x1, y1 = full
    rows = [
        mask.crop((x0, y, x1, y + 1)).getbbox() is not None
        for y in range(y0, y1)
    ]

    # Only look below the middle: the emblem/wordmark gap is near the bottom,
    # while any blank rows inside the emblem sit in the upper half.
    search_from = int(len(rows) * 0.45)
    best_len = 0
    best_start = None
    run_start = None
    for i in range(search_from, len(rows)):
        if not rows[i]:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            if i - run_start > best_len:
                best_len = i - run_start
                best_start = run_start
            run_start = None
    if run_start is not None and len(rows) - run_start > best_len:
        best_len = len(rows) - run_start
        best_start = run_start

    if best_start is None or best_len < 4:  # no clear gap: treat it all as emblem
        return full

    emblem_bottom = y0 + best_start
    box = mask.crop((0, 0, image.width, emblem_bottom)).getbbox()
    return box if box is not None else full


def build() -> None:
    logo = Image.open(ASSETS / "logo.jpg").convert("RGB")
    logo.save(ASSETS / "logo.png", optimize=True)

    mask = foreground_mask(logo)
    box = emblem_box(logo, mask)
    emblem = logo.crop(box)
    background = logo.getpixel((6, 6))

    # Fit the emblem inside the canvas with equal padding on all sides.
    scale = min(CANVAS * FILL / emblem.width, CANVAS * FILL / emblem.height)
    scaled = emblem.resize(
        (max(1, round(emblem.width * scale)), max(1, round(emblem.height * scale))),
        Image.LANCZOS,
    )

    canvas = Image.new("RGB", (CANVAS, CANVAS), background)
    canvas.paste(
        scaled,
        ((CANVAS - scaled.width) // 2, (CANVAS - scaled.height) // 2),
    )

    rounded = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(rounded).rounded_rectangle(
        [0, 0, CANVAS - 1, CANVAS - 1], radius=RADIUS, fill=255
    )
    icon = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    icon.paste(canvas, (0, 0), rounded)
    icon.save(ASSETS / "logo_icon.png", optimize=True)

    ICONS.mkdir(parents=True, exist_ok=True)
    for size in ICON_SIZES:
        icon.resize((size, size), Image.LANCZOS).save(ICONS / f"icon{size}.png")

    print(f"emblem box: {box}  ({emblem.width}x{emblem.height})")
    print(f"wrote {ASSETS / 'logo.png'}")
    print(f"wrote {ASSETS / 'logo_icon.png'}")
    for size in ICON_SIZES:
        print(f"wrote {ICONS / f'icon{size}.png'}")


if __name__ == "__main__":
    build()
