"""Level 4-5 Diagnostik-Benchmark: Integrale, Matrizen, Trig, spezielle Symbole.

Synthetisch GERENDERT (matplotlib mathtext + eigene Matrix-Komposition), festes Dataset,
dev/holdout getrennt mit null Ueberlappung, in jedem Bucket absichtlich FALSCHE
Schuelergleichungen (GT = was geschrieben wurde, nie korrigiert). Misst live TexTeller CPU
gegen structure_bench.score (sympy_equal = Primaer-Metrik) und protokolliert Fehlerverteilung,
Parse-Fehler-Rate und student_error_preserved (Anteil der falschen Aussagen, die treu gelesen
wurden — stille Korrektur waere ein Verstoß gegen Issue #1).

Matrizen werden als Zell-Grid mit klar getrennten Spalten gerendert (fontsize 30, Spaltengap
25 px): Pass-3-Messung zeigte, dass zu enge Zellen (fs 26, gap 10) TexTeller zur '&'-Loss
verleiten — ein Rendering-Artefakt, kein TexTeller-Problem.

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
from ocr.latex import normalize  # noqa: E402
from ocr.pre import MIN_TEXTELLER_HEIGHT, ensure_min_height  # noqa: E402

# ---------------------------------------------------------------- Renderer
DELIMS = {"paren": ("(", ")"), "bracket": ("[", "]"), "vbar": ("|", "|")}
GAP, PAD, FS = 25, 16, 30


def _cell(latex: str, fs: int = FS) -> Image.Image:
    fig = plt.figure(figsize=(1.8, 0.8))
    fig.text(0.5, 0.5, "$" + latex + "$", fontsize=fs, ha="center", va="center")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    return Image.open(buf).convert("L")


def _paste_row(imgs: list[Image.Image], gap: int = 34) -> Image.Image:
    h = max(i.height for i in imgs)
    w = sum(i.width for i in imgs) + gap * (len(imgs) - 1) + 2 * PAD
    cv = Image.new("L", (w, h + 2 * PAD), 255)
    x = PAD
    for i in imgs:
        cv.paste(i, (x, (h - i.height) // 2 + PAD))
        x += i.width + gap
    return cv


def _matrix_img(spec: dict) -> Image.Image:
    rows = spec["rows"]
    d = DELIMS[spec["delim"]]
    cells = [[_cell(c) for c in row] for row in rows]
    ncol, nrow = len(rows[0]), len(rows)
    colw = [max(cells[r][c].width for r in range(nrow)) for c in range(ncol)]
    rowh = [max(cells[i][c].height for c in range(ncol)) for i in range(nrow)]
    W = sum(colw) + (ncol - 1) * GAP + 2 * PAD
    H = sum(rowh) + (nrow - 1) * GAP + 2 * PAD
    dpad = int(H * 0.9)
    cv = Image.new("L", (W + 2 * dpad, H), 255)
    y = PAD
    for r in range(nrow):
        x = dpad + PAD
        for c in range(ncol):
            cv.paste(cells[r][c], (x, y))
            x += colw[c] + GAP
        y += rowh[r] + GAP
    for side, glyph in enumerate(d):
        fig = plt.figure(figsize=(0.5, H / 60))
        fig.text(0.5, 0.5, "$" + glyph + "$", fontsize=int(H * 0.95), ha="center", va="center")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", pad_inches=0.02)
        plt.close(fig)
        g = Image.open(buf).convert("L")
        g = g.resize((max(1, int(g.width * H / g.height)), H))
        cv.paste(g, (dpad - g.width if side == 0 else W + dpad, 0))
    return cv


def _render_matrix_item(mx: dict, out: Path) -> None:
    if "parts" in mx:  # z. B. Matrix + Matrix oder A + B = C
        imgs = [_matrix_img(p) if isinstance(p, dict) else _cell(p) for p in mx["parts"]]
        _paste_row(imgs).save(out)
    else:
        im = _matrix_img(mx)
        if mx.get("tail"):
            _paste_row([im, _cell(mx["tail"])]).save(out)
        else:
            im.save(out)


def render(item: dict, out: Path) -> None:
    if item["c"] == "matrix":
        _render_matrix_item(item["mx"], out)
    else:
        fig = plt.figure(figsize=(7, 1.1))
        fig.text(0.01, 0.5, "$" + item["gt"] + "$", fontsize=FS)
        fig.savefig(out, dpi=120, bbox_inches="tight", pad_inches=0.06)
        plt.close(fig)


# ---------------------------------------------------------------- Dataset (fest, dokumentiert)
# mx-Spec: {"delim": paren|bracket|vbar, "rows": [[zelle,...],...], "tail": "= x"}
#          oder {"parts": [matrix|operator, ...]} fuer A+B / A+B=C.
DEV = [
    # --- integrals (18) ---
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
    {"c": "integral", "gt": r"\int\cos(x)\,dx=\sin(x)", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{3}x\,dx=\frac{9}{2}", "f": False},
    {"c": "integral", "gt": r"\int x^{3}\,dx=\frac{x^{4}}{4}", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x\,\mathrm{d}x=\frac{1}{2}", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x^{2}\,dx=\frac{1}{2}", "f": True},
    {"c": "integral", "gt": r"\int\cos(x)\,dx=\cos(x)", "f": True},
    # --- matrices (16), numerisch (latex2sympy parst keine symbolischen Matrizen) ---
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}=7",
     "f": True, "mx": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]], "tail": "= 7"}},
    {"c": "matrix", "gt": r"\begin{bmatrix}1&2\\3&4\end{bmatrix}",
     "f": False, "mx": {"delim": "bracket", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{vmatrix}1&2\\3&4\end{vmatrix}=-2",
     "f": False, "mx": {"delim": "vbar", "rows": [["1", "2"], ["3", "4"]], "tail": "= -2"}},
    {"c": "matrix", "gt": r"\begin{vmatrix}1&2\\3&4\end{vmatrix}=2",
     "f": True, "mx": {"delim": "vbar", "rows": [["1", "2"], ["3", "4"]], "tail": "= 2"}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2&3\\4&5&6\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["1", "2", "3"], ["4", "5", "6"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2&3\\4&5&6\\7&8&9\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&0\\0&1\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["1", "0"], ["0", "1"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}2&0\\0&3\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["2", "0"], ["0", "3"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}+\begin{pmatrix}5&6\\7&8\end{pmatrix}",
     "f": False, "mx": {"parts": [{"delim": "paren", "rows": [["1", "2"], ["3", "4"]]},
                                   "+", {"delim": "paren", "rows": [["5", "6"], ["7", "8"]]}]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}-1&2\\3&-4\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["-1", "2"], ["3", "-4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}\frac{1}{2}&2\\3&\frac{1}{4}\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [[r"\frac{1}{2}", "2"], ["3", r"\frac{1}{4}"]]}},
    {"c": "matrix", "gt": r"\begin{bmatrix}-1&-2\\-3&-4\end{bmatrix}",
     "f": False, "mx": {"delim": "bracket", "rows": [["-1", "-2"], ["-3", "-4"]]}},
    {"c": "matrix", "gt": r"\begin{vmatrix}2&0\\0&3\end{vmatrix}=6",
     "f": False, "mx": {"delim": "vbar", "rows": [["2", "0"], ["0", "3"]], "tail": "= 6"}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&1\\1&1\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["1", "1"], ["1", "1"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}+\begin{pmatrix}5&6\\7&8\end{pmatrix}=\begin{pmatrix}7&8\\10&12\end{pmatrix}",
     "f": True, "mx": {"parts": [{"delim": "paren", "rows": [["1", "2"], ["3", "4"]]},
                                 "+", {"delim": "paren", "rows": [["5", "6"], ["7", "8"]]},
                                 "=", {"delim": "paren", "rows": [["7", "8"], ["10", "12"]]}]}},
    # --- trig (18) ---
    {"c": "trig", "gt": r"\cos^{2}(x)+\sin^{2}(x)=1", "f": False},
    {"c": "trig", "gt": r"\cos(\pi)=-1", "f": False},
    {"c": "trig", "gt": r"\cos(\pi)=1", "f": True},
    {"c": "trig", "gt": r"\sin(2x)=2\sin(x)\cos(x)", "f": False},
    {"c": "trig", "gt": r"\tan(x)=\frac{\sin(x)}{\cos(x)}", "f": False},
    {"c": "trig", "gt": r"\cos(\frac{\pi}{3})=\frac{1}{2}", "f": False},
    {"c": "trig", "gt": r"\sin(\frac{\pi}{2})=1", "f": False},
    {"c": "trig", "gt": r"\cos(0)=0", "f": True},
    {"c": "trig", "gt": r"\sin(x)+\cos(x)=1", "f": True},
    {"c": "trig", "gt": r"\tan(\frac{\pi}{4})=1", "f": False},
    {"c": "trig", "gt": r"\sin^{2}(x)=1-\cos^{2}(x)", "f": False},
    {"c": "trig", "gt": r"\sin(\frac{\pi}{6})=\frac{1}{2}", "f": False},
    {"c": "trig", "gt": r"\cos(2x)=\cos^{2}(x)-\sin^{2}(x)", "f": False},
    {"c": "trig", "gt": r"\tan(\alpha)=\frac{\sin(\alpha)}{\cos(\alpha)}", "f": False},
    {"c": "trig", "gt": r"\sin(2x)=\sin(x)", "f": True},
    {"c": "trig", "gt": r"\cos(2\pi)=2", "f": True},
    {"c": "trig", "gt": r"\sin(0)=1", "f": True},
    {"c": "trig", "gt": r"\sin(\pi)+\cos(\pi)=-1", "f": False},
    # --- special (18) ---
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
    {"c": "special", "gt": r"e^{-x^{2}}", "f": False},
    {"c": "special", "gt": r"x\neq 0", "f": False},
    {"c": "special", "gt": r"x\leq 5", "f": False},
    {"c": "special", "gt": r"x\geq 5", "f": False},
    {"c": "special", "gt": r"\pi+\pi=2\pi", "f": False},
    {"c": "special", "gt": r"a=\pm 1", "f": False},
]

HOLDOUT = [
    # --- integrals (9) ---
    {"c": "integral", "gt": r"\int_{0}^{1}x\,dx=\frac{1}{2}", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x^{3}\,dx=\frac{1}{4}", "f": False},
    {"c": "integral", "gt": r"\int x\,dx=\frac{x^{2}}{2}+C", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{2}2x\,dx=8", "f": True},
    {"c": "integral", "gt": r"\int_{1}^{2}x^{2}\,dx=\frac{7}{3}", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{\pi}\cos(x)\,dx=0", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}e^{x}\,dx=1", "f": True},
    {"c": "integral", "gt": r"\int\frac{1}{x^{2}}\,dx=-\frac{1}{x}", "f": False},
    {"c": "integral", "gt": r"\int_{0}^{1}x^{2}\,\mathrm{d}x=\frac{1}{3}", "f": False},
    # --- matrices (9) ---
    {"c": "matrix", "gt": r"\begin{pmatrix}1&2\\3&4\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["1", "2"], ["3", "4"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}2&1\\1&2\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["2", "1"], ["1", "2"]]}},
    {"c": "matrix", "gt": r"\begin{bmatrix}0&1\\1&0\end{bmatrix}",
     "f": False, "mx": {"delim": "bracket", "rows": [["0", "1"], ["1", "0"]]}},
    {"c": "matrix", "gt": r"\begin{vmatrix}1&0\\0&1\end{vmatrix}=1",
     "f": False, "mx": {"delim": "vbar", "rows": [["1", "0"], ["0", "1"]], "tail": "= 1"}},
    {"c": "matrix", "gt": r"\begin{vmatrix}1&2\\3&4\end{vmatrix}=-1",
     "f": True, "mx": {"delim": "vbar", "rows": [["1", "2"], ["3", "4"]], "tail": "= -1"}},
    {"c": "matrix", "gt": r"\begin{pmatrix}7&8&9\\10&11&12\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["7", "8", "9"], ["10", "11", "12"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}-2&0\\0&-3\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["-2", "0"], ["0", "-3"]]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}1&0\\0&1\end{pmatrix}+\begin{pmatrix}0&1\\1&0\end{pmatrix}",
     "f": False, "mx": {"parts": [{"delim": "paren", "rows": [["1", "0"], ["0", "1"]]},
                                   "+", {"delim": "paren", "rows": [["0", "1"], ["1", "0"]]}]}},
    {"c": "matrix", "gt": r"\begin{pmatrix}3&1\\4&1\end{pmatrix}",
     "f": False, "mx": {"delim": "paren", "rows": [["3", "1"], ["4", "1"]]}},
    # --- trig (9) ---
    {"c": "trig", "gt": r"\sin(\frac{\pi}{6})=\frac{1}{2}", "f": False},
    {"c": "trig", "gt": r"\cos(\frac{\pi}{2})=0", "f": False},
    {"c": "trig", "gt": r"\sin(\pi)=0", "f": False},
    {"c": "trig", "gt": r"\tan(\frac{\pi}{4})=2", "f": True},
    {"c": "trig", "gt": r"\cos(-x)=\cos(x)", "f": False},
    {"c": "trig", "gt": r"\sin^{2}(x)+\cos^{2}(x)=0", "f": True},
    {"c": "trig", "gt": r"\tan(0)=0", "f": False},
    {"c": "trig", "gt": r"\sin(x)\cos(x)=\frac{1}{2}\sin(2x)", "f": False},
    {"c": "trig", "gt": r"\cos(\alpha+\beta)=\cos(\alpha)\cos(\beta)-\sin(\alpha)\sin(\beta)", "f": False},
    # --- special (9) ---
    {"c": "special", "gt": r"\sum_{k=1}^{3}k=6", "f": False},
    {"c": "special", "gt": r"\pi\cdot\pi=\pi^{2}", "f": False},
    {"c": "special", "gt": r"e^{0}=2", "f": True},
    {"c": "special", "gt": r"2^{-1}=\frac{1}{2}", "f": False},
    {"c": "special", "gt": r"\pi=3", "f": True},
    {"c": "special", "gt": r"\theta=\alpha+\beta", "f": False},
    {"c": "special", "gt": r"e^{i\pi}+2=0", "f": True},
    {"c": "special", "gt": r"\lim_{x\to\infty}\frac{1}{x}=0", "f": False},
    {"c": "special", "gt": r"\beta+\gamma=\delta", "f": False},
]


def build(split: str) -> list[dict]:
    data = HERE / "data" / "level45"
    png_dir = data / split
    png_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, item in enumerate(DEV if split == "dev" else HOLDOUT):
        rid = f"l45_{split}_{i:02d}"
        png = png_dir / f"{rid}.png"
        render(item, png)
        rows.append({"id": rid, "category": item["c"], "gt_latex": item["gt"],
                     "is_false": item["f"], "png": str(png.relative_to(ROOT))})
    (data / f"{split}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return rows


def run_texter(rows: list[dict], split: str) -> list[dict]:
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
        im = Image.open(p).convert("L")
        ip = p
        if im.height < MIN_TEXTELLER_HEIGHT:
            ip = str(HERE / "data" / "level45" / "_pre.png")
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
    (HERE / "data" / "level45" / f"results_{split}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    return out


def _commit() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.stdout.strip() or "-"


def report(rows: list[dict], split: str, tag: str) -> None:
    n = len(rows)
    struct = sum(1 for r in rows if r["sympy_equal"]) / n
    char = sum(r["latex_edit_sim"] for r in rows) / n
    parse_err = sum(1 for r in rows if not r["parse_ok"]) / n
    false_rows = [r for r in rows if r["is_false"]]
    sep = (sum(1 for r in false_rows if r["sympy_equal"]) / len(false_rows)) if false_rows else 1.0
    lat = sorted(r["s"] for r in rows)
    p50, p95 = lat[n // 2], lat[int(n * 0.95) - 1]
    by = {}
    for r in rows:
        by.setdefault(r["category"], []).append(r)
    print(f"level45 {split}: n={n}  struct={struct:.3f}  char={char:.3f}  parse_err={parse_err:.3f}  "
          f"student_error_preserved={sep:.3f}  p50={p50:.3f}s  p95={p95:.3f}s  (Linux CPU)")
    for c in ("integral", "matrix", "trig", "special"):
        rs = by.get(c, [])
        if rs:
            print(f"  {c:<9} n={len(rs):2d}  struct={sum(1 for r in rs if r['sympy_equal'])/len(rs):.3f}  "
                  f"parse_err={sum(1 for r in rs if not r['parse_ok'])/len(rs):.3f}")
    print("Fehler (sympy_equal=False):")
    for r in rows:
        if not r["sympy_equal"]:
            print(f"  {r['id']} [{r['category']}] GT={r['gt']!r}\n      TT={r['pred']!r}\n"
                  f"      norm={normalize(r['pred'])!r}")
    tsv = HERE / "results_level45.tsv"
    if not tsv.exists():
        tsv.write_text("commit\tsplit\tstruct\tchar\tparse_err\tsep\tp50_s\tp95_s\tn\ttag\n")
    with open(tsv, "a") as f:
        f.write(f"{_commit()}\t{split}\t{struct:.4f}\t{char:.4f}\t{parse_err:.4f}\t{sep:.4f}"
                f"\t{p50:.3f}\t{p95:.3f}\t{n}\t{tag}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("split", nargs="?", default="dev", choices=["dev", "holdout"])
    ap.add_argument("--tag", default="baseline")
    a = ap.parse_args()
    rows = build(a.split)
    out = run_texter(rows, a.split)
    report(out, a.split, a.tag)


if __name__ == "__main__":
    main()
