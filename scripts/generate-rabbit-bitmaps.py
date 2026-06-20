#!/usr/bin/env python3
"""Convert six generated state illustrations into M5GFX RGB565 sprites."""

from pathlib import Path
from collections import deque

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
STATES_DIR = ROOT / "assets/rabbit-animation/pixel/states"
RAW_DIR = STATES_DIR / "raw"
PNG_DIR = STATES_DIR / "72x72"
OUTPUT = ROOT / "rabbit_bitmaps.h"

SIZE = 72
LOGICAL_SIZE = 72
SPRITE_MARGIN = 4
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
    dark_neutral = max(pixel) - min(pixel) < 16 and red + green + blue < 360
    return distance < BACKGROUND_DISTANCE or (green > red and green > blue) or dark_neutral


def foreground_mask(source: Image.Image) -> Image.Image:
    """Remove only background-like pixels connected to the image border."""
    width, height = source.size
    pixels = source.load()
    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if not background[index] and is_background(pixels[x, y]):
            background[index] = 1
            queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x > 0:
            enqueue(x - 1, y)
        if x + 1 < width:
            enqueue(x + 1, y)
        if y > 0:
            enqueue(x, y - 1)
        if y + 1 < height:
            enqueue(x, y + 1)

    mask = Image.new("1", source.size)
    mask.putdata([0 if value else 1 for value in background])
    return mask


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


def refine_state_details(state: str, image: Image.Image) -> None:
    """Apply deliberate one-pixel details after scaling to the native grid."""
    dark = (*PALETTE[0], 255)
    pink = (*PALETTE[4], 255)
    clear = (0, 0, 0, 0)
    draw = ImageDraw.Draw(image)

    if state == "sleep":
        draw.rectangle((7, 6, 25, 23), fill=clear)
        draw.rectangle((8, 7, 17, 8), fill=dark)
        draw.rectangle((15, 9, 17, 10), fill=dark)
        draw.rectangle((13, 11, 15, 12), fill=dark)
        draw.rectangle((11, 13, 13, 14), fill=dark)
        draw.rectangle((9, 15, 11, 16), fill=dark)
        draw.rectangle((8, 17, 17, 18), fill=dark)
        draw.point((10, 8), fill=pink)
        draw.point((15, 17), fill=pink)
        draw.rectangle((18, 16, 24, 17), fill=dark)
        draw.rectangle((22, 18, 24, 19), fill=dark)
        draw.rectangle((20, 20, 22, 21), fill=dark)
        draw.rectangle((18, 22, 24, 23), fill=dark)
        draw.point((20, 16), fill=pink)

    if state == "attention":
        draw.rectangle((12, 17, 22, 33), fill=clear)
        draw.rectangle((14, 18, 18, 27), fill=dark)
        draw.rectangle((15, 20, 16, 25), fill=pink)
        draw.rectangle((14, 30, 18, 33), fill=dark)
        draw.rectangle((15, 30, 17, 31), fill=pink)


def convert_state(state: str) -> tuple[list[int], Image.Image]:
    source = Image.open(RAW_DIR / f"{state}.png").convert("RGB")
    mask = foreground_mask(source)
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError(f"{state} does not contain a rabbit")

    keyed = Image.new("RGB", source.size, TRANSPARENT_RGB)
    keyed.paste(source, mask=mask)
    cropped = keyed.crop(bounds)
    # Build on a true 36x36 logical grid. The final 72x72 image is an exact
    # integer 2x enlargement, so every visible pixel is a complete 2x2 block.
    available = LOGICAL_SIZE - SPRITE_MARGIN * 2
    scale = min(available / cropped.width, available / cropped.height)
    target_size = (
        max(1, round(cropped.width * scale)),
        max(1, round(cropped.height * scale)),
    )
    cropped = cropped.resize(target_size, Image.Resampling.NEAREST)

    sprite = Image.new("RGB", (LOGICAL_SIZE, LOGICAL_SIZE), TRANSPARENT_RGB)
    x = (LOGICAL_SIZE - cropped.width) // 2
    y = (LOGICAL_SIZE - cropped.height) // 2
    sprite.paste(cropped, (x, y))

    transparent = rgb565(*TRANSPARENT_RGB)
    pixels = []
    logical_png = Image.new("RGBA", (LOGICAL_SIZE, LOGICAL_SIZE), (0, 0, 0, 0))
    png_pixels = []
    for pixel in sprite.getdata():
        if pixel == TRANSPARENT_RGB:
            pixels.append(transparent)
            png_pixels.append((0, 0, 0, 0))
        else:
            color = nearest_palette_color(pixel)
            pixels.append(rgb565(*color))
            png_pixels.append((*color, 255))
    logical_png.putdata(png_pixels)
    png = logical_png.resize((SIZE, SIZE), Image.Resampling.NEAREST)
    refine_state_details(state, png)
    pixels = [
        transparent if pixel[3] == 0 else rgb565(*pixel[:3])
        for pixel in png.getdata()
    ]
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
