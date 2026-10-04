#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow"]
# ///

# ─── How to run ───
# python3 make_illustrative.py

"""Write a small illustrative chart. It is not a measurement."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parent.parent / "examples" / "illustrative.png"


def main() -> None:
    """Draw fixed bars and a label. No data file is read."""
    image = Image.new("RGB", (640, 360), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 616, 336), outline=(180, 180, 180))
    bars = ((80, 220, 70, 180, 230), (180, 160, 70, 120, 180), (280, 120, 70, 90, 150))
    for left, top, width, height, shade in bars:
        draw.rectangle((left, top, left + width, top + height), fill=(shade, shade, shade))
    draw.text((80, 40), "Illustrative, not measured", fill=(40, 40, 40))
    image.save(OUTPUT)
    print(f"FIXTURE {OUTPUT}")


if __name__ == "__main__":
    main()
