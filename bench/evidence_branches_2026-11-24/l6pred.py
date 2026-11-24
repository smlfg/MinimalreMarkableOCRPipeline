import sys, json
from pathlib import Path
root = Path.cwd(); sys.path.insert(0, str(root))
from ocr import formula
SRC = Path("/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/synth/campaign_v3"); variant = sys.argv[1]; level = sys.argv[2]
fs = [json.loads(l) for l in open(SRC/"formulas.jsonl") if json.loads(l)["level"] == level]
tt = formula.TexTeller(); out = open("/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/evidence_branches_2026-11-24/pred_%s_%s.jsonl" % (level, variant), "w")
for f in fs:
    o = formula.recognize(SRC/f["png"], tt=tt)
    out.write(json.dumps({"id": f["id"], "topic": f["topic"], "gt": f["gt_latex"], "pred": o["latex"], "unc": o.get("uncertain", False)}, ensure_ascii=False) + "\n"); out.flush()
