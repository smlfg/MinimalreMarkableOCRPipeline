"""Fehlerverteilung ueber die getrackten Cache-Ausgaben (last_real / last_synth_real).

Nur Lesen + Messen: kategorisiert die ocr_hit=false-Zeilen nach Ursache (X/x-Groesse,
fuehrende '='-Fortsetzung, frac-vs-Schraegstrich, fusionierter Exponent) und prueft, ob die
Ursache im Primaer-Metrik-Pfad (same/sympy_equal) ueberhaupt ein Fehler ist oder nur ein
String-Match-Artefakt. Aendert nichts am Produktcode.

Aufruf: venv/bin/python bench/overnight/error_distribution.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from ocr.latex import normalize, parse, same  # noqa: E402

REAL = ROOT / "bench" / "formula_flywheel" / "kalib" / "ketten"
SYNTH = ROOT / "bench" / "synth"


def load_gt(path):
    return {c["id"]: c for c in map(json.loads, open(path))}


def categorize(gt_steps, read, ocr_hit, label):
    """Fuer jede falsch gelesene Zeile: (gt, read, ursache).

    leading_eq       : nur die Fortsetzungs-'-'-Notation weicht ab (GT hat '=', OCR nicht,
                      oder beide haben es und latex2sympy bricht daran) — Inhalt ist gleich.
    leading_eq_plus : fuehrendes '=' UND ein echter Inhaltsunterschied (z. B. fusionierter
                      Exponent '=3^{9}' -> '=39').
    """
    out = []
    for k in range(1, len(gt_steps)):  # Schritt 0 ist die Aufgabe, wird nicht gelesen
        if k - 1 >= len(ocr_hit) or ocr_hit[k - 1]:
            continue
        gt, rd = gt_steps[k], read[k]
        g2 = gt.lstrip().lstrip("=")
        r2 = rd.lstrip().lstrip("=")
        if same(gt, rd):
            cause = "already_equal"  # eigentlich nicht false -> Artefakt der alten Messung
        elif gt.lstrip().startswith("=") or rd.lstrip().startswith("="):
            cause = "leading_eq" if same(g2, r2) else "leading_eq_plus"
        elif normalize(gt).replace("X", "x") == normalize(rd).replace("X", "x"):
            cause = "case_x"
        else:
            cause = "other"
        out.append((gt, rd, cause))
    return out


def main():
    print("=== 1) X vs x: ist das ueberhaupt ein Fehler? ===")
    for a, b in [("3x=15", "3X=15"), ("5x=25", "5X=25"), ("(x-1)(x+7)=0", "(X-1)(X+7)=0")]:
        print(f"  same({a!r}, {b!r}) = {same(a, b)}   (latex2sympy folded X->x)")
    print("  => kein Fehler in der Primaer-Metrik; X-Vorkommen sind bereits treffer.\n")

    print("=== 2) fuehrende '='-Fortsetzung (parse-Faehigkeit) ===")
    for s in [r"=\frac{20}{6}", r"=20/6", r"=3\cdot10+3\cdot7", r"3\cdot10+3\cdot7"]:
        print(f"  parse({s!r}) = {parse(s)!r}")
    print("  => fuehrendes '=' ist fuer latex2sympy unparsebar -> same() kann nicht auf "
          "SymPy-Aequivalenz ausweichen.\n")

    print("=== 3) frac vs Schraegstrich: bereits gleich? ===")
    print(f"  same(\\frac{{20}}{{6}}, 20/6) = {same(r'\frac{20}{6}', r'20/6')}")
    print(f"  same(=\\frac{{20}}{{6}}, =20/6) = {same(r'=\frac{20}{6}', r'=20/6')}   (fuehrendes '=' bricht es)\n")

    # --- kategorisierte Verteilung ueber die Cache-Ausgaben ---
    for name, rows_path, gt_path in [
        ("real", REAL / "last_real.jsonl", REAL / "ketten_gt.jsonl"),
        ("synth", SYNTH / "last_synth_real.jsonl", SYNTH / "ketten_gt.jsonl"),
    ]:
        gt = load_gt(gt_path)
        rows = [json.loads(l) for l in open(rows_path)]
        cats = {}
        for r in rows:
            c = gt[r["id"]]
            for gt_step, rd, cause in categorize(c["steps"], r["read"], r["ocr_hit"], r["label"]):
                cats.setdefault(cause, []).append((r["id"], gt_step, rd))
        n_hit = sum(1 for r in rows for h in r["ocr_hit"] if h)
        n_all = sum(len(r["ocr_hit"]) for r in rows)
        f1_wrong = sum(1 for r in rows if r["pred"] != r["label"])
        print(f"=== {name}: {len(rows)} Ketten, {n_all} gelesene Zeilen, {n_all-n_hit} ocr_hit=false, "
              f"Ketten-F1-Treffer {len(rows)-f1_wrong}/{len(rows)} ===")
        for cause in ("already_equal", "case_x", "leading_eq", "leading_eq_plus", "other"):
            if cause in cats:
                ids = sorted({cid for cid, _, _ in cats[cause]})
                print(f"    {cause:<16} {len(cats[cause]):2d} Zeile(n) in {ids}")
                for cid, g, rd in cats[cause]:
                    print(f"        {cid}: GT={g!r}  read={rd!r}")
        print()


if __name__ == "__main__":
    main()
