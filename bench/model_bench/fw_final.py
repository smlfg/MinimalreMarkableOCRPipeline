"""Endmessung (einmalig) der akzeptierten Flywheel-Konfiguration eines Modells auf allen eingefrorenen Splits. KEIN weiteres Tuning danach.
  python fw_final.py --model uni_qwen3vl_2b   -> fw/<modell>/final_<split>.jsonl (roh) + final_summary.json"""
import argparse, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import fw_step as F, mb_run, mb_score as S
from PIL import Image
ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); a = ap.parse_args()
d = HERE / "fw" / a.model; st = json.loads((d / "state.json").read_text()); c = st["cfg"]
if (d / "final_summary.json").exists(): sys.exit("Endmessung existiert bereits (einmalig)")
cfgm = next(m for m in mb_run.REG if m["key"] == a.model); runner = F.Runner(cfgm, mb_run.fetch(cfgm))
out = {"model": a.model, "cfg": c, "splits": {}}
for sp in S.SPLITS:
    rows = S.prepare.load(sp); gts = {r["id"]: r["gt_latex"] for r in rows}; raws = []
    for r in rows:
        t0 = time.perf_counter()
        try: raw, err = F.post(runner.go(Image.open(mb_run.FW / r["png"]), c), c), None
        except Exception as e: raw, err = "", f"{type(e).__name__}: {e}"
        raws.append({"id": r["id"], "src": r["src"], "raw": raw, "s": time.perf_counter() - t0, "error": err})
    (d / f"final_{sp}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in raws))
    out["splits"][sp] = S.agg(a.model, sp, S.score_rows(raws, gts, sp), {})
(d / "final_summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False)); print("fertig", a.model)
