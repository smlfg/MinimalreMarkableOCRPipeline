#!/usr/bin/env python3
"""Fast (<1s) OCR variant definitions and worker/process evaluation runners."""

import collections, concurrent.futures, json, subprocess, tempfile, time
from pathlib import Path
from PIL import Image

from ocr import engine as ocr_engine, pipeline as ocr_pipeline, pre as ocr_pre

BASE_DIR = Path(__file__).resolve().parent.parent
MAX_MS = 1000.0
TESS_BEST = str(BASE_DIR / "data" / "tessdata_best")
WAVE2_PY = BASE_DIR / ".venv_wave2" / "bin" / "python"
WAVE2_WORKER = BASE_DIR / "bench" / "wave2_worker.py"

VARIANTS = {
    "vision_batch_acc":   ("AppleVision", {"engine": "apple_vision_batch", "vision_level": "accurate", "vision_lang": "de-DE,en-US", "vision_correct": True}),
    "vision_batch_bold":  ("AppleVision", {"engine": "apple_vision_batch", "ink_crop": True, "bold": True, "vision_level": "accurate", "vision_lang": "de-DE,en-US", "vision_correct": True}),
    "vision_batch_s2":    ("AppleVision", {"engine": "apple_vision_batch", "ink_crop": True, "bold": True, "scale": 2.0, "vision_level": "accurate", "vision_lang": "de-DE,en-US", "vision_correct": True}),
    "vision_batch_s3":    ("AppleVision", {"engine": "apple_vision_batch", "ink_crop": True, "bold": True, "scale": 3.0, "vision_level": "accurate", "vision_lang": "de-DE,en-US", "vision_correct": True, "vision_min_height": 0.0}),
    "vision_batch_s2_nc": ("AppleVision", {"engine": "apple_vision_batch", "ink_crop": True, "bold": True, "scale": 2.0, "vision_level": "accurate", "vision_lang": "de-DE,en-US", "vision_correct": False}),
    "tess_fast_bold":     ("Tesseract",   {"engine": "tesseract_word", "ink_crop": True, "bold": True, "lang": "deu+eng", "psm": "7"}),
    "tess_best_bold":     ("Tesseract",   {"engine": "tesseract_word", "ink_crop": True, "bold": True, "lang": "deu+eng", "psm": "7", "tessdata_dir": TESS_BEST}),
    "rapidocr_raw":       ("RapidOCR",    {"engine": "rapidocr"}),
    "rapidocr_bold":      ("RapidOCR",    {"engine": "rapidocr", "ink_crop": True, "bold": True}),
}


