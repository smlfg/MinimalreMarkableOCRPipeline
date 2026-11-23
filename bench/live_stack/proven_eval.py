"""Proven-Stack live: die 28/28-Lesestufe (TexTeller + GLM + Kohaerenz) LIVE ohne Bench-Cache
plus chain_bench-Urteil, auf demselben Ketten-Protokoll wie live_eval.py (qwen-Stack).

Integrationstest: Kann die bewiesene Pipeline als LIVE-Leser arbeiten —
freies Zeilen-Clustering (rm_canvas.cluster_student_lines), echte Engine-Aufrufe —
und dasselbe Blatt ebenfalls 28/28 beurteilen?

Bewertung: finale chain_bench.judge-Sequenz pro Kette (Predikt == Label),
Uneinigkeit/ask wird berichtet. GT-unterstuetzte Ketten-Gruppierung wie im
qwen-Lauf (Segmentierungs-Assist, dokumentiert in BENCHMARK-ketten-2026-11-23.md).

Aufruf: .venv_structure/bin/python proven_eval.py   (rmscene + LaTeX-Stack + PIL)
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parent / "formula_flywheel"
OWN = FW / "own" / "ketten"
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import rm_canvas                                       # noqa: E402
from ocr.formula import recognize, TexTeller, glm_live  # noqa: E402
from bench.chain_bench import judge                     # noqa: E402

DOC = "8a5fc918-e5db-43e1-973f-4235c3ef3008"
_TT = None


def get_tt():
    global _TT
    if _TT is None:
        _TT = TexTeller()          # Live-Worker in .venv_tt, ein Prozess fuer alle Zeilen
    return _TT


def read_chain(strokes, png_dir, tag) -> dict:
    """Freies Zeilen-Clustering + live recognize() je Zeile -> lines, uncertain, alts."""
    clusters = rm_canvas.cluster_student_lines(strokes, pad=22.0)
    student = [s for s in strokes if s.get("author") == "student" and s.get("points")]

    def sbox(s):
        xs = [p[0] for p in s["points"]]
        ys = [p[1] for p in s["points"]]
        return min(xs), min(ys), max(xs), max(ys)

    lines, unsure, alts = [], [], {}
    for c in clusters:
        b = c["bbox"]
        row = [s for s in student
               if not (sbox(s)[2] < b[0] or sbox(s)[0] > b[2] or sbox(s)[3] < b[1] or sbox(s)[1] > b[3])]
        if not row:
            continue
        png = png_dir / f"{tag}_z{c['index']}.png"
        rm_canvas.render_strokes_png(row, png, authors=("student",))
        o = recognize(str(png), tt=get_tt(), glm=glm_live)
        lines.append(o["latex"])
        if o["uncertain"]:
            unsure.append(len(lines))
            if o.get("alt") is not None:
                alts[len(lines)] = o["alt"]
    return {"lines": lines, "uncertain": unsure, "alts": alts}


def main():
    content = json.load(open(OWN / f"{DOC}.content"))
    pages = content["cPages"]["pages"] if "cPages" in content else content["pages"]
    pages = [p["id"] if isinstance(p, dict) else p for p in pages]
    chains = [json.loads(l) for l in open(FW / "kalib" / "ketten" / "ketten_gt.jsonl")]

    raw = []
    for c in chains:
        for sl in c["slots"]:
            raw.append((c["id"], sl["step"], sl["page"], sl["slot_y"][0], sl["slot_y"][1]))
    raw.sort(key=lambda r: (r[2], r[3]))
    bands, prev = [], {}
    for cid, step, p, ya, yb in raw:
        ya2 = max((prev[p][1] + 4) if p in prev else 120, ya - 90)
        bands.append((cid, step, p, ya2, yb))
        prev[p] = (ya2, yb)

    page_strokes = {i: rm_canvas.read_strokes(OWN / f"{pid}.rm") for i, pid in enumerate(pages)}

    def cent(s):
        pts = s["points"]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    png_dir = HERE / "pngs_proven"
    png_dir.mkdir(exist_ok=True)
    t0 = time.time()
    results = []
    for c in chains:
        mine = sorted([b for b in bands if b[0] == c["id"]], key=lambda b: b[3])
        chain_strokes = []
        for cid, step, p, ya, yb in mine:
            chain_strokes += [s for s in page_strokes[p] if ya <= cent(s)[1] <= yb and cent(s)[0] > 660]
        row = {"id": c["id"], "label": c["label"], "gt_steps": c["steps"], "n_slots": len(mine)}
        if not chain_strokes:
            row["error"] = "keine Striche"
            results.append(row)
            print(f"{c['id']}: keine Striche", flush=True)
            continue
        rd = read_chain(chain_strokes, png_dir, c["id"])
        read = [c["steps"][0]] + rd["lines"]
        pred, st, speak = judge(read, rd["uncertain"], rd["alts"])
        row.update(read=rd["lines"], uncertain=rd["uncertain"], pred=pred, status=st, speak=speak)
        row["richtig"] = pred == c["label"]
        results.append(row)
        print(f"{c['id']}: {len(rd['lines'])} Zeilen · pred {pred} (label {c['label']}) "
              f"· {'OK' if row['richtig'] else 'FEHL'} · gelesen {rd['lines']}", flush=True)

    n_ok = sum(1 for r in results if r.get("richtig"))
    n_ask = sum(1 for r in results if r.get("pred") == "ask")
    summary = {
        "n": len(results), "richtig": n_ok, "falsch": len(results) - n_ok,
        "davon_asks": n_ask,
        "dauer_s": round(time.time() - t0, 1),
    }
    (HERE / "proven_results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results))
    (HERE / "proven_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print("\n== Zusammenfassung ==")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
