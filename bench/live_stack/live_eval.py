"""Live-Stack-Benchmark (2026-11-23): SchlangebeißtinSchwanz-Lesestapel auf dem Ketten-Blatt.

Klon-Regel: rm_canvas.py / vlm_reader.py / agents.py / math_parser.py /
dynamic_writer.py / font.py sind byte-identisch aus SchlangebeißtinSchwanz @ ed94508
kopiert. Reduziert auf das, was jetzt wichtig ist: KEIN Server, keine Geisterhand,
keine Tablet-Bridge, kein Student-Agent — nur Lesen (qwen2.5vl:7b) + Urteil.

Ablauf pro Kette (28):
  1. Segmentierung GT-unterstützt: Slot-Bänder wie kalib_eval (inkl. Bandöffnung),
     Schritte in Slot-Reihenfolge. Das misst Lese- und Urteilsqualität des Live-Stacks,
     nicht das freie Seiten-Clustering (Doku: BENCHMARK-ketten-2026-11-23.md).
  2. vlm_read_student_strokes -> qwen2.5vl liest die Zeilen (wie im Mensch-Modus).
  3. Inkrementelles Urteil wie im Live-Turn: nach jedem Schritt wird
     _judge_line_sequence über alle bisherigen Zeilen gerufen (neueste Zeile zählt).

Bewertung:
  label -1 (korrekte Kette): bestanden, wenn kein Schritt rot urteilt.
  label k  (Fehler in Schritt k): getroffen, wenn Schritt k rot ist;
           rotes Urteil vorher = falsche Anschuldigung; kein Rot = Fehler verpasst.

Aufruf: python3 live_eval.py   (aus bench/live_stack; System-python3 mit rmscene+PIL)
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parent / "formula_flywheel"
OWN = FW / "own" / "ketten"
sys.path.insert(0, str(HERE))

import rm_canvas                      # noqa: E402
import vlm_reader                     # noqa: E402
from agents import classify_line, _judge_line_sequence  # noqa: E402

DOC = "8a5fc918-e5db-43e1-973f-4235c3ef3008"


def main():
    content = json.load(open(OWN / f"{DOC}.content"))
    pages = content["cPages"]["pages"] if "cPages" in content else content["pages"]
    pages = [p["id"] if isinstance(p, dict) else p for p in pages]
    chains = [json.loads(l) for l in open(FW / "kalib" / "ketten" / "ketten_gt.jsonl")]

    # Slot-Bänder mit Bandöffnung (identisch zur kalib_eval-Regel von heute Nacht)
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

    png_dir = HERE / "pngs"
    png_dir.mkdir(exist_ok=True)
    t0 = time.time()
    results = []
    for c in chains:
        mine = sorted([b for b in bands if b[0] == c["id"]], key=lambda b: b[3])
        per_slot, chain_strokes = [], []
        for cid, step, p, ya, yb in mine:
            sel = [s for s in page_strokes[p] if ya <= cent(s)[1] <= yb and cent(s)[0] > 660]
            per_slot.append((step, sel))
            chain_strokes += sel
        row = {"id": c["id"], "label": c["label"], "n_slots": len(mine), "gt_steps": c["steps"]}
        if not chain_strokes:
            row["error"] = "keine Striche"
            results.append(row)
            print(f"{c['id']}: keine Striche")
            continue
        vlm = vlm_reader.vlm_read_student_strokes(chain_strokes, png_dir / f"{c['id']}.png")
        lines = vlm["lines"]
        row["read"] = lines
        verdicts = []
        for i in range(len(lines)):
            classified = [classify_line(ln) for ln in lines[: i + 1]]
            verdict, note, color = _judge_line_sequence(classified)
            verdicts.append({"line": i + 1, "verdict": verdict, "color": color, "note": note})
        row["verdicts"] = verdicts
        results.append(row)
        print(f"{c['id']}: {len(lines)}/  Slots {len(mine)} · "
              + " | ".join(f"z{v['line']}={v['verdict']}({v['color']})" for v in verdicts), flush=True)

    # Score
    ok = err = caught = false_acc = missed = 0
    for r in results:
        if "verdicts" not in r:
            continue
        reds = [v["line"] for v in r["verdicts"] if v["color"] == "red"]
        if r["label"] == -1:
            ok += 1
            if reds:
                false_acc += 1
                r["live_result"] = f"falsche Anschuldigung in Schritt {reds[0]}"
            else:
                r["live_result"] = "bestanden"
        else:
            err += 1
            if r["label"] in reds:
                if any(x < r["label"] for x in reds):
                    false_acc += 1
                    r["live_result"] = f"getroffen, aber frueher rot in {min(reds)}"
                else:
                    caught += 1
                    r["live_result"] = "getroffen"
            elif reds:
                false_acc += 1
                r["live_result"] = f"rot, aber am falschen Schritt {reds}"
            else:
                missed += 1
                r["live_result"] = "Fehler verpasst"

    n_false_ok = sum(1 for r in results if r["label"] == -1 and "falsche" in r.get("live_result", ""))
    summary = {
        "n": len(results), "korrekte_ketten": ok, "fehler_ketten": err,
        "getroffen": caught, "verpasst": missed, "falsche_anschuldigung": false_acc,
        "acc_err": round(caught / max(1, err), 3),
        "acc_ok": round((ok - n_false_ok) / max(1, ok), 3),
        "dauer_s": round(time.time() - t0, 1),
    }
    (HERE / "live_results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results))
    (HERE / "live_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print("\n== Zusammenfassung ==")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