class BatchWorker:
    """Persistent stdin/stdout JSON-lines OCR worker."""

    def __init__(self, cmd: list[str], warmup_png: Path | None = None):
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1
        )
        if warmup_png is not None:
            self.infer(warmup_png)

    def infer(self, png_path: Path) -> tuple[str, float]:
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(f"{png_path}\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("Batch worker exited unexpectedly")
        obj = json.loads(line)
        return obj.get("text", "").strip(), float(obj.get("ms", 0.0))

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


def _eval_real(task: tuple[Path, str, str, dict]) -> tuple[str, str, float, float]:
    png_path, bucket, gt, cfg = task
    res = ocr_pipeline.run_detailed(png_path, cfg)
    return bucket, res["final"], ocr_pipeline.accuracy(gt, res["final"]) * 100.0, res["ms"]


def _eval_synth(task: tuple[Path, str, dict]) -> tuple[bool, float]:
    png_path, gt, cfg = task
    res = ocr_pipeline.run_detailed(png_path, cfg)
    return ocr_pipeline.norm(gt) == ocr_pipeline.norm(res["final"]), res["ms"]


def _prep_item(task: tuple[int, Path, dict, Path]) -> tuple[int, list[Path], float]:
    idx, png_path, cfg, out_dir = task
    merged = {**ocr_pipeline.DEFAULT_CFG, **cfg}
    t0 = time.perf_counter()
    gray = Image.open(png_path).convert("L")
    chunks = ocr_pre.split_lines(gray) if merged.get("split_lines") else [gray]
    paths: list[Path] = []
    for ci, ch in enumerate(chunks):
        proc = ocr_pre.preprocess(ch, merged)
        out = out_dir / f"{idx}_{ci}.png"
        proc.save(out)
        paths.append(out)
    return idx, paths, (time.perf_counter() - t0) * 1000.0


def _eval_worker_paths(worker: BatchWorker, pool: concurrent.futures.ProcessPoolExecutor, png_paths: list[Path], cfg: dict) -> list[tuple[str, float]]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        prepped = list(pool.map(_prep_item, [(i, p, cfg, tmp) for i, p in enumerate(png_paths)], chunksize=16))
        out: list[tuple[str, float]] = []
        for _, chunk_paths, pre_ms in prepped:
            texts, eng_ms = [], 0.0
            for cp in chunk_paths:
                txt, cms = worker.infer(cp)
                if txt:
                    texts.append(txt)
                eng_ms += cms
            out.append(("\n".join(texts), pre_ms + eng_ms))
        return out


def active_variants() -> dict[str, tuple[str, dict]]:
    out = {}
    has_wave2 = WAVE2_PY.is_file() and WAVE2_WORKER.is_file()
    for name, (fam, cfg) in VARIANTS.items():
        if cfg.get("tessdata_dir") and not (Path(cfg["tessdata_dir"]) / "eng.traineddata").is_file():
            continue
        if cfg.get("engine") == "rapidocr" and not has_wave2:
            continue
        out[name] = (fam, cfg)
    return out


def open_persistent_workers(variants: dict[str, tuple[str, dict]], warmup_png: Path) -> dict[str, BatchWorker]:
    workers: dict[str, BatchWorker] = {}
    if any(c.get("engine") == "rapidocr" for _, c in variants.values()):
        workers["rapidocr"] = BatchWorker([str(WAVE2_PY), str(WAVE2_WORKER), "--engine", "rapidocr"], warmup_png)
    return workers


def evaluate_variant(
    pool: concurrent.futures.ProcessPoolExecutor,
    vname: str,
    family: str,
    cfg: dict,
    real_rows: list[list[str]],
    real_paths: list[Path],
    synth_rows: list[tuple[str, int, str, str]],
    synth_paths: list[Path],
    persistent_workers: dict[str, BatchWorker],
    first_png: Path,
) -> tuple[dict, list[tuple[str, str, float, float]]]:
    eng = cfg.get("engine")
    if eng == "tesseract_word":
        r_res = list(pool.map(_eval_real, [(p, r[1], r[4], cfg) for p, r in zip(real_paths, real_rows)]))
        s_res = list(pool.map(_eval_synth, [(p, gt, cfg) for p, (_, _, _, gt) in zip(synth_paths, synth_rows)], chunksize=8))
    else:
        temp_worker = None
        if eng == "apple_vision_batch":
            merged = {**ocr_pipeline.DEFAULT_CFG, **cfg}
            worker = temp_worker = BatchWorker(ocr_engine._vision_cmd("--batch", merged), first_png)
        else:
            worker = persistent_workers[eng]
        try:
            r_raw = _eval_worker_paths(worker, pool, real_paths, cfg)
            s_raw = _eval_worker_paths(worker, pool, synth_paths, cfg)
        finally:
            if temp_worker is not None:
                temp_worker.close()
        r_res = [(r[1], pred, ocr_pipeline.accuracy(r[4], pred) * 100.0, ms) for r, (pred, ms) in zip(real_rows, r_raw)]
        s_res = [(ocr_pipeline.norm(gt) == ocr_pipeline.norm(pred), ms) for (_, _, _, gt), (pred, ms) in zip(synth_rows, s_raw)]

    by_b = collections.defaultdict(list)
    for b, _, acc, _ in r_res:
        by_b[b].append(acc)
    mean_ms = sum(x[3] for x in r_res) / max(1, len(r_res))
    row = {
        "name": vname,
        "family": family,
        "math": sum(by_b["real_math"]) / max(1, len(by_b["real_math"])),
        "dev": sum(by_b["real_text_dev"]) / max(1, len(by_b["real_text_dev"])),
        "hold": sum(by_b["real_text_holdout"]) / max(1, len(by_b["real_text_holdout"])),
        "real_all": sum(x[2] for x in r_res) / max(1, len(r_res)),
        "synth": 100.0 * sum(x[0] for x in s_res) / max(1, len(s_res)),
        "ms": mean_ms,
        "gate": "OK" if mean_ms < MAX_MS else "TOO_SLOW",
    }
    return row, r_res
