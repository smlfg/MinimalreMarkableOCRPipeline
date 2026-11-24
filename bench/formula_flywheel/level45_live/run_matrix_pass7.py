"""Pass 7 matrix experiments H1 (wide split) and H2 (tall re-render), live TT CPU."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ocr.coherence import coherent, tt_postprocess  # noqa: E402
from ocr.formula import TexTeller, prepare_tt_input  # noqa: E402
from ocr.latex import same  # noqa: E402
import bench.structure_bench as sb  # noqa: E402

HERE = Path(__file__).resolve().parent
BENCH = ROOT / "bench"
TALL_DIR = HERE / "images_matrix_tall_pass7"


def _pipe(raw: str) -> tuple[str, str | None]:
    t = tt_postprocess(raw)
    fixed, repair, _ = coherent(t, t)
    return fixed, repair


def _sympy_ok(gt: str, pred: str) -> bool:
    return bool(sb.score(gt, pred)["sympy_equal"])


def _image_wh(png: Path) -> tuple[int, int, float]:
    img = Image.open(png)
    w, h = img.size
    return w, h, w / max(h, 1)


def find_split_column(img: Image.Image, min_aspect: float = 12.0) -> int | None:
    w, h = img.size
    if w / max(h, 1) < min_aspect:
        return None
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    ink = (255.0 - gray).clip(0, 255)
    proj = ink.sum(axis=0)
    lo, hi = int(w * 0.25), int(w * 0.72)
    if hi <= lo + 8:
        return None
    band = proj[lo:hi]
    if band.max() <= 0:
        return None
    rel = band / max(band.max(), 1e-6)
    candidates = [i for i, v in enumerate(rel) if v < 0.08]
    if not candidates:
        return None
    best_start, best_len = 0, 0
    i = 0
    while i < len(candidates):
        start = candidates[i]
        j = i + 1
        while j < len(candidates) and candidates[j] == candidates[j - 1] + 1:
            j += 1
        run_len = candidates[j - 1] - start + 1
        if run_len > best_len:
            best_len, best_start = run_len, start
        i = j
    if best_len < 3:
        return None
    return lo + best_start + best_len // 2


def tt_split_merge(tt: TexTeller, png: Path, aspect_min: float = 12.0) -> tuple[str, float, bool]:
    img = Image.open(png).convert("RGB")
    w, h = img.size
    t0 = time.perf_counter()
    split_x = find_split_column(img, min_aspect=aspect_min)
    if split_x is None:
        raw, _ = tt(str(png))
        return raw, (time.perf_counter() - t0) * 1000, False
    left = img.crop((0, 0, split_x, h))
    right = img.crop((split_x, 0, w, h))
    temps: list[Path] = []
    try:
        parts: list[str] = []
        for part in (left, right):
            fd, p = tempfile.mkstemp(suffix=".png", prefix="tt_split_")
            Path(p).unlink(missing_ok=True)
            tmp = Path(p)
            part.save(tmp)
            temps.append(tmp)
            latex, _ = tt(str(tmp))
            parts.append(latex.strip())
        raw = parts[0] + "=" + parts[1] if len(parts) == 2 else parts[0]
        return raw, (time.perf_counter() - t0) * 1000, True
    finally:
        for t in temps:
            t.unlink(missing_ok=True)


def tallify_matrix_png(src: Path, dst: Path, min_h: int = 128) -> tuple[int, int]:
    """Pass 7 H2: upscale + white pad existing strip (no latex re-render)."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    if h < min_h:
        scale = min_h / max(h, 1)
        img = img.resize((max(1, int(round(w * scale))), min_h), Image.LANCZOS)
    border = max(24, min_h // 5)
    img = ImageOps.expand(img, border=border, fill=(255, 255, 255))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)
    return img.size


def load_dev_matrix() -> list[dict]:
    rows = [
        json.loads(ln)
        for ln in (HERE / "dev.jsonl").read_text().splitlines()
        if ln.strip()
    ]
    return [r for r in rows if r.get("bucket") == "matrix"]


