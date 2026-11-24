"""End-to-End Mehrzeilen-Benchmark (live TexTeller CPU): gerenderte mehrzeilige Rechenseiten.

Synthetisch GERENDERT (matplotlib mathtext, NICHT Handschrift), festes Dataset. Ablauf wie die
echte Pipeline: Seite rendern -> Zeilen mit Boxen segmentieren (ocr/pre.split_lines_with_boxes)
-> jede Zeile live mit TexTeller lesen -> Ketten gruppieren (ocr/multiline.py).

Gemessen (Zeilen-Metrik = `same()`, wie vorgegeben — leading '='-Fortsetzungen sind nicht
eigenstaendig parsebar, `same` nutzt dort den Normalisierungs-Exaktpfad):
- line_struct:  Anteil Zeilen mit same(GT, read)=True
- chain_recall: Anteil GT-Ketten, deren Zeilen zu genau EINER Gruppe werden
- chain_exact:  Anteil Seiten, deren Gruppierungs-Partition exakt der GT entspricht
- merge_fp:     Anzahl GT-Ketten, die mit einer anderen verschmolzen wurden
- student_error_preserved: Anteil falscher Zeilen, die treu falsch gelesen wurden (same(read,gt))
- anti_domino:  strukturell 100 % (Gruppierung aendert nie eine Zeile; hier zusaetzlich geprueft)
- p50/p95:      Linux CPU (NICHT Mac MPS)

Aufruf: venv/bin/python bench/overnight/multiline_bench.py [--tag notiz]
"""
from __future__ import annotations

import argparse
import io
import json
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

from ocr.latex import same  # noqa: E402
from ocr.multiline import group_lines  # noqa: E402
from ocr.pre import split_lines_with_boxes  # noqa: E402

# page = {"id": str, "exercises": [[line, ...], ...]}; "exercise" = eine Kette.
# Ein line-Eintrag ist entweder ein str (richtig) oder (latex, True) fuer eine FALSCHE Zeile.
PAGES = [
    {"id": "p01", "exercises": [[r"(x+y)^{3}", r"=(x+y)(x+y)^{2}",
                                 r"=x^{3}+3x^{2}y+3xy^{2}+y^{3}"]]},
    {"id": "p02", "exercises": [[r"x^{2}-5x+6=0", r"=(x-2)(x-3)"]]},
    {"id": "p03", "exercises": [[r"2x+4=8", r"2x=4", r"x=2"]]},
    {"id": "p04", "exercises": [[r"\frac{1}{2}+\frac{1}{3}", r"=\frac{3}{6}+\frac{2}{6}",
                                 r"=\frac{5}{6}"]]},
    {"id": "p05", "exercises": [[r"17\cdot3", r"=30+21", r"=51"]]},
    {"id": "p06", "exercises": [[r"\sin(2x)", r"=2\sin(x)\cos(x)"]]},
    {"id": "p07", "exercises": [[r"\int_{0}^{1}x^{2}dx", r"=\frac{1}{3}"]]},
    {"id": "p08", "exercises": [[r"(a+b)^{2}", r"=a^{2}+2ab+b^{2}"]]},
    # falscher Schuelerschritt (41 statt 51): bleibt falsch, wird NICHT korrigiert
    {"id": "p09", "exercises": [[r"17\cdot3", r"=30+21", (r"=41", True)]]},
    {"id": "p10", "exercises": [[r"x^{2}-9=0", r"x^{2}=9", r"x=3"]]},
    # falscher Rechenschritt (2x=10 statt 2x=-4)
    {"id": "p11", "exercises": [[r"4x-7=2x+3", (r"2x=10", True), (r"x=5", True)]]},
    # Mehr-Aufgaben-Seite (durch Luecke getrennt): muss getrennt bleiben
    {"id": "p12", "exercises": [[r"2x=6", r"x=3"], [r"3y=12", r"y=4"]]},
    {"id": "p13", "exercises": [[r"x+1=5", r"x=4"], [r"y-2=3", r"y=5"],
                                [r"z+4=10", r"z=6"]]},
    {"id": "p14", "exercises": [[r"(x+1)(x+2)", r"=x^{2}+3x+2"]]},
    {"id": "p15", "exercises": [[r"e^{i\pi}", r"=-1"]]},
]

