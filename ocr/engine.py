#!/usr/bin/env python3
"""Stage 2 (Engine): Image -> Raw Tesseract output only (zero filtering/rewriting)."""

import json, os
os.environ["OMP_THREAD_LIMIT"] = "1"

import subprocess, tempfile
from pathlib import Path
from PIL import Image

WL_MATH = "0123456789abxyzABXYZ+-="
WL_SUP = "0123456789"
VISION_BIN = Path(__file__).resolve().parent / "vision_ocr"


def _tess_extra(cfg: dict) -> list[str]:
    extra: list[str] = []
    if wl := cfg.get("whitelist", ""):
        extra += ["-c", f"tessedit_char_whitelist={wl}"]
    for k, v in (cfg.get("tess_cfg") or {}).items():
        extra += ["-c", f"{k}={v}"]
    if dpi := cfg.get("dpi", ""):
        extra += ["--dpi", str(dpi)]
    if td := cfg.get("tessdata_dir", ""):
        extra += ["--tessdata-dir", str(td)]
    return extra


def run_tesseract(
    img: Image.Image,
    *,
    lang: str = "eng",
    oem: str = "1",
    psm: str = "6",
    extra: tuple[str, ...] = (),
) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        img.save(tf.name)
        cmd = ["tesseract", tf.name, "stdout", "-l", lang, "--oem", oem, "--psm", psm, *extra]
        return subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False).stdout.strip()


def read_text(img: Image.Image, cfg: dict) -> str:
    return run_tesseract(
        img,
        lang=str(cfg.get("lang", "eng")),
        oem=str(cfg.get("oem", "1")),
        psm=str(cfg.get("psm", "6")),
        extra=tuple(_tess_extra(cfg)),
    )


def _vision_cmd(target: str, cfg: dict) -> list[str]:
    cmd = [
        str(VISION_BIN), target,
        "--level", str(cfg.get("vision_level", "accurate")),
        "--lang", str(cfg.get("vision_lang", "de-DE,en-US")),
        "--correct", "1" if cfg.get("vision_correct", True) else "0",
    ]
    if (mh := cfg.get("vision_min_height")) is not None:
        cmd += ["--min-height", str(mh)]
    return cmd


def read_vision(img: Image.Image, cfg: dict) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as tf:
        img.save(tf.name)
        return subprocess.run(_vision_cmd(tf.name, cfg), stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False).stdout.strip()


def run_vision_batch(paths: list[Path], cfg: dict) -> list[tuple[str, float]]:
    """Run vision_ocr --batch once over a list of PNG paths; returns [(text, ms), ...]."""
    payload = "".join(f"{p}\n" for p in paths)
    res = subprocess.run(_vision_cmd("--batch", cfg), input=payload, capture_output=True, text=True, check=False)
    out = [json.loads(line) for line in res.stdout.splitlines() if line.strip()]
    return [(o.get("text", "").strip(), float(o.get("ms", 0.0))) for o in out]


def read_boxes(img: Image.Image, cfg: dict) -> tuple[str, list[tuple[str, int, int, int, int]]]:
    extra = _tess_extra(cfg) + ["makebox"]
    raw = run_tesseract(
        img,
        lang=str(cfg.get("lang", "eng")),
        oem=str(cfg.get("oem", "1")),
        psm=str(cfg.get("psm", "6")),
        extra=tuple(extra),
    )
    H = img.height
    boxes = []
    for line in raw.splitlines():
        p = line.split()
        if len(p) >= 5:
            x0, y_bot, x1, y_top = int(p[1]), int(p[2]), int(p[3]), int(p[4])
            boxes.append((p[0], x0, H - y_top, x1, H - y_bot))
    return "".join(b[0] for b in boxes), boxes


def read_char_crop(img: Image.Image, box: tuple[int, int, int, int], wl: str) -> str:
    crop = img.crop(box)
    scale = max(1, 60 // max(1, crop.height))
    if scale > 1:
        crop = crop.resize((crop.width * scale, crop.height * scale))
    canvas = Image.new("L", (crop.width + 60, crop.height + 60), 255)
    canvas.paste(crop, (30, 30))
    return run_tesseract(canvas, lang="eng", oem="1", psm="10", extra=("-c", f"tessedit_char_whitelist={wl}"))
