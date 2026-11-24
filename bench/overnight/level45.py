"""Level 4-5 Diagnostik-Benchmark: Integrale, Matrizen, Trig, spezielle Symbole.

Synthetisch GERENDERT (matplotlib mathtext + eigene Matrix-Komposition), festes Dataset,
dev/holdout getrennt, in jedem Bucket absichtlich FALSCHE Schuelergleichungen (GT = was
geschrieben wurde, nie korrigiert). Misst live TexTeller CPU gegen structure_bench.score
(sympy_equal = Primaer-Metrik) und protokolliert die Fehlerverteilung.

Aufruf:  venv/bin/python bench/overnight/level45.py [dev|holdout] [--tag notiz]
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import structure_bench as sb  # noqa: E402


# ---------------------------------------------------------------- Dataset (fest, dokumentiert)
# matrix: {"delim": paren|bracket|vbar, "rows": [[zelle, ...], ...]}
DEV = [
    # --- integrals (definit/unbestimmt, Grenzen, dx-Varianten, falsche Werte) ---
    {"c": "integral", "gt": r"\int x^{2}\,dx", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x^{2}\,dx=\frac{1}{3}", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x\,dx=1", "f": True},
    {"c": "integral", "gt": r"\int_{-\infty}^{\infty}e^{-x^{2}}\,dx", "f": False},
    {"c": "integral", "gt": r"\int\frac{1}{x}\,dx=\ln(x)", "f": False},
    {"c": "integral", "gt": r"\int_{a}^{b}f(x)\,dx", "f": False},
    {"c": "integral", "gt": r"\int\sin(x)\,dx=-\cos(x)", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{\pi}\sin(x)\,dx=2", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{2}x^{2}\,dx=8", "f": True},
    {"c": "integral", "gt": r"\int 2x\,dx=x^{2}+C", "f": False},
    {"c": "integral", "gt": r"\int_{1}^{2}\frac{1}{x}\,dx=\ln(2)", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}e^{x}\,dx=e-1", "f": False},
    # --- matrices (numerisch, damit latex2sympy sie parst) ---
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}=7",
     "f": True, "matrix": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{bmatrix}1&2\\3&4\end{bmatrix}",
     "f": False, "matrix": {"delim": "bracket", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{vmatrix}1&2\\3&4\end{vmatrix}=-2",
     "f": False, "matrix": {"delim": "vbar", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2&3\\4&5&6\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "2", "3"], ["4", "5", "6"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2&3\\4&5&6\\7&8&9\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&0\\0&1\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "0"], ["0", "1"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}2&0\\0&3\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["2", "0"], ["0", "3"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}+\begin{pmatrix}5&6\\7&8\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}2&3\\4&5\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["2", "3"], ["4", "5"]]}},
    # --- trig (Identitaeten, echte + falsche) ---
    {"c": "trig", "gt": r"\cos^{2}(x)+\sin^{2}(x)=1", "f": False},
    {"c": "trig", "gt": r"\cos(\pi)=-1", "f": False},
    {"c": "trig", "gt": r"\cos(\pi)=1", "f": True},
    {"c": "trig", "gt": r"\sin(2x)=2\sin(x)\cos(x)", "f": False},
    {"c": "trig", "gt": r"\tan(x)=\frac{\sin(x)}{\cos(x)}", "f": False},
    {"c": "trig", "gt": r"\cos(\frac{\pi}{3})=\frac{1}{2}", "f": False},
    {"c": "trig", "gt": r"\sin(\frac{\pi}{2})=1", "f": False},
    {"c": "trig", "gt": r"\cos(0)=0", "f": True},
    {"c": "trig", "gt": r"\sin(x)+\cos(x)=1", "f": True},
    {"c": "trig", "gt": r"\cos(x)=\cos(x)", "f": False},
    {"c": "trig", "gt": r"\tan(\frac{\pi}{4})=1", "f": False},
    {"c": "trig", "gt": r"\sin^{2}(x)=1-\cos^{2}(x)", "f": False},
    # --- special (i, pi, e, Summe, Limes, unendlich, Relationen, griechisch) ---
    {"c": "special", "gt": r"e^{i\pi}+1=0", "f": False},
    {"c": "special", "gt": r"e^{i\pi}=1", "f": True},
    {"c": "special", "gt": r"\pi r^{2}", "f": False},
    {"c": "special", "gt": r"i^{2}=-1", "f": False},
    {"c": "special", "gt": r"i^{2}=1", "f": True},
    {"c": "special", "gt": r"\sum_{k=1}^{n}k=\frac{n(n+1)}{2}", "f": False},
    {"c": "special", "gt": r"\lim_{x\to 0}\frac{\sin(x)}{x}=1", "f": False},
    {"c": "special", "gt": r"\alpha^{2}+\beta^{2}=\theta", "f": False},
    {"c": "special", "gt": r"e^{x}\cdot e^{y}=e^{x+y}", "f": False},
    {"c": "special", "gt": r"\pi\approx3.14", "f": False},
    {"c": "special", "gt": r"2^{10}=1024", "f": False},
    {"c": "special", "gt": r"\infty-\infty=0", "f": True},
]

HOLDOUT = [
    {"c": "integral", "gt": r"\int_{0}^{1}x\,dx=\frac{1}{2}", "f": False},
    {"c": "integral", "gt": r"\int\cos(x)\,dx=\sin(x)", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x^{3}\,dx=\frac{1}{4}", "f": False},
    {"c": "integral", "gt": r"\int x\,dx=\frac{x^{2}}{2}+C", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{2}2x\,dx=4", "f": False},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}2&1\\1&2\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["2", "1"], ["1", "2"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&1\\1&1\end{pmatrix}",
     "f": False, "matrix": {"delim": "paren", "rows": [["1", "1"], ["1", "1"]]}},
    {"c": "trig", "gt": r"\sin(\frac{\pi}{6})=\frac{1}{2}", "f": False},
    {"c": "trig", "gt": r"\cos(2x)=\cos^{2}(x)-\sin^{2}(x)", "f": False},
    {"c": "trig", "gt": r"\sin(2x)=\sin(x)", "f": True},
    {"c": "special", "gt": r"\sum_{k=0}^{\infty}\frac{1}{2^{k}}=2", "f": False},
    {"c": "special", "gt": r"e^{2}=7.39", "f": False},
    {"c": "special", "gt": r"\pi\approx\frac{22}{7}", "f": False},
]


def render_cell(latex: str, fontsize: int = 26) -> Image.Image:
    fig = plt.figure(figsize=(1.6, 0.7))
    fig.text(0.5, 0.5, "$" + latex + "$", fontsize=fontsize, ha="center", va="center")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    return Image.open(buf).convert("L")


def render_matrix(spec: dict, out: Path) -> None:
    rows = spec["rows"]
    delim = {"paren": ("(", ")"), "bracket": ("[", "]"), "vbar": ("|", "|")}[spec["delim"]]
    cells = [[render_cell(c) for c in row] for row in rows]
    ncol, nrow = len(rows[0]), len(rows)
    colw = [max(cells[r][c].width for r in range(nrow)) for c in range(ncol)]
    rowh = [max(cells[i][c].height for c in range(ncol)) for i in range(nrow)]
    gap, pad = 10, 12
    W = sum(colw) + (ncol - 1) * gap + 2 * pad
    H = sum(rowh) + (nrow - 1) * gap + 2 * pad
    dpad = int(H * 0.9)
    canvas = Image.new("L", (W + 2 * dpad, H), 255)
    y = pad
    for r in range(nrow):
        x = dpad + pad
        for c in range(ncol):
            canvas.paste(cells[r][c], (x, y))
            x += colw[c] + gap
        y += rowh[r] + gap
    for side, glyph in enumerate(delim):
        fig = plt.figure(figsize=(0.5, H / 60))
        fig.text(0.5, 0.5, "$" + glyph + "$", fontsize=int(H * 0.95), ha="center", va="center")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", pad_inches=0.02)
        plt.close(fig)
        g = Image.open(buf).convert("L")
        g = g.resize((max(1, int(g.width * H / g.height)), H))
        canvas.paste(g, (dpad - g.width if side == 0 else W + dpad, 0))
    canvas.save(out)


def render(item: dict, out: Path) -> None:
    if item["c"] == "matrix":
        render_matrix(item["matrix"], out)
    else:
        fig = plt.figure(figsize=(7, 1.1))
        fig.text(0.01, 0.5, "$" + item["gt"] + "$", fontsize=26)
        fig.savefig(out, dpi=120, bbox_inches="tight", pad_inches=0.06)
        plt.close(fig)


def build(split: str) -> list[dict]:
    data = HERE / "data" / "level45"
    png_dir = data / split
    png_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, item in enumerate(DEV if split == "dev" else HOLDOUT):
        rid = f"l45_{split}_{i:02d}"
        png = png_dir / f"{rid}.png"
        render(item, png)
        r = {"id": rid, "category": item["c"], "gt_latex": item["gt"],
             "is_false": item["f"], "png": str(png.relative_to(ROOT))}
        rows.append(r)
    (data / f"{split}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return rows


def run_texter(rows: list[dict]) -> list[dict]:
    import torch
    from texteller import img2latex, load_model, load_tokenizer
    t0 = time.perf_counter()
    dev = torch.device("cpu")
    model = load_model(None, use_onnx=False).to(dev)
    tok = load_tokenizer(None)
    print(f"TexTeller geladen in {time.perf_counter()-t0:.1f}s (Linux CPU)", file=sys.stderr)
    paths = [str(ROOT / r["png"]) for r in rows]
    img2latex(model, tok, [paths[0]], device=dev)
    out = []
    for r, p in zip(rows, paths):
        a = time.perf_counter()
        latex = img2latex(model, tok, [p], device=dev)[0]
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
    (HERE / "data" / "level45" / f"results_{'dev' if len(rows) > 30 else 'holdout'}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    return out


def report(rows: list[dict], split: str, tag: str) -> None:
    n = len(rows)
    struct = sum(1 for r in rows if r["sympy_equal"]) / n
    char = sum(r["latex_edit_sim"] for r in rows) / n
    lat = sorted(r["s"] for r in rows)
    p50, p95 = lat[n // 2], lat[int(n * 0.95) - 1]
    by = {}
    for r in rows:
        by.setdefault(r["category"], []).append(r)
    print(f"level45 {split}: n={n}  struct={struct:.3f}  char={char:.3f}  p50={p50:.3f}s  p95={p95:.3f}s")
    for c in ("integral", "matrix", "trig", "special"):
        rs = by.get(c, [])
        if rs:
            print(f"  {c:<9} n={len(rs):2d}  struct={sum(1 for r in rs if r['sympy_equal'])/len(rs):.3f}")
    print("Fehler (sympy_equal=False):")
    for r in rows:
        if not r["sympy_equal"]:
            print(f"  {r['id']} [{r['category']}] GT={r['gt']!r}\n      TT={r['pred']!r}")
    tsv = HERE / "results_level45.tsv"
    if not tsv.exists():
        tsv.write_text("commit\tsplit\tstruct\tchar\tp50_s\tp95_s\tn\ttag\n")
    with open(tsv, "a") as f:
        f.write(f"{_commit()}\t{split}\t{struct:.4f}\t{char:.4f}\t{p50:.3f}\t{p95:.3f}\t{n}\t{tag}\n")


def _commit() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.stdout.strip() or "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("split", nargs="?", default="dev", choices=["dev", "holdout"])
    ap.add_argument("--tag", default="baseline")
    a = ap.parse_args()
    rows = build(a.split)
    out = run_texter(rows)
    report(out, a.split, a.tag)


if __name__ == "__main__":
    main()
