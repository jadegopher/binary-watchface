# Xiaomi Smart Band 10 JSON watchface notes

This project is a Chinese GMF watchface (`wfDef.json`) targeting the Xiaomi
Smart Band 10 at 212×520.

## Architecture

- Use `widge_imagelist` for complete state images.
- Temperature is the exception: source `2031` is a signed numeric value and
  must use `widge_dignum`. The `°C` resource uses an image list mapped to all
  hour values because a plain static `element` is not reliable on the Band.
- `x` and `y` are direct top-left coordinates.
- `imageList` and `imageIndexList` must have equal lengths.
- Resource names in JSON omit `.png`.
- Normal resources live in `images`; AOD resources live in `images_aod`.
- Do not convert the time panels to `widge_dignum`. Complete panels keep all
  four binary columns fixed on both the editor and Band firmware.

Normal mode contains one background; 24 complete hour panels; 60 complete
minute panels; temperature, month, weekday, and day selectors; and 101
battery capsule states. AOD uses the same time and date positions without
weather or battery.

## Rendering rules

- All circles, the colon, text, and battery geometry are rendered at 4× and
  downsampled with Lanczos.
- The background is opaque RGB.
- Dynamic panels are transparent RGBA.
- Every image in a selector must have identical dimensions and format.
- Run `python generate_assets.py` after changing any layout constant.

## Weather compatibility

Source `2031` is numeric, not an image-list index. Using it with
`widge_imagelist` makes the firmware show the selector's first image
continuously. The digital-number widget lets firmware render current positive
and negative temperatures and handle invalid weather according to the phone's
runtime data.

## Build and validation

1. Run `python generate_assets.py`.
2. Confirm image-list mapping lengths match and weather remains
   `widge_dignum`.
3. Run `WatchfacePackTool64.exe` from the project directory.
4. Wait for `wf_pack.bin`, then verify `pack.log` ends in `success`.
5. Test the new binary on-device; successful packing does not validate
   firmware runtime behavior.
