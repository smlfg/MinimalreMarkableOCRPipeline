"""Overnight OCR-Benchmark (Linux CPU): synthetisch GERENDERTE Formeln (matplotlib mathtext,
NICHT Handschrift) -> live TexTeller CPU -> structure_bench.score.

Zweck: reproduzierbare Baseline der Pipeline-Struktur (sympy_equal) und Latenz auf dieser
CPU-VM, plus Fehlerverteilung als Eingang fuer die Optimierungsschleife. Kein Anspruch auf
Handschrift-Genauigkeit (Mac MPS / eigene Schrift sind getrennt zu messen, ADR-008).

Aufruf:  .venv_structure/bin/python bench/overnight/benchmark.py [--limit N] [--tag notiz]

Ausgabe:
  bench/overnight/data/png/*.png           gerenderte Bilder (gitignored, deterministisch)
  bench/overnight/data/manifest.jsonl      id, category, gt_latex, is_false, png
  bench/overnight/data/results.jsonl       je Zeile: GT, TexTeller, Metriken, Latenz
  bench/overnight/results.tsv              eine Zeile pro Lauf (append)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import structure_bench as sb  # noqa: E402
from PIL import Image  # noqa: E402

from ocr.pre import MIN_TEXTELLER_HEIGHT, ensure_min_height  # noqa: E402

# ---------------------------------------------------------------- Dataset (fest, dokumentiert)
# Jeder Eintrag: (category, gt_latex, is_false). GT = was geschrieben wurde (nie korrigiert).
DATASET = [
    # --- basic: Schulalgebra ---
    ("basic", r"2x+4=8", False),
    ("basic", r"x^{2}+3x+2=0", False),
    ("basic", r"7+5=13", True),
    ("basic", r"17\cdot 3=51", False),
    ("basic", r"17\cdot 3=50", True),
    ("basic", r"3x-7=14", False),
    ("basic", r"9x=81", False),
    ("basic", r"x=9", False),
    # --- fraction: Brueche ---
    ("fraction", r"\frac{1}{2}+\frac{1}{3}=\frac{5}{6}", False),
    ("fraction", r"\frac{1}{2}+\frac{1}{3}=\frac{2}{5}", True),
    ("fraction", r"\frac{a}{b}+\frac{c}{d}=\frac{ad+bc}{bd}", False),
    ("fraction", r"\frac{x^{2}-1}{x^{2}}", False),
    ("fraction", r"\frac{9}{9}+\frac{9}{4}=\frac{18}{13}", True),
    ("fraction", r"\frac{2}{3}\cdot\frac{3}{4}=\frac{1}{2}", False),
    # --- power: Potenzen ---
    ("power", r"x^{2}\cdot x^{3}=x^{5}", False),
    ("power", r"x^{2}\cdot x^{3}=x^{6}", True),
    ("power", r"(x^{2})^{3}=x^{6}", False),
    ("power", r"a^{b^{c}}", False),
    ("power", r"x^{10}+3x^{2}=0", False),
    ("power", r"2^{10}=1024", False),
    # --- root: Wurzeln ---
    ("root", r"\sqrt{x^{2}+1}", False),
    ("root", r"\sqrt{16}=4", False),
    ("root", r"\sqrt{2}", False),
    ("root", r"\sqrt[3]{8}=2", False),
    ("root", r"\sqrt{1}\cdot\sqrt{1}=\sqrt{-1}\cdot\sqrt{-1}", True),
    # --- trig: Trigonometrie ---
    ("trig", r"\cos^{2}(x)+\sin^{2}(x)=1", False),
    ("trig", r"\cos(\pi)=-1", False),
    ("trig", r"\cos(\pi)=1", True),
    ("trig", r"\sin(2x)=2\sin(x)\cos(x)", False),
    ("trig", r"\tan(x)=\frac{\sin(x)}{\cos(x)}", False),
    ("trig", r"\cos(\frac{\pi}{3})=\frac{1}{2}", False),
    # --- integral: Integrale ---
    ("integral", r"\int x^{2}\,dx", False),
    ("integral", r"\int_{0}^{1}x^{2}\,dx=\frac{1}{3}", False),
    ("integral", r"\int_{0}^{1}x\,dx=1", True),
    ("integral", r"\int_{-\infty}^{\infty}e^{-x^{2}}\,dx", False),
    ("integral", r"\int\frac{1}{x}\,dx=\ln(x)", False),
    ("integral", r"\int_{a}^{b}f(x)\,dx", False),
    # --- special: Konstanten/Symbole ---
    ("special", r"e^{i\pi}+1=0", False),
    ("special", r"e^{i\pi}=1", True),
    ("special", r"\pi r^{2}", False),
    ("special", r"i^{2}=-1", False),
    ("special", r"i^{2}=1", True),
    ("special", r"\sum_{k=1}^{n}k=\frac{n(n+1)}{2}", False),
    ("special", r"\lim_{x\to 0}\frac{\sin(x)}{x}=1", False),
    ("special", r"\alpha^{2}+\beta^{2}=\theta", False),
    # --- mult_decimal: Malpunkt / Dezimalkomma ---
    ("mult_decimal", r"17.3=51", True),
    ("mult_decimal", r"0.5+0.5=1", False),
    ("mult_decimal", r"3\cdot 10+3\cdot 7=51", False),
    ("mult_decimal", r"4.8=32", True),
    ("mult_decimal", r"6\cdot 7=42", False),
]


def render(gt_latex: str, out_png: Path) -> None:
    """mathtext -> PNG (tight, hohe Aufloesung)."""
    fig = plt.figure(figsize=(7, 1.1))
    fig.text(0.01, 0.5, "$" + gt_latex + "$", fontsize=26)
    fig.savefig(out_png, dpi=120, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def build_manifest(limit: int | None) -> list[dict]:
    data = HERE / "data"
    png_dir = data / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (cat, gt, is_false) in enumerate(DATASET):
        if limit is not None and i >= limit:
            break
        rid = f"overnight_{i:03d}"
        png = png_dir / f"{rid}.png"
        render(gt, png)
        rows.append({"id": rid, "category": cat, "gt_latex": gt,
                     "is_false": is_false, "png": str(png.relative_to(ROOT))})
    (data / "manifest.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return rows


def run_texter(rows: list[dict]) -> None:
    """TexTeller einmal laden, alle Bilder -> latex + echte CPU-Sekunden."""
    import torch
    from texteller import img2latex, load_model, load_tokenizer

    t0 = time.perf_counter()
    dev = torch.device("cpu")
    model = load_model(None, use_onnx=False).to(dev)
    tok = load_tokenizer(None)
    print(f"TexTeller geladen in {time.perf_counter() - t0:.1f}s (Linux CPU)", file=sys.stderr)
    paths = [str(ROOT / r["png"]) for r in rows]
    img2latex(model, tok, [paths[0]], device=dev)  # Warm-up
    out = []
    for r, p in zip(rows, paths):
        a = time.perf_counter()
        im = Image.open(p).convert("L")
        ip = p
        if im.height < MIN_TEXTELLER_HEIGHT:
            ip = str(HERE / "data" / "_pre.png")
            ensure_min_height(im).save(ip)
        latex = img2latex(model, tok, [ip], device=dev)[0]
        dt = time.perf_counter() - a
        latex = latex.strip().strip("$").strip()
        if latex.startswith("\\[") and latex.endswith("\\]"):
            latex = latex[2:-2]
        s = sb.score(r["gt_latex"], latex)
        out.append({"id": r["id"], "category": r["category"], "gt": r["gt_latex"],
                    "is_false": r["is_false"], "pred": latex,
                    "sympy_equal": s["sympy_equal"], "exact": s["exact"],
                    "latex_edit_sim": s["latex_edit_sim"], "tree_sim": s["tree_sim"],
                    "parse_ok": s["parse_ok"], "s": round(dt, 4)})
    (HERE / "data" / "results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    return out


def _commit() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.stdout.strip() or "-"


def report(rows: list[dict], tag: str) -> None:
    n = len(rows)
    struct = sum(1 for r in rows if r["sympy_equal"]) / n
    char = sum(r["latex_edit_sim"] for r in rows) / n
    lat = sorted(r["s"] for r in rows)
    p50, p95 = lat[n // 2], lat[int(n * 0.95) - 1]
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    print(f"n={n}  struct={struct:.3f}  char={char:.3f}  p50={p50:.3f}s  p95={p95:.3f}s")
    for c, rs in sorted(by_cat.items()):
        st = sum(1 for r in rs if r["sympy_equal"]) / len(rs)
        print(f"  {c:<13} n={len(rs):2d}  struct={st:.3f}")
    print("\nFehler (sympy_equal=False):")
    for r in rows:
        if not r["sympy_equal"]:
            print(f"  {r['id']} [{r['category']}] GT={r['gt']!r}\n      TT={r['pred']!r}")
    tsv = HERE / "results.tsv"
    if not tsv.exists():
        tsv.write_text("commit\tstruct\tchar\tp50_s\tp95_s\tn\ttag\n")
    with open(tsv, "a") as f:
        f.write(f"{_commit()}\t{struct:.4f}\t{char:.4f}\t{p50:.3f}\t{p95:.3f}\t{n}\t{tag}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--manifest-only", action="store_true")
    a = ap.parse_args()
    rows = build_manifest(a.limit)
    if a.manifest_only:
        print(f"manifest: {len(rows)} Zeilen in bench/overnight/data/manifest.jsonl")
        return
    out = run_texter(rows)
    report(out, a.tag)


if __name__ == "__main__":
    main()
