"""Struktur-Benchmark fuer Formel-Erkennung (Glue ueber Upstream-Bausteine).

Bausteine: latex2sympy2_extended (LaTeX->SymPy), sympy (Aequivalenz),
apted (Tree-Edit-Distance), rapidfuzz (Levenshtein). Siehe
docs/research/UPSTREAM_SEARCH-struktur-benchmark.md.

Aufruf (eigene venv):
  .venv_structure/bin/python bench/structure_bench.py <manifest.jsonl> --pred <pred.jsonl>
  .venv_structure/bin/python bench/structure_bench.py --selftest
Hauptmetrik: sympy_equal-Rate (None/Parse-Fehler zaehlt als falsch).
"""
import argparse, json, re, sys
from pathlib import Path

import sympy
from apted import APTED
from apted.helpers import Tree
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocr.latex import normalize, parse, equivalent_expr as _eq  # eine Quelle mit der Pipeline
from rapidfuzz.distance import Levenshtein


def _tree(e) -> Tree:
    label = type(e).__name__ if e.args else str(e)
    t = Tree(label)
    for a in e.args:
        t.children.append(_tree(a))
    return t


def _size(t: Tree) -> int:
    return 1 + sum(_size(c) for c in t.children)


def score(gt_latex: str, pred_latex: str) -> dict:
    g, p = normalize(gt_latex), normalize(pred_latex)
    out = {"exact": g == p,
           "latex_edit_sim": Levenshtein.normalized_similarity(g, p),
           "tree_sim": None, "sympy_equal": None, "parse_ok": False}
    ge, pe = parse(gt_latex), parse(pred_latex)
    out["parse_ok"] = pe is not None
    if out["exact"]:  # identisches LaTeX ist per Definition gleich; der Parser liest Leerzeichen-Varianten sonst verschieden
        out.update(tree_sim=1.0, sympy_equal=True)
        return out
    if ge is None or pe is None:
        return out
    try:  # Matrizen u. ä. haben kein .args -> tree_sim bleibt None statt Absturz
        t1, t2 = _tree(ge), _tree(pe)
        dist = APTED(t1, t2).compute_edit_distance()
        out["tree_sim"] = max(0.0, 1 - dist / max(_size(t1), _size(t2)))
    except Exception:
        out["tree_sim"] = None
    try:
        out["sympy_equal"] = bool(_eq(ge, pe))
    except Exception:
        out["sympy_equal"] = None
    return out


METRICS = ["exact", "latex_edit_sim", "tree_sim", "sympy_equal", "parse_ok"]


def _num(v):  # strikt: None (nicht parsebar) zaehlt als 0
    return float(v) if v is not None else 0.0


def run(rows, preds):
    res = []
    for r in rows:
        pred = preds.get(r["id"])
        if pred is None:
            continue
        res.append((r["id"], score(r["gt_latex"], pred)))
    print(f"{'id':<14}" + "".join(f"{m:>16}" for m in METRICS))
    for i, s in res:
        print(f"{i:<14}" + "".join(f"{str(round(s[m], 3)) if isinstance(s[m], float) else str(s[m]):>16}" for m in METRICS))
    if res:
        print(f"{'MEAN(n=%d)' % len(res):<14}" + "".join(f"{sum(_num(s[m]) for _, s in res) / len(res):>16.3f}" for m in METRICS))
        print("(None zaehlt als 0; Hauptmetrik = sympy_equal)")
    return res


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def selftest() -> int:
    pairs = [
        ("same", r"\frac{\cos^2(x)-1}{x^2}", r"\frac{\cos^2(x)-1}{x^2}"),
        ("flat_frac", r"\frac{\cos^2(x)-1}{x^2}", "cos(x)-1 x^2"),
        ("dot_vs_x", r"17\cdot 3=3\cdot 10+3\cdot 7", r"17\times 3=3\times 10+3\times 7"),
        ("digit_err", "2x+4=8", "2x+4=9"),
        ("reorder", "x^2+2x+1", "1+2x+x^2"),
    ]
    rows = [{"id": i, "gt_latex": g} for i, g, _ in pairs]
    res = dict(run(rows, {i: p for i, _, p in pairs}))
    ok = (res["same"]["exact"] and res["same"]["tree_sim"] == 1 and res["same"]["sympy_equal"] is True
          and res["flat_frac"]["sympy_equal"] is False and res["flat_frac"]["tree_sim"] < 0.5
          and res["dot_vs_x"]["sympy_equal"] is True
          and res["digit_err"]["sympy_equal"] is False
          and res["reorder"]["sympy_equal"] is True)
    print("SELFTEST", "OK" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="?")
    ap.add_argument("--pred")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not (a.manifest and a.pred):
        ap.error("manifest und --pred noetig (oder --selftest)")
    rows = load_jsonl(a.manifest)
    preds = {r["id"]: r["pred_latex"] for r in load_jsonl(a.pred)}
    run(rows, preds)


if __name__ == "__main__":
    main()
