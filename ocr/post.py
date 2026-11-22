#!/usr/bin/env python3
"""Stage 3 (Post-Processing): Raw Tesseract boxes -> final text + shared metrics."""

import difflib
from PIL import Image
from ocr import engine


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


def accuracy(gt: str, pred: str) -> float:
    gn, pn = norm(gt), norm(pred)
    return max(0.0, 1.0 - levenshtein(gn, pn) / max(1, len(gn)))


def diff_tags(gt_n: str, pred_n: str) -> list[str]:
    tags = [f"{gt_n[i1:i2]!r} -> {pred_n[j1:j2]!r}"
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, gt_n, pred_n).get_opcodes() if op != "equal"]
    return tags or [f"{gt_n!r} -> {pred_n!r}"]


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


def postprocess(img: Image.Image, boxes: list[tuple[str, int, int, int, int]], cfg: dict) -> str:
    if not (cfg.get("detect_sup") or cfg.get("detect_eq") or cfg.get("geom_sup_rescue")):
        return "".join(b[0] for b in boxes)
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
            digit = engine.read_char_crop(img, crop_box, engine.WL_SUP)
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
                    digit = engine.read_char_crop(img, (max(0, ix0 - 4), max(0, iy0 - 4), min(W, x + 4), min(H, iy1 + 4)), engine.WL_SUP)
                    if digit:
                        items.append((ix0, "^" + digit))

    items.sort(key=lambda t: t[0])
    return "".join(tok for _, tok in items)
