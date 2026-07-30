#!/usr/bin/env python3
"""Generate all normal and AOD assets for the 212 x 520 binary watchface."""

from __future__ import annotations

import datetime as dt
import shutil
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_FILE = PROJECT_DIR / "binary.fprj"
ASSET_DIRS = (PROJECT_DIR / "images", PROJECT_DIR / "assets")

# Xiaomi Band 10 display. Mi Create coordinates start at the top-left:
# x grows to the right (0..211), y grows downward (0..519).
SCREEN_WIDTH = 212
SCREEN_HEIGHT = 520
# FaceProject DeviceType is a compiler ID, not the display width. Mi Create
# maps Xiaomi Band 10 to ID 466.
DEVICE_TYPE = "466"

# Main layout:
# 8 px | hour columns | 20 px group gap | minute columns | 8 px
DIGIT_WIDTH = 46
DIGIT_HEIGHT = 260
DOT_SIZE = 44
ROW_STEP = 72
TIME_Y = 108
HOURS_X = 2
MINUTES_X = 116
DIGIT_SPACING = 0
WEIGHTS = (8, 4, 2, 1)

DATE_Y = 404
WEEKDAY_WIDTH = 64
WEEKDAY_HEIGHT = 30
WEEKDAY_FONT_SIZE = 24
DATE_DIGIT_WIDTH = 18
DATE_DIGIT_HEIGHT = 30
DATE_FONT_SIZE = 24
DATE_SPACING = 0
HEADER_GAP = 6
HEADER_WIDTH = (
    2 * DATE_DIGIT_WIDTH + HEADER_GAP + WEEKDAY_WIDTH
    + HEADER_GAP + 2 * DATE_DIGIT_WIDTH
)
HEADER_X = (SCREEN_WIDTH - HEADER_WIDTH) // 2

BATTERY_WIDTH = 112
BATTERY_HEIGHT = 30
BATTERY_X = (SCREEN_WIDTH - BATTERY_WIDTH) // 2
BATTERY_Y = 462  # 28 px clear below it
FONT_FILE = PROJECT_DIR / "Lato-Black.ttf"

SAMPLE_SCALE = 4


class Bitmap:
    """Small dependency-free RGBA bitmap with basic antialiased primitives."""

    def __init__(
        self, width: int, height: int, color: tuple[int, int, int, int]
    ) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(color * (width * height))

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        offset = (y * self.width + x) * 4
        source_alpha = color[3] / 255
        if source_alpha >= 1:
            self.pixels[offset : offset + 4] = bytes(color)
            return
        destination = self.pixels[offset : offset + 4]
        inverse = 1 - source_alpha
        self.pixels[offset : offset + 4] = bytes(
            (
                round(color[0] * source_alpha + destination[0] * inverse),
                round(color[1] * source_alpha + destination[1] * inverse),
                round(color[2] * source_alpha + destination[2] * inverse),
                round(255 * (source_alpha + destination[3] / 255 * inverse)),
            )
        )

    def draw_dot(self, x: int, y: int, filled: bool, dim: bool = False) -> None:
        inset = 2
        radius = (DOT_SIZE - 2 * inset - 1) / 2
        center_x = x + inset + radius
        center_y = y + inset + radius
        color_value = 156 if dim else 255
        for pixel_y in range(y, y + DOT_SIZE):
            for pixel_x in range(x, x + DOT_SIZE):
                covered = 0
                for sample_y in range(SAMPLE_SCALE):
                    for sample_x in range(SAMPLE_SCALE):
                        dx = pixel_x + (sample_x + 0.5) / SAMPLE_SCALE - center_x
                        dy = pixel_y + (sample_y + 0.5) / SAMPLE_SCALE - center_y
                        distance = dx * dx + dy * dy
                        if distance <= radius * radius and (
                            filled or distance >= (radius - 3) ** 2
                        ):
                            covered += 1
                if covered:
                    self.set_pixel(
                        pixel_x,
                        pixel_y,
                        (color_value, color_value, color_value,
                         round(255 * covered / SAMPLE_SCALE**2)),
                    )

    def draw_oval_outline(
        self, x: int, y: int, width: int, height: int, thickness: int = 2
    ) -> None:
        radius = height / 2
        for py in range(y, y + height):
            for px in range(x, x + width):
                nearest_x = min(max(px + 0.5, x + radius), x + width - radius)
                dx = px + 0.5 - nearest_x
                dy = py + 0.5 - (y + radius)
                distance = (dx * dx + dy * dy) ** 0.5
                if radius - thickness <= distance <= radius:
                    self.set_pixel(px, py, (255, 255, 255, 255))

    def draw_rect(
        self, x: int, y: int, width: int, height: int,
        color: tuple[int, int, int, int],
    ) -> None:
        for py in range(y, y + height):
            for px in range(x, x + width):
                self.set_pixel(px, py, color)

    def blit(self, source: "Bitmap", x: int, y: int) -> None:
        for sy in range(source.height):
            for sx in range(source.width):
                offset = (sy * source.width + sx) * 4
                self.set_pixel(x + sx, y + sy, tuple(source.pixels[offset:offset + 4]))

    def save(self, path: Path) -> None:
        def chunk(kind: bytes, data: bytes) -> bytes:
            payload = kind + data
            return (
                struct.pack(">I", len(data))
                + payload
                + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
            )

        scanlines = b"".join(
            b"\0" + self.pixels[y * self.width * 4 : (y + 1) * self.width * 4]
            for y in range(self.height)
        )
        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 6, 0, 0, 0)
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(scanlines, level=9))
            + chunk(b"IEND", b"")
        )


