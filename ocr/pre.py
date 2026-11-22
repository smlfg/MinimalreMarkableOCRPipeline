#!/usr/bin/env python3
"""Stage 1 (Pre-Processing): Image -> Image only (zero Tesseract/subprocess)."""

from PIL import Image, ImageFilter, ImageOps


def split_lines(gray: Image.Image) -> list[Image.Image]:
    mask = ImageOps.invert(gray).point(lambda p: 255 if p > 55 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return [gray]
    px, raw_bands, in_b = mask.load(), [], False
    for y in range(bbox[1], bbox[3]):
        has_ink = any(px[x, y] for x in range(bbox[0], bbox[2]))
        if has_ink and not in_b:
            in_b, y0 = True, y
        elif not has_ink and in_b:
            in_b = False
            if raw_bands and y0 - raw_bands[-1][1] <= 3:
                raw_bands[-1] = (raw_bands[-1][0], y)
            else:
                raw_bands.append((y0, y))
    if in_b:
        raw_bands.append((y0, bbox[3]))
    bands = [(a, b) for a, b in raw_bands if b - a >= 8]
    if len(bands) <= 1:
        return [gray]
    lines = []
    for y0, y1 in bands:
        sub_box = (bbox[0], max(0, y0 - 2), bbox[2], min(gray.height, y1 + 2))
        lb = mask.crop(sub_box).getbbox()
        if lb:
            crop = gray.crop((sub_box[0] + lb[0], sub_box[1] + lb[1], sub_box[0] + lb[2], sub_box[1] + lb[3]))
            canvas = Image.new("L", (crop.width + 80, crop.height + 80), 255)
            canvas.paste(crop, (40, 40))
            lines.append(canvas)
    return lines or [gray]


def preprocess(img: Image.Image, cfg: dict) -> Image.Image:
    gray = img.convert("L")
    if cfg.get("ink_crop"):
        bbox = ImageOps.invert(gray).point(lambda p: 255 if p > 55 else 0).getbbox()
        if bbox:
            pad = 40
            crop = gray.crop(bbox)
            canvas = Image.new("L", (crop.width + 2 * pad, crop.height + 2 * pad), 255)
            canvas.paste(crop, (pad, pad))
            gray = canvas
    if cfg.get("bold"):
        gray = gray.filter(ImageFilter.MinFilter(3))
    scale = float(cfg.get("scale", 1.0))
    if scale != 1.0:
        gray = gray.resize(
            (max(1, int(round(gray.width * scale))), max(1, int(round(gray.height * scale)))),
            Image.Resampling.LANCZOS,
        )
    return gray
