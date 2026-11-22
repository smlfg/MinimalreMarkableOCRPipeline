#!/usr/bin/env python3
"""3-stage Tesseract OCR pipeline + shared text metrics."""

import os
os.environ["OMP_THREAD_LIMIT"] = "1"

import difflib, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

WL_MAIN = "0123456789abxyzABXYZ+-="
WL_SUP = "0123456789"

DEFAULT_CFG = {
    "split_lines": True,
    "ink_crop": False,
    "bold": False,
    "psm": "6",
    "use_whitelist": False,
    "detect_sup": True,
    "fix_minus_bug": False,
    "detect_eq": True,
    "geom_sup_rescue": False,
}


def norm(s: str) -> str:
    return "".join(s.split()).lower()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def real_accuracy(gt: str, pred: str) -> float:
    gn, pn = norm(gt), norm(pred)
    return max(0.0, 1.0 - levenshtein(gn, pn) / max(1, len(gn)))


def diff_tags(gt_n: str, pred_n: str) -> list[str]:
    tags = [f"{gt_n[i1:i2]!r} -> {pred_n[j1:j2]!r}"
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, gt_n, pred_n).get_opcodes() if op != "equal"]
    return tags or [f"{gt_n!r} -> {pred_n!r}"]


def tess(img: Image.Image, psm: str = "6", extra: tuple[str, ...] = ()) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        img.save(tf.name)
        cmd = ["tesseract", tf.name, "stdout", "-l", "eng", "--oem", "1", "--psm", psm, *extra]
        return subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False).stdout.strip()


def read_crop(img: Image.Image, box: tuple[int, int, int, int], wl: str) -> str:
    crop = img.crop(box)
    scale = max(1, 60 // max(1, crop.height))
    if scale > 1:
        crop = crop.resize((crop.width * scale, crop.height * scale))
    canvas = Image.new("L", (crop.width + 60, crop.height + 60), 255)
    canvas.paste(crop, (30, 30))
    return tess(canvas, "10", ("-c", f"tessedit_char_whitelist={wl}"))


def is_equals_box(img: Image.Image, box: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = box
    px, mx = img.load(), (x0 + x1) // 2
    runs, dark = 0, False
    for y in range(max(0, y0 - 12), min(img.height, y1 + 12)):
        ink = px[mx, y] < 200
        if ink and not dark:
            runs += 1
        dark = ink
    return runs >= 2


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
    return gray


def ocr_boxes(img: Image.Image, cfg: dict) -> list[tuple[str, int, int, int, int]]:
    extra = ("-c", f"tessedit_char_whitelist={WL_MAIN}", "makebox") if cfg.get("use_whitelist") else ("makebox",)
    raw = tess(img, str(cfg.get("psm", "6")), extra)
    H = img.height
    boxes = []
    for line in raw.splitlines():
        p = line.split()
        if len(p) >= 5:
            x0, y_bot, x1, y_top = int(p[1]), int(p[2]), int(p[3]), int(p[4])
            boxes.append((p[0], x0, H - y_top, x1, H - y_bot))
    return boxes


def postprocess(img: Image.Image, boxes: list[tuple[str, int, int, int, int]], cfg: dict) -> str:
    if not boxes:
        return ""
    W, H = img.size
    max_h = max(bot - top for _, _, top, _, bot in boxes)
    base_bots = sorted(bot for _, _, top, _, bot in boxes if (bot - top) >= max_h * 0.65)
    baseline = base_bots[len(base_bots) // 2] if base_bots else max(b[4] for b in boxes)

    items = []
    for ch, x0, top, x1, bot in boxes:
        w, h = x1 - x0, bot - top
        crop_box = (max(0, x0 - 4), max(0, top - 4), min(W, x1 + 4), min(H, bot + 4))
        is_flat = cfg.get("fix_minus_bug") and (ch == "-" or w > h * 1.4)
        is_sup = cfg.get("detect_sup") and not is_flat and bot < baseline - max_h * 0.45 and h < max_h * 0.75
        if is_sup:
            digit = read_crop(img, crop_box, WL_SUP)
            if digit:
                items.append((x0, "^" + digit))
        elif cfg.get("detect_eq") and ch == "-" and is_equals_box(img, crop_box):
            items.append((x0, "="))
        else:
            items.append((x0, ch))

    if cfg.get("geom_sup_rescue"):
        px = img.load()
        covered = [(x0 - 2, x1 + 2) for _, x0, _, x1, _ in boxes]
        scan_x0 = max(0, min(b[1] for b in boxes))
        scan_x1 = min(W, int(max(b[3] for b in boxes) + max_h))
        by0, by1 = max(0, int(baseline - 1.5 * max_h)), max(0, int(baseline - 0.25 * max_h))
        in_col = False
        for x in range(scan_x0, scan_x1 + 1):
            is_cov = any(a <= x <= b for a, b in covered)
            ys = [] if (is_cov or x == scan_x1) else [y for y in range(by0, by1) if px[x, y] < 200]
            if ys and not in_col:
                in_col, ix0, iy0, iy1 = True, x, min(ys), max(ys)
            elif ys and in_col:
                iy0, iy1 = min(iy0, min(ys)), max(iy1, max(ys))
            elif not ys and in_col:
                in_col = False
                if (iy1 - iy0) >= 6 and (x - ix0) >= 4 and iy1 < baseline - max_h * 0.30:
                    digit = read_crop(img, (max(0, ix0 - 4), max(0, iy0 - 4), min(W, x + 4), min(H, iy1 + 4)), WL_SUP)
                    if digit:
                        items.append((ix0, "^" + digit))

    items.sort(key=lambda t: t[0])
    return "".join(tok for _, tok in items)


def run(png_path: Path, cfg: dict | None = None) -> str:
    merged = {**DEFAULT_CFG, **(cfg or {})}
    gray = Image.open(png_path).convert("L")
    chunks = split_lines(gray) if merged.get("split_lines") else [gray]
    outs = [postprocess(proc, ocr_boxes(proc, merged), merged) for c in chunks if (proc := preprocess(c, merged))]
    return "\n".join(o for o in outs if o)


if __name__ == "__main__":
    if len(sys.argv) < 2 or not Path(sys.argv[1]).is_file():
        print("Verwendung: python3 ocr/pipeline.py <bild.png>", file=sys.stderr)
        sys.exit(1)
    best_cfg = {"ink_crop": True, "bold": True, "fix_minus_bug": True, "use_whitelist": True, "geom_sup_rescue": True}
    print(run(Path(sys.argv[1]), best_cfg))
