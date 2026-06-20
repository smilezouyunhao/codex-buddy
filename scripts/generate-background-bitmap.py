#!/usr/bin/env python3
"""Build the aligned cyber UI background and convert it to RGB565."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/backgrounds/cyber-terminal-source.png"
PREVIEW = ROOT / "assets/backgrounds/cyber-terminal-135x240.png"
OUTPUT = ROOT / "background_bitmap.h"
WIDTH = 135
HEIGHT = 240

SLOTS = (
    (2, 2, 43, 13),      # battery
    (101, 2, 32, 13),    # BLE
    (19, 16, 97, 22),    # state
    (18, 40, 99, 132),   # rabbit chamber
    (17, 164, 101, 22),  # token usage
    (5, 190, 125, 21),   # progress meter
    (17, 214, 101, 22),  # reset countdown
)


def rgb565(red: int, green: int, blue: int) -> int:
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def stepped_box(x: int, y: int, width: int, height: int, inset: int = 0):
    left = x + inset
    top = y + inset
    right = x + width - 1 - inset
    bottom = y + height - 1 - inset
    step = 2 if width >= 20 and height >= 12 else 1
    return (
        (left + step, top),
        (right - step, top),
        (right, top + step),
        (right, bottom - step),
        (right - step, bottom),
        (left + step, bottom),
        (left, bottom - step),
        (left, top + step),
    )


def draw_recessed_slot(draw: ImageDraw.ImageDraw, slot: tuple[int, int, int, int]) -> None:
    x, y, width, height = slot
    draw.polygon(stepped_box(x, y, width, height), fill=(2, 7, 10), outline=(45, 66, 72))
    draw.line(stepped_box(x, y, width, height)[:4], fill=(55, 80, 85), width=1)
    draw.polygon(stepped_box(x, y, width, height, 2), fill=(5, 12, 16), outline=(13, 29, 34))

    # A few fixed hardware pixels make the slots feel built into the terminal.
    if width >= 90:
        draw.line((x + 7, y + 1, x + 15, y + 1), fill=(0, 116, 133), width=1)
        draw.line((x + width - 16, y + height - 2, x + width - 8, y + height - 2), fill=(0, 75, 88), width=1)


def build_background() -> Image.Image:
    image = Image.open(SOURCE).convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
    image = ImageEnhance.Brightness(image).enhance(0.64)
    image = ImageEnhance.Color(image).enhance(0.82)
    draw = ImageDraw.Draw(image)
    for slot in SLOTS:
        draw_recessed_slot(draw, slot)
    return image.quantize(colors=64).convert("RGB")


def main() -> None:
    image = build_background()
    image.save(PREVIEW)

    pixels = [rgb565(*pixel) for pixel in image.get_flattened_data()]
    rows = []
    for offset in range(0, len(pixels), 16):
        values = ", ".join(f"0x{pixel:04X}" for pixel in pixels[offset : offset + 16])
        rows.append(f"  {values},")

    output = "\n".join(
        [
            "#pragma once",
            "",
            "#include <Arduino.h>",
            "",
            f"constexpr int BACKGROUND_WIDTH = {WIDTH};",
            f"constexpr int BACKGROUND_HEIGHT = {HEIGHT};",
            "constexpr int BACKGROUND_PIXEL_COUNT = BACKGROUND_WIDTH * BACKGROUND_HEIGHT;",
            "",
            "static const uint16_t cyber_terminal_background[BACKGROUND_PIXEL_COUNT] PROGMEM = {",
            *rows,
            "};",
            "",
        ]
    )
    OUTPUT.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