X0, PAD, LGAP, EXGAP, FS = 60, 40, 22, 110, 26


def _norm_ex(ex):
    return [(t, False) if isinstance(t, str) else (t[0], bool(t[1])) for t in ex]


def _line_img(latex: str) -> Image.Image:
    fig = plt.figure(figsize=(7, 1.0))
    fig.text(0.01, 0.5, "$" + latex + "$", fontsize=FS)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    return Image.open(buf).convert("L")


def render_page(page: dict, out_png: Path) -> list[dict]:
    imgs = []
    for ex_i, ex in enumerate(page["exercises"]):
        for li, (latex, is_false) in enumerate(_norm_ex(ex)):
            imgs.append((ex_i, li, latex, is_false, _line_img(latex)))
    W = max(im.width for *_, im in imgs) + 2 * X0 + 2 * PAD
    y, gt = PAD, []
    for ex_i, li, latex, is_false, im in imgs:
        if li == 0 and ex_i > 0:
            y += EXGAP
        gt.append({"ex": ex_i, "latex": latex, "is_false": is_false,
                   "bbox": [X0, y, X0 + im.width, y + im.height]})
        y += im.height + LGAP
    canvas = Image.new("L", (W, y + PAD), 255)
    for (ex_i, li, latex, is_false, im), g in zip(imgs, gt):
        canvas.paste(im, (X0, g["bbox"][1]))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png)
    return gt


def _overlap(a, b) -> float:
    return max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _clean(latex: str) -> str:
    s = latex.strip().strip("$").strip()
    if s.startswith("\\[") and s.endswith("\\]"):
        s = s[2:-2].strip()
    return s


def _match(seg_boxes, gt) -> list[int]:
    out = []
    for sb_ in seg_boxes:
        best, best_ov = -1, 0.0
        for gi, g in enumerate(gt):
            ov = _overlap(sb_, g["bbox"])
            if ov > best_ov:
                best, best_ov = gi, ov
        out.append(best)
    return out


