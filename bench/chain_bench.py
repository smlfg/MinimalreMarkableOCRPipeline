"""End-to-End-Messung der Kette (ADR-009): Handschrift -> OCR -> Validator -> Tutor-Urteil.

Zielmetrik ProcessBench-F1 (QwenLM/ProcessBench, code/run_eval.py, Apache-2.0):
  acc_err = Anteil fehlerhafter Ketten, deren frühester Fehlerschritt exakt getroffen wird
  acc_ok  = Anteil korrekter Ketten, die als korrekt (-1) erkannt werden
  F1      = 2 * acc_err * acc_ok / (acc_err + acc_ok)
Eigene Zählregel für Nachfragen ("ask", in ProcessBench nicht vorgesehen), vor der Messung fixiert:
  F1_strict   ask zählt als falsch
  F1_answered Ketten mit ask fallen heraus; Abdeckung wird mit berichtet

Pfade:
  --oracle  GT-LaTeX statt OCR -> Obergrenze von Validator + Tutor (kein Tablet nötig)
  (ohne)    Slot-PNGs aus bench/formula_flywheel/data/own_ketten.jsonl (kalib_eval.py ketten) durch die OCR
  --synth   wie (ohne)/--oracle, aber gegen bench/synth/ (gen_ketten.py: AI-Student + Schriftsimulation)

Bausteine (wiederverwendet, kein eigener Prüfer): ocr/latex.parse, ocr/coherence.decimal_comma,
AlgebraAgentChecker + SimpleTutor aus urgent-Math-help.
Aufruf: .venv_structure/bin/python bench/chain_bench.py [--oracle] ["notiz"]
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "urgent-Math-help" / "src"))
from ocr.coherence import decimal_comma  # noqa: E402
from ocr.latex import parse, same  # noqa: E402
from math_help.adapters.algebra_agent_checker import AlgebraAgentChecker  # noqa: E402
from math_help.models import Problem, Verdict  # noqa: E402
from math_help.tutor import SimpleTutor  # noqa: E402

KETTEN = ROOT / "bench" / "formula_flywheel" / "kalib" / "ketten"
OWN = ROOT / "bench" / "formula_flywheel" / "data" / "own_ketten.jsonl"
SYNTH = ROOT / "bench" / "synth"                 # Ouroboros: gen_ketten.py (ADR-009)
SYNTH_GT = SYNTH / "ketten_gt.jsonl"
SYNTH_ROWS = SYNTH / "synth_ketten.jsonl"
TSV = ROOT / "bench" / "results_chain.tsv"
EQ = r"(?<![<>!\\])="


def validator_lines(steps):
    """LaTeX-Schritte -> Zeilen für den Validator. Jede Seite einzeln parsen, sonst wertet SymPy
    Zahlengleichungen sofort zu True aus. '=...' setzt den vorigen Ausdruck fort. Nackte Terme
    ab Zeile 2 gelten nach Schul-Konvention als Ist-gleich-Fortsetzung (K25); nur der
    Aufgaben-Term in Zeile 1 bleibt reiner Term."""
    out, prev = [], None
    for pos, s in enumerate(steps):
        s = decimal_comma(s or "")
        parts = [p for p in re.split(EQ, s)]
        if s.strip().startswith("=") and prev is not None:
            parts = [prev] + parts[1:]
        elif s.strip() and "=" not in s and pos > 0 and prev is not None:
            parts = [prev] + parts                    # nackter Term: implizite Gleichheit
        es = [parse(p) for p in parts if p.strip()]
        if len(es) == 1 and not s.strip().startswith("="):       # reiner Term (Aufgabe "17·3")
            prev = parts[0]; out.append(None); continue
        if len(es) != 2 or any(e is None for e in es):
            out.append(""); prev = parts[-1] if parts else prev; continue
        out.append("=".join(str(e) for e in es)); prev = parts[-1]
    return out


def judge(steps, ocr_uncertain=None, alts=None):
    """-> (prediction, statuses, speak). prediction: Index des frühesten Fehlers, -1 oder 'ask'.

    Arbitrierung (ADR-007 Erweiterung): Bei OCR-Unsicherheit mit abweichender Zweitmeinung
    (alt) wird geprüft, ob das valdierte Präfix die Primärlesart bestätigt und die
    Zweitmeinung widerlegt. Nur Bestätigen, nie Überschreiben: passt stattdessen die
    Zweitmeinung zur Kette, bleibt unsicher und wird nachgefragt (verschleiert keine Fehler)."""
    alts = alts or {}
    lines = validator_lines(steps)
    idx = [i for i, l in enumerate(lines) if l is not None]
    verdicts = AlgebraAgentChecker().check(Problem(source=None, lines=tuple(lines[i] for i in idx)))
    status = {i: "correct" for i, l in enumerate(lines) if l is None}
    for i, v in zip(idx, verdicts):
        status[i] = v.status
    for i in (ocr_uncertain or []):              # ADR-007: unsicher gelesene Zeile wird nie still geprüft
        if status.get(i) == "correct":
            alt = alts.get(i)
            if alt is not None and all(status.get(j) == "correct" for j in range(i)):
                steps_alt = list(steps); steps_alt[i] = alt
                lines_alt = validator_lines(steps_alt)
                alt_lines = tuple(lines_alt[j] for j in idx if j <= i)
                v_alt = (AlgebraAgentChecker().check(Problem(source=None, lines=alt_lines))[-1].status
                         if len(alt_lines) >= 2 else None)   # 1-zeiliges Praefix ist nicht widerlegbar
                if v_alt is not None and v_alt != "correct":   # Primaerlesart kettentauglich, Zweitmeinung widerlegt
                    continue
            status[i] = "uncertain"
    statuses = [status[i] for i in range(len(steps))]
    # Tutor bekommt die Urteile inkl. OCR-Unsicherheit, mit Zeilennummern der ganzen Kette
    speak = SimpleTutor().advise(Problem(source=None, lines=tuple(steps)),
                                 [Verdict(line=i, status=st, reason="") for i, st in enumerate(statuses)]).speak
    for i, st in enumerate(statuses):
        if st == "incorrect":
            return i, statuses, speak
        if st in ("uncertain", "empty"):
            return "ask", statuses, speak
    return -1, statuses, speak


def f1(acc_err, acc_ok):
    return 0.0 if acc_err + acc_ok == 0 else 2 * acc_err * acc_ok / (acc_err + acc_ok)


def score(rows):
    err = [r for r in rows if r["label"] != -1]; ok = [r for r in rows if r["label"] == -1]
    hit = lambda r: r["pred"] == r["label"]
    a_err = sum(map(hit, err)) / max(1, len(err)); a_ok = sum(map(hit, ok)) / max(1, len(ok))
    ans = [r for r in rows if r["pred"] != "ask"]
    ae = [r for r in ans if r["label"] != -1]; ao = [r for r in ans if r["label"] == -1]
    asks = [r for r in rows if r["pred"] == "ask"]
    return {"n": len(rows), "acc_err": a_err, "acc_ok": a_ok, "F1_strict": f1(a_err, a_ok),
            "F1_answered": f1(sum(map(hit, ae)) / max(1, len(ae)), sum(map(hit, ao)) / max(1, len(ao))),
            "coverage": len(ans) / max(1, len(rows)), "ask_rate": len(asks) / max(1, len(rows)),
            "ask_justified": sum(r.get("ask_justified", False) for r in asks)}


def main():
    oracle = "--oracle" in sys.argv
    synth = "--synth" in sys.argv
    note = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
    src_dir = SYNTH if synth else KETTEN
    path = ("synth_" if synth else "") + ("oracle" if oracle else "real")
    chains = [json.loads(l) for l in open(SYNTH_GT if synth else KETTEN / "ketten_gt.jsonl")]
    rows = []
    if oracle:
        for c in chains:
            pred, st, speak = judge(c["steps"])
            rows.append({"id": c["id"], "label": c["label"], "pred": pred, "status": st, "speak": speak})
    else:
        rows_src = SYNTH_ROWS if synth else OWN
        if not rows_src.exists():
            sys.exit(f"{rows_src} fehlt" +
                     ("" if synth else ": erst Blatt abschreiben und 'kalib_eval.py ketten' laufen lassen"))
        sys.path.insert(0, str(ROOT / "bench" / "formula_flywheel"))
        from pipeline import recognize
        png_base = SYNTH if synth else OWN.parent.parent
        own = {(r["chain_id"], r["step"]): r for r in map(json.loads, open(rows_src))}
        oracle_pred = {c["id"]: judge(c["steps"])[0] for c in chains}
        for c in chains:
            read, unsure, hits, alt_reads = [c["steps"][0]], [], [], {}
            for k in range(1, len(c["steps"])):
                r = own.get((c["id"], k))
                if r is None:
                    read.append(""); unsure.append(k); hits.append(False); continue
                o = recognize(png_base / r["png"])
                read.append(o["latex"]); hits.append(same(o["latex"], c["steps"][k]))
                if o["uncertain"]:
                    unsure.append(k)
                    if o.get("alt") is not None:
                        alt_reads[k] = o["alt"]
            pred, st, speak = judge(read, unsure, alt_reads)
            relevant = c["label"] if c["label"] != -1 else len(c["steps"]) - 1
            row = {"id": c["id"], "label": c["label"], "pred": pred, "status": st, "speak": speak,
                   "read": read, "ocr_hit": hits, "oracle_pred": oracle_pred[c["id"]],
                   "miss_relevant": any(not h for h in hits[:relevant])}
            if pred == "ask":
                first = next(i for i, s in enumerate(st) if s in ("uncertain", "empty"))
                row["ask_justified"] = first >= 1 and not hits[first - 1]
            if pred != c["label"]:
                row["stage"] = "③ OCR" if oracle_pred[c["id"]] == c["label"] else "④/⑤ Validator/Tutor"
            rows.append(row)
    s = score(rows)
    (src_dir / f"last_{path}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    new = not TSV.exists()
    with open(TSV, "a") as f:
        if new:
            f.write("zeit\tpfad\tn\tF1_strict\tF1_answered\tabdeckung\tnachfrage\tnachfrage_berechtigt\tacc_err\tacc_ok\tnotiz\n")
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M')}\t{path}\t{s['n']}\t{s['F1_strict']:.3f}\t{s['F1_answered']:.3f}\t"
                f"{s['coverage']:.2f}\t{s['ask_rate']:.2f}\t{s['ask_justified']}\t{s['acc_err']:.3f}\t{s['acc_ok']:.3f}\t{note}\n")
    print(json.dumps(s, indent=1))
    for r in rows:
        if r["pred"] != r["label"]:
            print(f"  {r['id']}: label {r['label']} pred {r['pred']} {r['status']} {r.get('stage', '')}")


if __name__ == "__main__":
    main()
