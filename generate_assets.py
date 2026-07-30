#!/usr/bin/env python3
"""Generate the JSON/GMF Binary watchface and its supersampled assets."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "wfDef.json"
IMAGES = ROOT / "images"
IMAGES_AOD = ROOT / "images_aod"
FONT_PATH = ROOT / "Lato-Black.ttf"

WIDTH, HEIGHT = 212, 520
SCALE = 4
TIME_Y = 108
HOURS_X = 2
MINUTES_X = 116
TIME_WIDTH, TIME_HEIGHT = 92, 260
DIGIT_WIDTH = 46
DOT_SIZE = 44
ROW_STEP = 72
DATE_Y = 404
MONTH_X, WEEKDAY_X, DAY_X = 32, 74, 144
DATE_WIDTH, WEEKDAY_WIDTH = 36, 64
INFO_HEIGHT = 30
BATTERY_X, BATTERY_Y = 50, 462
BATTERY_WIDTH, BATTERY_HEIGHT = 112, 30
WEATHER_X, WEATHER_Y = 72, 54
WEATHER_DIGIT_WIDTH = 18
WEATHER_UNIT_X = 108
WEIGHTS = (8, 4, 2, 1)

WHITE = (255, 255, 255, 255)
DIM = (156, 156, 156, 255)
TRANSPARENT = (0, 0, 0, 0)
BLACK = (0, 0, 0)


def font(size: int) -> ImageFont.FreeTypeFont:
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"Missing font: {FONT_PATH}")
    return ImageFont.truetype(str(FONT_PATH), size)


def supersampled(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGBA", (size[0] * SCALE, size[1] * SCALE), TRANSPARENT)


def reduce(image: Image.Image, rgb: bool = False) -> Image.Image:
    result = image.resize(
        (image.width // SCALE, image.height // SCALE),
        Image.Resampling.LANCZOS,
    )
    if rgb:
        canvas = Image.new("RGB", result.size, BLACK)
        canvas.paste(result, mask=result.getchannel("A"))
        return canvas
    return result


def indexed(image: Image.Image) -> Image.Image:
    """Keep antialiased alpha in a compact indexed-color PNG."""
    return image.convert("RGBA").quantize(
        colors=32,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    )


def centered_text(
    text: str,
    size: tuple[int, int],
    font_size: int,
    color: tuple[int, int, int, int] = WHITE,
) -> Image.Image:
    image = supersampled(size)
    draw = ImageDraw.Draw(image)
    face = font(font_size * SCALE)
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(
        (
            image.width / 2 - (box[2] - box[0]) / 2 - box[0],
            image.height / 2 - (box[3] - box[1]) / 2 - box[1],
        ),
        text,
        font=face,
        fill=color,
    )
    return reduce(image)


def draw_binary_digit(
    draw: ImageDraw.ImageDraw,
    digit: int,
    left: int,
    color: tuple[int, int, int, int],
) -> None:
    inset = 2 * SCALE
    diameter = (DOT_SIZE - 4) * SCALE
    stroke = 3 * SCALE
    for row, weight in enumerate(WEIGHTS):
        x = left * SCALE + inset
        y = row * ROW_STEP * SCALE + inset
        bounds = (x, y, x + diameter, y + diameter)
        if digit & weight:
            draw.ellipse(bounds, fill=color)
        else:
            draw.ellipse(bounds, outline=color, width=stroke)


def time_panel(value: int, dim: bool = False) -> Image.Image:
    image = supersampled((TIME_WIDTH, TIME_HEIGHT))
    draw = ImageDraw.Draw(image)
    color = DIM if dim else WHITE
    draw_binary_digit(draw, value // 10, 0, color)
    draw_binary_digit(draw, value % 10, DIGIT_WIDTH, color)
    return reduce(image)


def binary_digit(value: int, dim: bool = False) -> Image.Image:
    image = supersampled((DIGIT_WIDTH, TIME_HEIGHT))
    draw_binary_digit(
        ImageDraw.Draw(image), value, 0, DIM if dim else WHITE
    )
    return reduce(image)


def background(dim: bool = False) -> Image.Image:
    image = Image.new("RGBA", (WIDTH * SCALE, HEIGHT * SCALE), (*BLACK, 255))
    draw = ImageDraw.Draw(image)
    color = DIM if dim else WHITE
    for center_y in (216, 258):
        cx, cy = 106 * SCALE, center_y * SCALE
        radius = 4.5 * SCALE
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
    return reduce(image, rgb=True)


def date_value(text: str, width: int, dim: bool = False) -> Image.Image:
    return centered_text(text, (width, INFO_HEIGHT), 24, DIM if dim else WHITE)


def weather_glyph(text: str) -> Image.Image:
    return centered_text(text, (WEATHER_DIGIT_WIDTH, INFO_HEIGHT), 24)


def weather_unit() -> Image.Image:
    return centered_text("°C", (32, INFO_HEIGHT), 24)


def battery_value(percent: int) -> Image.Image:
    image = supersampled((BATTERY_WIDTH, BATTERY_HEIGHT))
    draw = ImageDraw.Draw(image)
    bounds = (SCALE, SCALE, image.width - SCALE, image.height - SCALE)
    stroke = 2 * SCALE
    radius = BATTERY_HEIGHT * SCALE // 2
    draw.rounded_rectangle(bounds, radius=radius, outline=WHITE, width=stroke)
    if percent:
        inset = 3 * SCALE
        inner_right = inset + round(
            (BATTERY_WIDTH * SCALE - 2 * inset) * percent / 100
        )
        draw.rounded_rectangle(
            (inset, inset, inner_right, image.height - inset),
            radius=(BATTERY_HEIGHT * SCALE - 2 * inset) // 2,
            fill=WHITE,
        )
    return reduce(image)


def image_list(
    widget_id: str,
    x: int,
    y: int,
    source: str,
    names: list[str],
    indices: list[int],
) -> dict:
    if len(names) != len(indices):
        raise ValueError(f"{widget_id}: image and index counts differ")
    return {
        "type": "widge_imagelist",
        "x": x,
        "y": y,
        "dataSrc": source,
        "imageList": names,
        "imageIndexList": indices,
        "id": widget_id,
    }


def digital_number(
    widget_id: str,
    x: int,
    y: int,
    source: str,
    names: list[str],
    show_zero: bool = True,
) -> dict:
    return {
        "type": "widge_dignum",
        "x": x,
        "y": y,
        "showCount": 2,
        "align": 1,
        "spacing": 0,
        "showZero": show_zero,
        "dataSrc": source,
        "imageList": names,
        "id": widget_id,
    }


def clean_pngs(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob("*.png"):
        path.unlink()


def generate_assets() -> None:
    clean_pngs(IMAGES)
    clean_pngs(IMAGES_AOD)
    background().save(IMAGES / "background.png")
    background(True).save(IMAGES_AOD / "background.png")

    for value in range(10):
        indexed(binary_digit(value)).save(IMAGES / f"digit-{value}.png")
        indexed(binary_digit(value, True)).save(
            IMAGES_AOD / f"digit-{value}.png"
        )
        indexed(date_value(str(value), DATE_WIDTH // 2)).save(
            IMAGES / f"date-digit-{value}.png"
        )
        indexed(date_value(str(value), DATE_WIDTH // 2, True)).save(
            IMAGES_AOD / f"date-digit-{value}.png"
        )

    weekdays = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
    for value, name in enumerate(weekdays):
        indexed(date_value(name, WEEKDAY_WIDTH)).save(
            IMAGES / f"weekday-{value}.png"
        )
        indexed(date_value(name, WEEKDAY_WIDTH, True)).save(
            IMAGES_AOD / f"weekday-{value}.png"
        )
    for state in range(6):
        indexed(battery_value(state * 20)).save(
            IMAGES / f"battery-state-{state}.png"
        )

    for value in range(10):
        indexed(weather_glyph(str(value))).save(
            IMAGES / f"weather-digit-{value}.png"
        )
    indexed(weather_glyph("-")).save(IMAGES / "weather-minus.png")
    indexed(weather_unit()).save(IMAGES / "weather-unit.png")


def definition() -> dict:
    hours = list(range(24))
    weekdays = list(range(7))
    batteries = list(range(101))
    digits = [f"digit-{value}" for value in range(10)]
    date_digits = [f"date-digit-{value}" for value in range(10)]
    normal = [
        image_list("background", 0, 0, "811", ["background"] * 24, hours),
        digital_number("hours", HOURS_X, TIME_Y, "811", digits),
        digital_number("minutes", MINUTES_X, TIME_Y, "1011", digits),
        digital_number(
            "weather-temperature",
            WEATHER_X,
            WEATHER_Y,
            "2031",
            [*[f"weather-digit-{value}" for value in range(10)],
             "weather-minus"],
            show_zero=False,
        ),
        image_list(
            "weather-unit",
            WEATHER_UNIT_X,
            WEATHER_Y,
            "811",
            ["weather-unit"] * 24,
            hours,
        ),
        digital_number("month", MONTH_X, DATE_Y, "1012", date_digits),
        image_list(
            "weekday", WEEKDAY_X, DATE_Y, "2012",
            [f"weekday-{value}" for value in weekdays], weekdays,
        ),
        digital_number("day", DAY_X, DATE_Y, "1812", date_digits),
        image_list(
            "battery", BATTERY_X, BATTERY_Y, "0841",
            [
                f"battery-state-{min(5, (value + 10) // 20)}"
                for value in batteries
            ],
            batteries,
        ),
    ]
    aod = [
        image_list("aod-background", 0, 0, "811", ["background"] * 24, hours),
        digital_number("aod-hours", HOURS_X, TIME_Y, "811", digits),
        digital_number("aod-minutes", MINUTES_X, TIME_Y, "1011", digits),
        digital_number("aod-month", MONTH_X, DATE_Y, "1012", date_digits),
        image_list(
            "aod-weekday", WEEKDAY_X, DATE_Y, "2012",
            [f"weekday-{value}" for value in weekdays], weekdays,
        ),
        digital_number("aod-day", DAY_X, DATE_Y, "1812", date_digits),
    ]
    return {
        "name": "Binary",
        "id": "binary",
        "deviceType": "xiaomi_band_10",
        "previewImg": "preview",
        "elementsNormal": normal,
        "elementsAod": aod,
    }


def render_preview() -> None:
    now = dt.datetime.now()
    preview = background()
    for asset, xy in (
        (time_panel(now.hour), (HOURS_X, TIME_Y)),
        (time_panel(now.minute), (MINUTES_X, TIME_Y)),
        (weather_glyph("-"), (WEATHER_X, WEATHER_Y)),
        (weather_glyph("-"), (WEATHER_X + WEATHER_DIGIT_WIDTH, WEATHER_Y)),
        (weather_unit(), (WEATHER_UNIT_X, WEATHER_Y)),
        (date_value(f"{now.month:02d}", DATE_WIDTH), (MONTH_X, DATE_Y)),
        (
            date_value(now.strftime("%a").upper(), WEEKDAY_WIDTH),
            (WEEKDAY_X, DATE_Y),
        ),
        (date_value(f"{now.day:02d}", DATE_WIDTH), (DAY_X, DATE_Y)),
        (battery_value(80), (BATTERY_X, BATTERY_Y)),
    ):
        preview.paste(asset, xy, asset)
    preview.save(IMAGES / "preview.png")
    preview.save(ROOT / "preview.png")

    output_size = (120, 306)
    scale = max(output_size[0] / WIDTH, output_size[1] / HEIGHT)
    resized = preview.resize(
        (round(WIDTH * scale), round(HEIGHT * scale)), Image.Resampling.LANCZOS
    )
    left = (resized.width - output_size[0]) // 2
    top = (resized.height - output_size[1]) // 2
    cropped = resized.crop((left, top, left + 120, top + 306))
    mask = Image.new("L", output_size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 119, 305), radius=64, fill=255)
    readme = Image.new("RGBA", output_size, TRANSPARENT)
    readme.paste(cropped, mask=mask)
    readme.save(ROOT / "preview-readme.png")


def validate(data: dict) -> None:
    for mode in ("elementsNormal", "elementsAod"):
        ids: set[str] = set()
        for widget in data[mode]:
            if widget["type"] == "widge_imagelist":
                if len(widget["imageList"]) != len(widget["imageIndexList"]):
                    raise ValueError(f"{widget['id']}: mismatched mappings")
            elif widget["type"] not in ("widge_dignum", "element"):
                raise ValueError(f"{widget['id']}: unsupported widget type")
            if widget["id"] in ids:
                raise ValueError(f"{mode}: duplicate id {widget['id']}")
            ids.add(widget["id"])


def main() -> None:
    generate_assets()
    data = definition()
    validate(data)
    JSON_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    render_preview()
    print(
        "Generated JSON watchface: 4x supersampled binary dots, colon, text, "
        "battery, live numeric weather glyphs, and complete AOD assets."
    )


if __name__ == "__main__":
    main()
