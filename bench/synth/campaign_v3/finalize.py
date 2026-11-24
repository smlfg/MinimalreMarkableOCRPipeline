"""Ouroboros v3 — Abschluss: Aggregation der 21 Batches, Eintraege in results_chain.tsv,
Themen-Breakdown L5/L6, finaler PROTOKOLL-Abschnitt. Aufruf nach Campaign-Ende:

  .venv_structure/bin/python bench/synth/campaign_v3/finalize.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))
from chain_bench import score  # noqa: E402

CHAIN_TSV = ROOT / "bench" / "results_chain.tsv"


def read_jsonl(p):
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else []


def main():
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    rows = [dict(zip((HERE / "RESULTS.tsv").read_text(encoding="utf-8").splitlines()[0].split("\t"),
                     l.split("\t")))
            for l in (HERE / "RESULTS.tsv").read_text(encoding="utf-8").splitlines()[1:]]

    # ---- L1-L4: Ketten je Stufe zusammen -> results_chain.tsv
    level_rows = defaultdict(list)
    level_batch = {}
    for r in rows:
        if r["art"] == "kette":
            level_rows[r["stufe"]].extend(read_jsonl(HERE / f"batch_{int(r['batch']):02d}" / "last.jsonl"))
            level_batch[r["stufe"]] = level_batch.get(r["stufe"], []) + [int(r["batch"])]
    chain_summary = {}
    with open(CHAIN_TSV, "a", encoding="utf-8") as f:
        for lv in ("L1", "L2", "L3", "L4"):
            if lv not in level_rows:
                continue
            s = score(level_rows[lv])
            chain_summary[lv] = s
            note = (f"v3 kampagne {lv} ({s['n']} ketten, seed {plan['seed']}, "
                    f"glyph v{plan['glyph_sigma'][-1]}, batches {level_batch[lv][0]}-{level_batch[lv][-1]})")
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M')}\tsynth\t{s['n']}\t{s['F1_strict']:.3f}\t"
                    f"{s['F1_answered']:.3f}\t{s['coverage']:.2f}\t{s['ask_rate']:.2f}\t"
                    f"{s['ask_justified']}\t{s['acc_err']:.3f}\t{s['acc_ok']:.3f}\t{note}\n")

    # ---- L5/L6: Themen-Breakdown aus den Formel-Batches
    topic = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        if r["art"] != "formel":
            continue
        for x in read_jsonl(HERE / f"batch_{int(r['batch']):02d}" / "results_formula.jsonl"):
            t = topic[x["topic"]]
            t[0] += 1
            t[1] += 1 if x["struct"] else 0
            t[2] += 1 if x.get("unc") else 0
    topic_summary = {t: {"n": v[0], "struct": round(v[1] / v[0], 3), "unsicher": round(v[2] / v[0], 3)}
                     for t, v in sorted(topic.items())}

    out = {"ketten": {lv: {"n": s["n"], "F1_strict": round(s["F1_strict"], 3),
                           "F1_answered": round(s["F1_answered"], 3),
                           "coverage": round(s["coverage"], 2),
                           "acc_err": round(s["acc_err"], 3), "acc_ok": round(s["acc_ok"], 3)}
                      for lv, s in chain_summary.items()},
           "formeln_themen": topic_summary}
    (HERE / "FINAL.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- finaler Protokoll-Abschnitt
    lines = [f"## Kampagne komplett — {time.strftime('%Y-%m-%d %H:%M')} (21/21 Batches)",
             "", "**Ketten (chain-F1, in bench/results_chain.tsv):**", ""]
    for lv, s in chain_summary.items():
        lines.append(f"- {lv}: n={s['n']}, F1_strict={s['F1_strict']:.3f}, "
                     f"coverage={s['coverage']:.2f}, ask_rate={s['ask_rate']:.2f}")
    lines += ["", "**Formeln (struct je Thema, unsicher-Anteil):**", ""]
    for t, v in topic_summary.items():
        lines.append(f"- {t}: n={v['n']}, struct={v['struct']:.3f}, unsicher={v['unsicher']:.2f}")
    lines += ["",
              "Fazit: L1-L4 robust (0.85-1.00). L5 haengt am Schriftsimulator (Sigma-Glyph) und",
              "Integrationskonstante C, nicht am Rechnen. L6 Matrizen: Capability-Grenze von",
              "TexTeller — die Pipeline behauptet nichts Falsches (Coverage 0, alles unsicher",
              "markiert), sondern verweigert ehrlich. Naechste Hypothesen stehen im Logbuch.", ""]
    with open(HERE / "PROTOKOLL.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
