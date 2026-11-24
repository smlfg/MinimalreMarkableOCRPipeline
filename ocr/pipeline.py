#!/usr/bin/env python3
"""Thin 3-stage OCR orchestrator: pre -> engine -> post (exposes raw + final)."""

import sys, time
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ocr import engine, post, pre  # noqa: E402
from ocr.post import accuracy, diff_tags, levenshtein, norm  # noqa: F401, E402
from ocr.pre import split_lines  # noqa: F401, E402

real_accuracy = accuracy

DEFAULT_CFG = {
    # Pre
    "split_lines": True,
    "ink_crop": False,
    "bold": False,
    "scale": 1.0,
    # Engine
    "engine": "tesseract_word",
    "lang": "eng",
    "oem": "1",
    "psm": "6",
    "dpi": "",
    "tessdata_dir": "",
    "whitelist": "",
    "tess_cfg": {},
    "vision_level": "accurate",
    "vision_lang": "de-DE,en-US",
    "vision_correct": True,
    "vision_min_height": None,
    # Post
    "detect_sup": False,
    "fix_minus_bug": False,
    "detect_eq": False,
    "geom_sup_rescue": False,
}


def run_detailed(png_path: Path, cfg: dict | None = None) -> dict:
    t0 = time.perf_counter()
    merged = {**DEFAULT_CFG, **(cfg or {})}
    gray = Image.open(png_path).convert("L")
    chunks = pre.split_lines(gray) if merged.get("split_lines") else [gray]
    eng_name = merged.get("engine", "tesseract_word")
    raw_lines, fin_lines = [], []
    for chunk in chunks:
        proc = pre.preprocess(chunk, merged)
        if eng_name == "apple_vision":
            raw_txt = fin_txt = engine.read_vision(proc, merged)
        elif eng_name == "tesseract_word":
            raw_txt = fin_txt = engine.read_text(proc, merged)
        else:
            raw_txt, boxes = engine.read_boxes(proc, merged)
            fin_txt = post.postprocess(proc, boxes, merged)
        if raw_txt:
            raw_lines.append(raw_txt)
        if fin_txt:
            fin_lines.append(fin_txt)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {"raw": "\n".join(raw_lines), "final": "\n".join(fin_lines), "ms": elapsed_ms}


def run(png_path: Path, cfg: dict | None = None) -> str:
    return run_detailed(png_path, cfg)["final"]


def recognize_page(png_path: Path, recognize_line, cfg: dict | None = None) -> dict:
    """Mehrzeilige Seitenstruktur (ADR-005, additiv): Zeilen mit Boxen segmentieren,
    jede Zeile mit `recognize_line(img) -> dict` lesen und zu Rechenketten gruppieren.
    `recognize_line` liefert Felder wie ocr/formula.py (latex, uncertain, repair, math_status,
    alt). Die Zeilen werden unveraendert in `lines` durchgereicht; `chains` halten Referenzen
    (ocr/multiline.py). Kein bestehender Aufrufer ist betroffen."""
    from ocr import multiline
    merged = {**DEFAULT_CFG, **(cfg or {})}
    gray = Image.open(png_path).convert("L")
    chunks = pre.split_lines_with_boxes(gray)
    t0 = time.perf_counter()
    lines = []
    for idx, (img, bbox) in enumerate(chunks):
        rec = dict(recognize_line(img) or {})
        lines.append({"id": f"l{idx + 1}", "bbox": bbox, **rec})
    page = multiline.page_structure(lines)
    page["ms"] = (time.perf_counter() - t0) * 1000.0
    page["cfg"] = merged.get("engine")
    return page


if __name__ == "__main__":
    if len(sys.argv) < 2 or not Path(sys.argv[1]).is_file():
        print("Verwendung: python3 ocr/pipeline.py <bild.png>", file=sys.stderr)
        sys.exit(1)
    best_cfg = {
        "engine": "tesseract_makebox", "ink_crop": True, "bold": True, "whitelist": engine.WL_MATH,
        "detect_sup": True, "fix_minus_bug": True, "detect_eq": True, "geom_sup_rescue": True,
    }
    res = run_detailed(Path(sys.argv[1]), best_cfg)
    print(f"RAW:  {res['raw']}")
    print(f"POST: {res['final']} ({res['ms']:.1f} ms)")
