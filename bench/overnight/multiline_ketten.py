"""Strukturelle Ketten-Gruppierung auf echten kalib/ketten-Mustern (kein Modell, keine PNGs).

Quelle: `kalib/ketten/last_real.jsonl` (die tatsaechlich gelesenen Zeilen `read`) und
`kalib/ketten/ketten_gt.jsonl` (GT-Ketten). Die echte Kalibrier-Seite hat ein Zwei-Spalten-
Layout (Aufgabe gedruckt links, Schueler schreibt rechts je Zeile); fuer die *Ableitungs*-
Gruppierung ist das irrelevant, deshalb rekonstruieren wir eine **einspaltige** Anordnung wie
auf echtem Schuelerpapier (Zeilen untereinander, H=50, Gap=20). Das ist eine Muster-Messung,
keine Live-OCR-Messung.

Zielmetrik: Anteil der GT-Ketten mit >=2 Zeilen, deren Zeilen `group_lines` zu **genau einer**
Kette zusammenfasst (within-chain recall), plus Packed-Layout (reale ROW-Dichte) fuer
Cross-Chain-Fehlverschmelzungen.

Aufruf: venv/bin/python bench/overnight/multiline_ketten.py [--tag notiz]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from ocr.multiline import _vars, group_lines  # noqa: E402

KETTEN = ROOT / "bench" / "formula_flywheel" / "kalib" / "ketten"
H, GAP = 50, 20


def _stack(texts, y0=0, gap=GAP, x0=40, w=360, h=H):
    return [{"latex": t, "bbox": (x0, y0 + i * (h + gap), x0 + w, y0 + i * (h + gap) + h)}
            for i, t in enumerate(texts)]


def load():
    gt = {r["id"]: r for r in map(json.loads, open(KETTEN / "ketten_gt.jsonl"))}
    real = {r["id"]: r for r in map(json.loads, open(KETTEN / "last_real.jsonl"))}
    out = []
    for cid, c in gt.items():
        read = real.get(cid, {}).get("read") or c["steps"]
        out.append({"id": cid, "topic": c.get("topic"), "steps": c["steps"], "read": read})
    return out


def within_chain(chains):
    rows, ok = [], 0
    for c in chains:
        lines = _stack(c["read"])
        groups = group_lines(lines)
        good = len(groups) == 1
        ok += good
        if not good:
            varsets = [_vars(t) for t in c["read"]]
            rows.append({"id": c["id"], "read": c["read"], "n_groups": len(groups),
                         "varsets": [sorted(v) for v in varsets],
                         "group_sizes": [len(g["line_indices"]) for g in groups]})
    return ok, rows


def packed(chains, chain_gap=0):
    """Alle Ketten untereinander. `chain_gap` = zusaetzlicher Leerraum zwischen Aufgaben (wie
    ein leerer Zeilenabstand auf echtem Papier). Zaehlt GT-Ketten, die exakt als eine Gruppe
    wieder auftauchen, und Gruppen mit Zeilen aus >1 GT-Kette (Fehlverschmelzung)."""
    lines, owner = [], []
    for ci, c in enumerate(chains):
        for t in c["read"]:
            y = len(lines) * (H + GAP) + ci * chain_gap
            lines.append({"latex": t, "bbox": (40, y, 400, y + H)})
            owner.append(ci)
    groups = group_lines(lines)
    exact = merged = 0
    for g in groups:
        owners = {owner[i] for i in g["line_indices"]}
        if len(owners) > 1:
            merged += 1
        else:
            ci = next(iter(owners))
            if len(g["line_indices"]) == len(chains[ci]["read"]):
                exact += 1
    return {"n_chains": len(chains), "n_groups": len(groups), "exact": exact,
            "merged_groups": merged}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="baseline")
    a = ap.parse_args()
    chains = load()
    multi = [c for c in chains if len(c["read"]) >= 2]
    ok, fails = within_chain(multi)
    rec = ok / max(1, len(multi))
    pk_gap = packed(chains, chain_gap=2 * H)
    pk_adj = packed(chains, chain_gap=0)
    print(f"ketten within-chain: {ok}/{len(multi)} = {rec:.3f}  "
          f"(Ketten >=2 Zeilen, genau 1 Gruppe)")
    for r in fails:
        print(f"  {r['id']} groups={r['group_sizes']} varsets={r['varsets']} read={r['read']}")
    print(f"ketten packed+Leerzeile: chains={pk_gap['n_chains']} groups={pk_gap['n_groups']} "
          f"exact={pk_gap['exact']} merged_groups={pk_gap['merged_groups']}")
    print(f"ketten packed ohne Trenner: groups={pk_adj['n_groups']} exact={pk_adj['exact']} "
          f"merged_groups={pk_adj['merged_groups']}  (Grenze: ohne Luecke/Label verschmelzen)")
    tsv = HERE / "results_multiline_ketten.tsv"
    if not tsv.exists():
        tsv.write_text("commit\tn\twithin_recall\tpacked_exact\tpacked_merged\ttag\n")
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True, cwd=str(ROOT)).stdout.strip() or "-"
    with open(tsv, "a") as f:
        f.write(f"{commit}\t{len(multi)}\t{rec:.4f}\t{pk_gap['exact']}\t{pk_gap['merged_groups']}"
                f"\t{a.tag}\n")


if __name__ == "__main__":
    main()