def eval_h1(tt: TexTeller, only_fails: bool) -> dict:
    baseline_path = BENCH / "results_pass6_l45_baseline_dev.jsonl"
    base_fail = set()
    if baseline_path.is_file():
        for ln in baseline_path.read_text().splitlines():
            r = json.loads(ln)
            if r["bucket"] == "matrix" and not r.get("pipe_sympy"):
                base_fail.add(r["id"])
    rows = load_dev_matrix()
    if only_fails:
        rows = [r for r in rows if r["id"] in base_fail]
    detail = []
    for row in rows:
        png = HERE / row["png"]
        w, h, asp = _image_wh(png)
        raw, ms, split = tt_split_merge(tt, png)
        pipe, _ = _pipe(raw)
        gt = row["gt_latex"]
        detail.append(
            {
                "id": row["id"],
                "gt_latex": gt,
                "w": w,
                "h": h,
                "aspect": round(asp, 2),
                "split_used": split,
                "raw_latex": raw,
                "pipe_latex": pipe,
                "pipe_sympy": _sympy_ok(gt, pipe),
                "tt_ms": round(ms, 1),
            }
        )
    n = len(detail)
    hit = sum(x["pipe_sympy"] for x in detail)
    return {
        "experiment": "H1_wide_split",
        "n": n,
        "pipe_sympy": hit / n if n else 0.0,
        "split_rate": sum(x["split_used"] for x in detail) / n if n else 0.0,
        "rows": detail,
    }


def eval_h2(tt: TexTeller) -> dict:
    rows = load_dev_matrix()
    TALL_DIR.mkdir(parents=True, exist_ok=True)
    detail = []
    for row in rows:
        tall_png = TALL_DIR / f"{row['id']}.png"
        orig_png = HERE / row["png"]
        tw, th = tallify_matrix_png(orig_png, tall_png)
        w, h, asp = _image_wh(tall_png)
        tt_path, tmp = prepare_tt_input(tall_png)
        try:
            raw, dt = tt(tt_path)
        finally:
            if tmp and tmp.is_file():
                tmp.unlink(missing_ok=True)
        pipe, _ = _pipe(raw)
        gt = row["gt_latex"]
        _, h0, asp0 = _image_wh(orig_png)
        detail.append(
            {
                "id": row["id"],
                "gt_latex": gt,
                "orig_h": h0,
                "tall_h": th,
                "tall_w": tw,
                "orig_aspect": round(asp0, 2),
                "tall_aspect": round(asp, 2),
                "raw_latex": raw,
                "pipe_latex": pipe,
                "pipe_sympy": _sympy_ok(gt, pipe),
                "tt_ms": round(dt * 1000, 1),
            }
        )
    n = len(detail)
    hit = sum(x["pipe_sympy"] for x in detail)
    lat = [x["tt_ms"] for x in detail]
    return {
        "experiment": "H2_matrix_tall_render",
        "n": n,
        "pipe_sympy": hit / n if n else 0.0,
        "mean_tt_ms": statistics.mean(lat) if lat else 0,
        "note": "synthetic strip renderer limit; vertical upscale/pad only (not product OCR win)",
        "rows": detail,
    }


def write_results(tag: str, payload: dict) -> None:
    jp = BENCH / f"results_pass7_matrix_{tag}.json"
    tp = BENCH / f"results_pass7_matrix_{tag}.tsv"
    jp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    lines = [
        f"experiment\t{payload['experiment']}",
        f"n\t{payload['n']}",
        f"pipe_sympy\t{payload['pipe_sympy']:.4f}",
    ]
    for r in payload.get("rows", []):
        lines.append(
            f"{r['id']}\t{r.get('pipe_sympy')}\t{r.get('split_used', '')}\t"
            f"{r.get('h', r.get('tall_h', ''))}\t{r['pipe_latex'][:120]}"
        )
    tp.write_text("\n".join(lines) + "\n")
    print(json.dumps({k: payload[k] for k in payload if k != "rows"}, indent=2))
    print(f"wrote {jp.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--h1", action="store_true")
    ap.add_argument("--h2", action="store_true")
    ap.add_argument("--h1-all", action="store_true", help="H1 on all matrix dev, not only baseline fails")
    args = ap.parse_args()
    if not (args.h1 or args.h2):
        args.h1 = args.h2 = True
    tt = TexTeller()
    if args.h1:
        write_results("h1_dev", eval_h1(tt, only_fails=not args.h1_all))
    if args.h2:
        write_results("h2_tall", eval_h2(tt))


if __name__ == "__main__":
    main()