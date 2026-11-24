"""Latenz-Benchmark: live TexTeller CPU auf dieser VM, sauber gemessen und protokolliert.

Andere Hardwarebedingungen als der Mac-MPS-Baseline (results_2026-11-23.tsv: p95 0,32 s dev,
0,23 s own_probe) bewusst gegenuebergestellt — CPU ist kein MPS.

- Modell einmal laden (Ladezeit separat), Warm-up, dann N Durchlaeufe ueber den Datensatz.
- Berichtet p50/p95/min/max pro Formel + Gesamtdurchsatz, protokolliert nach
  bench/overnight/results.tsv (tag=latency-*).

Aufruf: venv/bin/python bench/overnight/latency.py [passes=3]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def commit() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=str(ROOT))
    return r.stdout.strip() or "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("passes", type=int, nargs="?", default=3)
    a = ap.parse_args()

    import torch
    from texteller import img2latex, load_model, load_tokenizer

    manifest = [json.loads(l) for l in Path(HERE / "data" / "manifest.jsonl").read_text().splitlines() if l.strip()]
    paths = [str(ROOT / r["png"]) for r in manifest]

    t0 = time.perf_counter()
    dev = torch.device("cpu")
    model = load_model(None, use_onnx=False).to(dev)
    tok = load_tokenizer(None)
    load_s = time.perf_counter() - t0
    print(f"TexTeller geladen: {load_s:.2f}s (Linux CPU)", file=sys.stderr)

    for _ in range(3):  # Warm-up
        img2latex(model, tok, [paths[0]], device=dev)

    lat = []
    for k in range(a.passes):
        for p in paths:
            t = time.perf_counter()
            img2latex(model, tok, [p], device=dev)
            lat.append(time.perf_counter() - t)
        print(f"pass {k + 1}/{a.passes} fertig ({len(paths)} Formeln)", file=sys.stderr)

    lat.sort()
    n = len(lat)
    stats = {
        "n": n, "load_s": round(load_s, 2),
        "p50": round(lat[n // 2], 4), "p95": round(lat[int(n * 0.95) - 1], 4),
        "min": round(lat[0], 4), "max": round(lat[-1], 4),
        "throughput_img_s": round(n / sum(lat), 2),
    }
    print(json.dumps(stats, indent=1))

    tsv = HERE / "results.tsv"
    if not tsv.exists():
        tsv.write_text("commit\tstruct\tchar\tp50_s\tp95_s\tn\ttag\n")
    with open(tsv, "a") as f:
        f.write(f"{commit()}\t-\t-\t{stats['p50']}\t{stats['p95']}\t{stats['n']}\t"
                f"latency-{a.passes}passes-load{stats['load_s']:.1f}s\n")


if __name__ == "__main__":
    main()