def run(rows_pages):
    import torch
    from texteller import img2latex, load_model, load_tokenizer
    dev = torch.device("cpu")
    t0 = time.perf_counter()
    model = load_model(None, use_onnx=False).to(dev)
    tok = load_tokenizer(None)
    print(f"TexTeller geladen in {time.perf_counter()-t0:.1f}s (Linux CPU)", file=sys.stderr)
    # Warm-up (erste Inferenz ist sonst ein Latenz-Ausreisser)
    first_chunks = split_lines_with_boxes(Image.open(rows_pages[0][2]).convert("L"))
    if first_chunks:
        wu = HERE / "data" / "multiline" / "_warm.png"
        first_chunks[0][0].save(wu)
        img2latex(model, tok, [str(wu)], device=dev)
    line_ok, lat = [], []
    chain_hit = chain_total = exact_pages = merge_chains = 0
    false_lines = false_preserved = 0
    anti_domino_ok = True
    mismatch_pages = []
    for page, gt, png in rows_pages:
        chunks = split_lines_with_boxes(Image.open(png).convert("L"))
        seg_boxes = [b for _, b in chunks]
        if len(chunks) != len(gt):
            mismatch_pages.append((page["id"], len(chunks), len(gt)))
        mapping = _match(seg_boxes, gt)
        recs = []
        tmp = HERE / "data" / "multiline" / "_tmp.png"
        for img, bbox in chunks:
            img.save(tmp)
            a = time.perf_counter()
            latex = img2latex(model, tok, [str(tmp)], device=dev)[0]
            lat.append(time.perf_counter() - a)
            recs.append({"latex": _clean(latex), "bbox": bbox,
                         "uncertain": False, "math_status": None})
        order = sorted(range(len(recs)), key=lambda i: (recs[i]["bbox"][1], recs[i]["bbox"][0]))
        ordered = [recs[i] for i in order]
        mapping_ord = [mapping[i] for i in order]
        groups = group_lines(ordered)
        if any(r["uncertain"] for r in ordered):     # Anti-Domino: nichts darf kippen
            anti_domino_ok = False
        for i, rec in enumerate(ordered):
            g = gt[mapping_ord[i]]
            line_ok.append(same(g["latex"], rec["latex"]))
            if g["is_false"]:
                false_lines += 1
                false_preserved += same(rec["latex"], g["latex"])
        gt_chains = {}
        for i, gi in enumerate(mapping_ord):
            gt_chains.setdefault(gt[gi]["ex"], set()).add(i)
        group_of = {i: grp["id"] for grp in groups for i in grp["line_indices"]}
        group_ex = {}
        page_exact = True
        for ex, idxs in gt_chains.items():
            gids = {group_of[i] for i in idxs}
            chain_total += 1
            if len(gids) == 1:
                chain_hit += 1
                group_ex.setdefault(next(iter(gids)), set()).add(ex)
            else:
                page_exact = False
        for gid, exs in group_ex.items():
            if len(exs) > 1:
                merge_chains += len(exs)
                page_exact = False
        exact_pages += page_exact
    n = len(line_ok)
    ls = sorted(lat)
    return {
        "pages": len(rows_pages), "n_lines": n,
        "line_struct": sum(1 for x in line_ok if x) / max(1, n),
        "chain_recall": chain_hit / max(1, chain_total),
        "chain_exact_pages": exact_pages / max(1, len(rows_pages)),
        "merge_fp_chains": merge_chains,
        "student_error_preserved": false_preserved / max(1, false_lines),
        "n_false_lines": false_lines,
        "anti_domino": anti_domino_ok,
        "seg_mismatch": mismatch_pages,
        "p50": ls[len(ls) // 2], "p95": ls[int(len(ls) * 0.95) - 1],
    }


def _commit() -> str:
    import subprocess
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True, cwd=str(ROOT)).stdout.strip() or "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--manifest-only", action="store_true")
    a = ap.parse_args()
    data = HERE / "data" / "multiline"
    data.mkdir(parents=True, exist_ok=True)
    rows_pages = []
    for page in PAGES:
        png = data / f"{page['id']}.png"
        gt = render_page(page, png)
        rows_pages.append((page, gt, png))
    (data / "manifest.jsonl").write_text("".join(
        json.dumps({"id": p["id"], "exercises": p["exercises"]}, ensure_ascii=False) + "\n"
        for p in PAGES))
    if a.manifest_only:
        for page, gt, _ in rows_pages:
            print(f"  {page['id']}: {len(gt)} GT-Zeilen")
        return
    res = run(rows_pages)
    print(f"multiline: pages={res['pages']} lines={res['n_lines']}  line_struct={res['line_struct']:.3f}")
    print(f"  chain_recall={res['chain_recall']:.3f}  chain_exact_pages={res['chain_exact_pages']:.3f}  "
          f"merge_fp_chains={res['merge_fp_chains']}")
    print(f"  student_error_preserved={res['student_error_preserved']:.3f} "
          f"(n_false={res['n_false_lines']})  anti_domino={res['anti_domino']}")
    print(f"  seg_mismatch={res['seg_mismatch']}")
    print(f"  p50={res['p50']:.3f}s  p95={res['p95']:.3f}s  (Linux CPU)")
    tsv = HERE / "results_multiline.tsv"
    if not tsv.exists():
        tsv.write_text("commit\tpages\tlines\tline_struct\tchain_recall\tchain_exact_pages\t"
                       "merge_fp\tsep\tanti_domino\tp50_s\tp95_s\ttag\n")
    with open(tsv, "a") as f:
        f.write(f"{_commit()}\t{res['pages']}\t{res['n_lines']}\t{res['line_struct']:.4f}\t"
                f"{res['chain_recall']:.4f}\t{res['chain_exact_pages']:.4f}\t"
                f"{res['merge_fp_chains']}\t{res['student_error_preserved']:.4f}\t"
                f"{int(res['anti_domino'])}\t{res['p50']:.3f}\t{res['p95']:.3f}\t{a.tag}\n")
    (data / "results.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