def make_text_bitmap(
    text: str, width: int, height: int, font_size: int, dim: bool = False,
    font_file: str | Path = FONT_FILE,
) -> Bitmap:
    """Rasterize centered text with the configured font."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_file), font_size)
    box = draw.textbbox((0, 0), text, font=font)
    x = (width - (box[2] - box[0])) / 2 - box[0]
    y = (height - (box[3] - box[1])) / 2 - box[1]
    value = 156 if dim else 255
    draw.text((x, y), text, font=font, fill=(value, value, value, 255))
    bitmap = Bitmap(width, height, (0, 0, 0, 0))
    bitmap.pixels[:] = image.tobytes()
    return bitmap


def draw_digit(bitmap: Bitmap, digit: int, x: int = 0, y: int = 0,
               dim: bool = False) -> None:
    for row, weight in enumerate(WEIGHTS):
        bitmap.draw_dot(x, y + row * ROW_STEP, bool(digit & weight), dim)


def make_background() -> Bitmap:
    return Bitmap(SCREEN_WIDTH, SCREEN_HEIGHT, (0, 0, 0, 255))


def make_colon(dim: bool = False) -> Bitmap:
    colon = Bitmap(10, 70, (0, 0, 0, 0))
    value = 156 if dim else 255
    for center_y in (14, 56):
        for y in range(70):
            for x in range(10):
                if (x - 4.5) ** 2 + (y - center_y) ** 2 <= 20.25:
                    colon.set_pixel(x, y, (value, value, value, 255))
    return colon


def make_battery(state: int) -> Bitmap:
    """Render one of six capsule-loader states (0..5)."""
    battery = Bitmap(BATTERY_WIDTH, BATTERY_HEIGHT, (0, 0, 0, 0))
    battery.draw_oval_outline(0, 0, BATTERY_WIDTH, BATTERY_HEIGHT, 2)
    state = max(0, min(5, state))
    if state == 0:
        return battery

    # Match the outline thickness so the fill touches its inner edge.
    inset = 2
    inner_width = BATTERY_WIDTH - 2 * inset
    inner_height = BATTERY_HEIGHT - 2 * inset
    fill_limit = inset + round(inner_width * state / 5)
    radius = inner_height / 2
    for y in range(inset, BATTERY_HEIGHT - inset):
        for x in range(inset, fill_limit):
            nearest_x = min(max(x + 0.5, inset + radius),
                            inset + inner_width - radius)
            dx = x + 0.5 - nearest_x
            dy = y + 0.5 - (inset + radius)
            if dx * dx + dy * dy <= radius * radius:
                battery.set_pixel(x, y, (255, 255, 255, 255))
    return battery


def generate_assets(directory: Path, aod: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for digit in range(10):
        glyph = Bitmap(DIGIT_WIDTH, DIGIT_HEIGHT, (0, 0, 0, 0))
        draw_digit(glyph, digit, dim=aod)
        glyph.save(directory / f"digit-{digit}.png")

        make_text_bitmap(
            str(digit), DATE_DIGIT_WIDTH, DATE_DIGIT_HEIGHT, DATE_FONT_SIZE, aod
        ).save(directory / f"date-{digit}.png")

    make_background().save(directory / "background.png")
    make_colon(aod).save(directory / "colon.png")
    for weekday in ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"):
        make_text_bitmap(
            weekday, WEEKDAY_WIDTH, WEEKDAY_HEIGHT, WEEKDAY_FONT_SIZE, aod
        ).save(directory / f"weekday-{weekday.lower()}.png")
    if not aod:
        make_text_bitmap("°C", 32, 30, DATE_FONT_SIZE).save(
            directory / "weather-unit.png"
        )
        make_text_bitmap(
            "-", DATE_DIGIT_WIDTH, DATE_DIGIT_HEIGHT, DATE_FONT_SIZE
        ).save(directory / "weather-minus.png")
        make_text_bitmap(
            "--", 2 * DATE_DIGIT_WIDTH, DATE_DIGIT_HEIGHT, DATE_FONT_SIZE
        ).save(
            directory / "weather-unavailable.png"
        )
    if not aod:
        for state in range(6):
            make_battery(state).save(directory / f"battery-state-{state}.png")


def validate_project() -> None:
    root = ET.parse(PROJECT_FILE).getroot()
    screen = root.find("Screen")
    if root.attrib.get("DeviceType") != DEVICE_TYPE or screen is None:
        raise ValueError(
            f"binary.fprj must use Xiaomi Band 10 DeviceType {DEVICE_TYPE}"
        )
    if (
        screen.attrib.get("Width") != str(SCREEN_WIDTH)
        or screen.attrib.get("Height") != str(SCREEN_HEIGHT)
    ):
        raise ValueError("binary.fprj Screen must explicitly be 212 x 520")


def render_preview(path: Path, hour: int, minute: int, battery: int,
                   aod: bool = False) -> None:
    preview = make_background()
    values = (hour // 10, hour % 10, minute // 10, minute % 10)
    xs = (HOURS_X, HOURS_X + DIGIT_WIDTH + DIGIT_SPACING,
          MINUTES_X, MINUTES_X + DIGIT_WIDTH + DIGIT_SPACING)
    for digit, x in zip(values, xs):
        draw_digit(preview, digit, x, TIME_Y, dim=aod)
    preview.blit(make_colon(aod), 101, TIME_Y + 94)

    weekday = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")[
        (dt.date.today().weekday() + 1) % 7
    ]
    preview.blit(
        make_text_bitmap(
            weekday, WEEKDAY_WIDTH, WEEKDAY_HEIGHT, WEEKDAY_FONT_SIZE, aod
        ),
        HEADER_X + 2 * DATE_DIGIT_WIDTH + HEADER_GAP,
        DATE_Y,
    )
    month_x = HEADER_X
    for position, character in enumerate(f"{dt.date.today().month:02d}"):
        preview.blit(
            make_text_bitmap(
                character, DATE_DIGIT_WIDTH, DATE_DIGIT_HEIGHT, DATE_FONT_SIZE, aod
            ),
            month_x + position * DATE_DIGIT_WIDTH,
            DATE_Y,
        )
    date_x = (
        HEADER_X + 2 * DATE_DIGIT_WIDTH + HEADER_GAP
        + WEEKDAY_WIDTH + HEADER_GAP
    )
    for position, character in enumerate(f"{dt.date.today().day:02d}"):
        preview.blit(
            make_text_bitmap(
                character, DATE_DIGIT_WIDTH, DATE_DIGIT_HEIGHT, DATE_FONT_SIZE, aod
            ),
            date_x + position * (DATE_DIGIT_WIDTH + DATE_SPACING),
            DATE_Y,
        )

    if not aod:
        temperature = -1
        weather_x = 72
        for position, character in enumerate(str(temperature)):
            preview.blit(
                make_text_bitmap(
                    character, DATE_DIGIT_WIDTH, DATE_DIGIT_HEIGHT,
                    DATE_FONT_SIZE
                ),
                weather_x + position * DATE_DIGIT_WIDTH,
                54,
            )
        preview.blit(make_text_bitmap("°C", 32, 30, DATE_FONT_SIZE), 108, 54)
        preview.blit(make_battery(round(battery / 20)), BATTERY_X, BATTERY_Y)
    preview.save(path)


def render_readme_preview(source: Path, destination: Path) -> None:
    """Match the Smart Band 10 preview styling used by the watch-face site."""
    output_size = (120, 306)
    with Image.open(source).convert("RGBA") as preview:
        # CSS object-fit: cover: fill 120 x 306 and crop the small overflow.
        scale = max(
            output_size[0] / preview.width,
            output_size[1] / preview.height,
        )
        resized = preview.resize(
            (round(preview.width * scale), round(preview.height * scale)),
            Image.Resampling.LANCZOS,
        )
        left = (resized.width - output_size[0]) // 2
        top = (resized.height - output_size[1]) // 2
        preview = resized.crop(
            (left, top, left + output_size[0], top + output_size[1])
        )

        mask = Image.new("L", output_size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, output_size[0] - 1, output_size[1] - 1),
            radius=64,
            fill=255,
        )
        canvas = Image.new("RGBA", output_size, (0, 0, 0, 0))
        canvas.paste(preview, (0, 0), mask)

    canvas.save(destination)


def main() -> None:
    validate_project()
    for directory in ASSET_DIRS:
        generate_assets(directory)

    aod_images = PROJECT_DIR / "AOD" / "images"
    generate_assets(aod_images, aod=True)
    now = dt.datetime.now()
    render_preview(PROJECT_DIR / "preview.png", now.hour, now.minute, 80)
    render_readme_preview(
        PROJECT_DIR / "preview.png", PROJECT_DIR / "preview-readme.png"
    )
    for directory in ASSET_DIRS:
        shutil.copy2(PROJECT_DIR / "preview.png", directory / "preview.png")
    # Mi Create's compiler requires this exact filename. Version 1.1.1 omits
    # Band 10 from preview_sizes.json, so the editor does not create it.
    shutil.copy2(PROJECT_DIR / "preview.png", PROJECT_DIR / "preview_default.png")
    shutil.copy2(PROJECT_DIR / "preview.png", PROJECT_DIR / "preview_default_large.png")

    render_preview(PROJECT_DIR / "AOD" / "preview.png", now.hour, now.minute, 80, True)
    shutil.copy2(
        PROJECT_DIR / "AOD" / "preview.png",
        PROJECT_DIR / "AOD" / "preview_default.png",
    )

    # Keep AOD's root assets available for Mi Create versions that do not resolve
    # the images/ folder automatically.
    for asset in aod_images.glob("*.png"):
        shutil.copy2(asset, PROJECT_DIR / "AOD" / asset.name)

    print(
        f"Generated 212x520 assets. Preview: {now:%H:%M}, battery 80%. "
        f"Time bounds x=20..192, y={TIME_Y}..{TIME_Y + DIGIT_HEIGHT}; "
        f"battery x={BATTERY_X}..{BATTERY_X + BATTERY_WIDTH}, "
        f"y={BATTERY_Y}..{BATTERY_Y + BATTERY_HEIGHT}."
    )


if __name__ == "__main__":
    main()
