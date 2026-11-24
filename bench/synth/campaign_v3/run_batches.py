"""Ouroboros v3 — Messung in Batches à 50 (Owner-Anweisung 23.11.), Sprachausgabe je Batch.

Pro Batch:
  1. TexTeller-Cache für die Batch-PNGs füllen (tt_run, .venv_tt)
  2. Messen — Ketten-Batches (L1-L4): chain_bench.run_real in-process (Engines einmal geladen),
     Oracle-Sanity: judge(GT) muss label treffen.
     Formel-Batches (L5/L6): pipeline.recognize je Zeile + Score
     (structure_bench fuer L5, matrix-aware fuer L6 — kein shared Code geaendert).
  3. Sprachausgabe (Thorsten/pycoach-speak, asynchron, Mutex serialisiert)
  4. PROTOKOLL.md + runs/batch_NN.json + RESULTS.tsv

Stellschrauben Messung (plan.json "messung"): glm "an" (volle Pipeline) | "aus" (nur TexTeller aus dem Cache).

Aufruf: .venv_structure/bin/python bench/synth/campaign_v3/run_batches.py [start=1] [ende=21]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import sympy
from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FW = ROOT / "bench" / "formula_flywheel"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(FW))

from chain_bench import judge, run_real, score  # noqa: E402
from ocr.latex import normalize, parse          # noqa: E402
import structure_bench as sb                     # noqa: E402  (Lesen; nicht geaendert)

BATCH = 50


def speak(text):
    if (HERE / "MUTE").exists():      # Owner-Schalter "thorsten stoppen" (23.11. 22:27)
        return
    subprocess.Popen(["/Users/samuelfleig/.local/bin/pycoach-speak"], stdin=subprocess.PIPE,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).communicate(text.encode())


def tt_run(pngs):
    if not pngs:
        return
    rel = [str(p.resolve()) for p in pngs]   # absolut: Kampagnen-PNGs liegen ausserhalb des Flywheel-Ordners
    subprocess.run([str(ROOT / ".venv_tt" / "bin" / "python"), "tt_run.py", "--files", *rel],
                   cwd=FW, check=True, capture_output=True, text=True, timeout=3600)


# ---------------------------------------------------------------- Formel-Scores
def _meq(a, b):
    if hasattr(a, "shape"):
        if not hasattr(b, "shape") or a.shape != b.shape:
            return False
        return all(sympy.simplify(sympy.expand(x - y)) == 0 for x, y in zip(a, b))
    try:
        return sympy.simplify(sympy.expand(a - b)) == 0
    except Exception:
        return False


def score_line(gt, pred):
    """L5: structure_bench. L6 (bmatrix): matrix-aware — lhs/rhs elementweise gegen GT."""
    if "\\begin{bmatrix}" in gt or "\\begin{bmatrix}" in pred:
        g, p = normalize(gt), normalize(pred)
        out = {"exact": g == p, "parse_ok": False, "struct": False,
               "char": Levenshtein.normalized_similarity(g, p)}
        try:
            ge, pe = parse(gt), parse(pred)
        except Exception:
            ge = pe = None
        out["parse_ok"] = pe is not None
        if ge is None or pe is None:
            return out
        if out["exact"]:
            out["struct"] = True
            return out
        try:
            if isinstance(ge, sympy.Equality) and isinstance(pe, sympy.Equality):
                out["struct"] = (_meq(ge.lhs.doit(), pe.lhs.doit())
                                 and _meq(ge.rhs.doit(), pe.rhs.doit()))
        except Exception:
            pass
        return out
    s = sb.score(gt, pred)
    return {"exact": s["exact"], "parse_ok": s["parse_ok"], "struct": s["sympy_equal"],
            "char": s["latex_edit_sim"]}


def protokoll(text):
    with open(HERE / "PROTOKOLL.md", "a", encoding="utf-8") as f:
        f.write(text + "\n")


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    chains = [json.loads(l) for l in open(HERE / "all_gt.jsonl", encoding="utf-8")]
    rows_all = [json.loads(l) for l in open(HERE / "all_rows.jsonl", encoding="utf-8")]
    formulas = [json.loads(l) for l in open(HERE / "formulas.jsonl", encoding="utf-8")]
    glm_mode = plan.get("messung", {}).get("glm", "an")

    sys.path.insert(0, str(FW))
    if glm_mode == "aus":
        import models as M  # EINGEFROREN: nur lesend, TexTeller aus dem Cache
        def recognize(p):
            latex, s = M.tt(str(p))
            return {"latex": latex, "uncertain": False, "cost_s": s}
    else:
        from pipeline import recognize as _r
        def recognize(p):
            return _r(Path(p))

    # Batch-Plan: L1-L4 (700 Ketten) zu je 50, dann L5 (150) und L6 (165 Zeilen) zu je 50
    batches = []
    ci = 0
    for level, n in (("L1", 200), ("L2", 200), ("L3", 150), ("L4", 150)):
        for b in range(0, n, BATCH):
            batches.append({"art": "kette", "level": level, "chains": chains[ci:ci + BATCH]})
            ci += min(BATCH, n - b)
    f5 = [f for f in formulas if f["level"] == "L5"]
    f6 = [f for f in formulas if f["level"] == "L6"]
    for fs, level in ((f5, "L5"), (f6, "L6")):
        for b in range(0, len(fs), BATCH):
            batches.append({"art": "formel", "level": level, "lines": fs[b:b + BATCH]})

    tsv = HERE / "RESULTS.tsv"
    if not tsv.exists():
        tsv.write_text("zeit\tbatch\tstufe\tart\tn\tF1_strict\tstruct\tchar\tcoverage\tprec_certain\tnachfrage\tnotiz\n",
                       encoding="utf-8")

    for i in range(start - 1, len(batches)):
        b = batches[i]
        bno, t0 = i + 1, time.time()
        bd = HERE / f"batch_{bno:02d}"
        bd.mkdir(exist_ok=True)
        if b["art"] == "kette":
            level, cs = b["level"], b["chains"]
            bad = [c["id"] for c in cs if judge(c["steps"])[0] != c["label"]]
            if bad:
                protokoll(f"## Batch {bno} ABGEBROCHEN: Oracle-Fehler bei {bad} — GT ungueltig, nicht messen")
                sys.exit(1)
            rows = [r for r in rows_all if r["chain_id"] in {c["id"] for c in cs}]
            for r in rows:
                r2 = dict(r)
                r2["png"] = "../" + r["png"]
                (bd / "rows.jsonl").open("a", encoding="utf-8").write(json.dumps(r2, ensure_ascii=False) + "\n")
            (bd / "gt.jsonl").write_text(
                "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cs), encoding="utf-8")
            pngs = [HERE / r["png"] for r in rows]
            tt_run(pngs)
            own = {(r["chain_id"], r["step"]): {**r, "png": "../" + r["png"]} for r in rows}
            res = run_real(cs, own, recognize, bd)
            s = score(res)
            (bd / "last.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in res), encoding="utf-8")
            misses = [r for r in res if r["pred"] != r["label"]]
            with open(tsv, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M')}\t{bno}\t{level}\tkette\t{s['n']}\t"
                        f"{s['F1_strict']:.3f}\t\t\t{s['coverage']:.2f}\t\t{s['ask_rate']:.2f}\tglm={glm_mode}\n")
            summary = {"batch": bno, "level": level, "art": "kette", "n": s["n"],
                       "F1_strict": s["F1_strict"], "coverage": s["coverage"],
                       "misses": [{"id": m["id"], "label": m["label"], "pred": m["pred"],
                                   "stage": m.get("stage", ""), "read": m["read"]} for m in misses]}
            text = (f"Batch {bno}. Stufe {level[1]}, {s['n']} Ketten. "
                    f"F eins strikt: {s['F1_strict']:.3f}. {len(misses)} Fehltreffer"
                    + (", alle Stufe drei, also Lesefehler." if misses and
                       all(m.get("stage") == "③ OCR" for m in misses) else ".")
                    + ("" if s["ask_rate"] == 0 else f" Nachfragen: {s['ask_rate']:.0%}."))
        else:
            level, fs = b["level"], b["lines"]
            pngs = [HERE / f["png"] for f in fs]
            tt_run(pngs)
            res = []
            for f in fs:
                t1 = time.time()
                o = recognize(HERE / f["png"])
                sc = score_line(f["gt_latex"], o["latex"])
                res.append({"id": f["id"], "topic": f["topic"], "pred": o["latex"],
                            "unc": o.get("uncertain", False), "dt": time.time() - t1, **sc})
            (bd / "results_formula.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in res), encoding="utf-8")
            n = len(res)
            struct = sum(r["struct"] or False for r in res) / n
            char = sum(r["char"] for r in res) / n
            cert = [r for r in res if not r["unc"]]
            cov = len(cert) / n
            prec = sum(bool(r["struct"]) for r in cert) / max(len(cert), 1)
            with open(tsv, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M')}\t{bno}\t{level}\tformel\t{n}\t\t"
                        f"{struct:.3f}\t{char:.3f}\t{cov:.2f}\t{prec:.3f}\t\tglm={glm_mode}\n")
            summary = {"batch": bno, "level": level, "art": "formel", "n": n,
                       "struct": struct, "char": char, "coverage": cov, "prec_certain": prec,
                       "misses": [{"id": r["id"], "topic": r["topic"], "pred": r["pred"]}
                                  for r in res if not r["struct"]]}
            text = (f"Batch {bno}. Stufe {level[1]}, {n} Zeilen. Strukturgenauigkeit {struct:.0%}, "
                    f"Zeichen {char:.0%}. Sicher gelesen: {cov:.0%}, davon richtig: {prec:.0%}.")
        (HERE / "runs" ).mkdir(exist_ok=True)
        (HERE / "runs" / f"batch_{bno:02d}.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        mins = (time.time() - t0) / 60
        protokoll(f"## Batch {bno} ({time.strftime('%H:%M')}) — {summary['art']} {summary['level']}, "
                  f"{summary['n']} Einheiten, {mins:.1f} min, glm={glm_mode}\n"
                  + json.dumps({k: v for k, v in summary.items() if k not in ("misses",)}, ensure_ascii=False))
        if summary.get("misses"):
            for m in summary["misses"][:8]:
                protokoll(f"  daneben: {m}")
        speak(text)
        print(f"batch {bno} fertig ({mins:.1f} min): {text}", flush=True)

    protokoll("## Kampagne komplett — " + time.strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
