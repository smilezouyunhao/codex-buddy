#!/usr/bin/env python3
"""Convert six generated state illustrations into M5GFX RGB565 sprites."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STATES_DIR = ROOT / "assets/rabbit-animation/pixel/states"
RAW_DIR = STATES_DIR / "raw"
PNG_DIR = STATES_DIR / "72x72"
OUTPUT = ROOT / "rabbit_bitmaps.h"

SIZE = 72
SPRITE_MARGIN = 3
TRANSPARENT_RGB = (255, 0, 255)
BACKGROUND_RGB = (220, 241, 221)
BACKGROUND_DISTANCE = 24

# A deliberately small screen palette reads better than hundreds of subtly
# different generated colors after RGB565 conversion.
PALETTE = (
    (52, 27, 25),    # deep brown outline / eyes
    (105, 60, 51),   # warm brown edge
    (255, 250, 239), # warm white fur
    (232, 214, 199), # fur shadow
    (255, 132, 154), # inner ear / cheek
    (218, 83, 111),  # dark pink accent
    (255, 213, 92),  # success sparkle
)

STATES = ("sleep", "idle", "working", "attention", "done", "error")


def rgb565(red: int, green: int, blue: int) -> int:
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def is_background(pixel: tuple[int, int, int]) -> bool:
    distance = sum(abs(channel - background) for channel, background in zip(pixel, BACKGROUND_RGB))
    red, green, blue = pixel
    return distance < BACKGROUND_DISTANCE or (green > red and green > blue)


def nearest_palette_color(pixel: tuple[int, int, int]) -> tuple[int, int, int]:
    red, green, blue = pixel
    brightness = red + green + blue
    if red - green > 25 and green - blue > 60:
        return PALETTE[6]
    if red - green > 40 and blue - green > 8:
        return PALETTE[5] if red < 235 else PALETTE[4]
    if brightness < 300:
        return PALETTE[0]
    if brightness < 560:
        return PALETTE[1]
    if brightness < 700:
        return PALETTE[3]
    return PALETTE[2]


def convert_state(state: str) -> tuple[list[int], Image.Image]:
    source = Image.open(RAW_DIR / f"{state}.png").convert("RGB")
    mask = Image.new("1", source.size)
    mask.putdata([0 if is_background(pixel) else 1 for pixel in source.getdata()])
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError(f"{state} does not contain a rabbit")

    cropped = source.crop(bounds)
    available = SIZE - SPRITE_MARGIN * 2
    scale = min(available / cropped.width, available / cropped.height)
    target_size = (
        max(1, round(cropped.width * scale)),
        max(1, round(cropped.height * scale)),
    )
    cropped = cropped.resize(target_size, Image.Resampling.NEAREST)

    sprite = Image.new("RGB", (SIZE, SIZE), TRANSPARENT_RGB)
    x = (SIZE - cropped.width) // 2
    y = (SIZE - cropped.height) // 2
    sprite.paste(cropped, (x, y))

    transparent = rgb565(*TRANSPARENT_RGB)
    pixels = []
    png = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    png_pixels = []
    for pixel in sprite.getdata():
        if pixel == TRANSPARENT_RGB or is_background(pixel):
            pixels.append(transparent)
            png_pixels.append((0, 0, 0, 0))
        else:
            color = nearest_palette_color(pixel)
            pixels.append(rgb565(*color))
            png_pixels.append((*color, 255))
    png.putdata(png_pixels)
    return pixels, png


def format_array(name: str, pixels: list[int]) -> str:
    rows = []
    for offset in range(0, len(pixels), 16):
        values = ", ".join(f"0x{pixel:04X}" for pixel in pixels[offset : offset + 16])
        rows.append(f"  {values},")
    return f"static const uint16_t rabbit_{name}[RABBIT_PIXEL_COUNT] PROGMEM = {{\n" + "\n".join(rows) + "\n};\n"


def main() -> None:
    sections = [
        "#pragma once",
        "",
        "#include <Arduino.h>",
        "",
        f"constexpr int RABBIT_WIDTH = {SIZE};",
        f"constexpr int RABBIT_HEIGHT = {SIZE};",
        "constexpr int RABBIT_PIXEL_COUNT = RABBIT_WIDTH * RABBIT_HEIGHT;",
        f"constexpr uint16_t RABBIT_TRANSPARENT = 0x{rgb565(*TRANSPARENT_RGB):04X};",
        "",
    ]
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    for state in STATES:
        pixels, png = convert_state(state)
        png.save(PNG_DIR / f"{state}.png")
        sections.append(format_array(state, pixels))

    sections.extend(
        [
            "static const uint16_t* const rabbit_bitmaps[] = {",
            "  rabbit_sleep, rabbit_idle, rabbit_working,",
            "  rabbit_attention, rabbit_done, rabbit_error,",
            "};",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(sections), encoding="utf-8")


if __name__ == "__main__":
    main()
