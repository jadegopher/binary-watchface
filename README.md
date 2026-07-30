# Binary watchface

A minimal binary watch face for Xiaomi Smart Band 10.

<p align="center">
  <img src="preview-readme.png"
       alt="Binary watch face preview for Xiaomi Smart Band 10"
       width="120"
       height="306">
  <br>
  <sub>212 × 520 px display · 46.57 × 22.54 mm band body</sub>
</p>

<p align="center">
  <a href="https://buymeacoffee.com/jadegopher">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png"
       alt="Buy Me a Coffee" width="200">
  </a>
</p>

## Reading the time

The four columns represent the digits of 24-hour time (`HHMM`). Read each
column from top to bottom using the values `8`, `4`, `2`, and `1`:

- Filled circle: `1`
- Empty circle: `0`

Add the filled values in each column to get its digit. The colon separates
hours from minutes.

The face also shows the current temperature, date, weekday, and battery level.
The battery capsule has six states from empty to full. Weather is left blank
when the band has no valid temperature data.

## Install

### Download a release

1. Download the latest `.face` file from the project's Releases page.
2. Connect the Xiaomi Smart Band 10 to an Android phone.
3. Install a compatible third-party app, such as **[Notify for Xiaomi](https://play.google.com/store/apps/details?id=com.mc.xiaomi1&hl=en)**.
4. Open the app and go to **Watchfaces**.
5. Select **Install private watchface**.
6. Choose the downloaded `.face` file and install it.

Third-party installation is unofficial. App menus and compatibility may change
between versions.

### Build with Mi Create

1. Install Xiaomi **[Mi Create](https://github.com/ooflet/Mi-Create)**.
2. Open `binary.fprj`.
3. Build or export the project for Xiaomi Smart Band 10.
4. Find the generated `.face` file in the output folder.
5. Install it using the Android steps above.

## Regenerate assets

Python and Pillow are required:

```sh
python generate_assets.py
```

This regenerates the normal assets, AOD assets, and preview images. The
watch face uses Lato Black for its text; `Lato-Black.ttf` must remain beside
the generator.

## Project notes

- Display: `212 × 520`
- Mi Create device ID: `466`
- Main project: `binary.fprj`
- AOD project: `AOD/AOD.fprj`
- Compiled output: `output/binary.face`

`DeviceType="466"` is Mi Create's compiler identifier, not the display width.
The generated `preview_default.png` files work around missing Smart Band 10
preview-size metadata in Mi Create 1.1.1.
