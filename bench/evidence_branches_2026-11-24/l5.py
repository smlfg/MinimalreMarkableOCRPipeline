import sys, json, time, collections
from pathlib import Path
root = Path.cwd(); sys.path.insert(0, str(root)); sys.path.insert(0, str(root/"bench")); sys.path.insert(0, str(root/"bench/formula_flywheel"))
from ocr import formula
import structure_bench as sb
SRC = Path("/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/synth/campaign_v3")
fs = [json.loads(l) for l in open(SRC/"formulas.jsonl") if '"level": "L5"' in l]
tt = formula.TexTeller(); res = []
for f in fs:
    o = formula.recognize(SRC/f["png"], tt=tt)
    s = sb.score(f["gt_latex"], o["latex"])
    res.append({"id": f["id"], "topic": f["topic"], "pred": o["latex"], "unc": o.get("uncertain", False),
                "struct": bool(s["sympy_equal"]), "char": s["latex_edit_sim"]})
n = len(res); cert = [r for r in res if not r["unc"]]
print(json.dumps({"n": n, "struct": sum(r["struct"] for r in res)/n, "char": sum(r["char"] for r in res)/n,
  "coverage": len(cert)/n, "prec_certain": sum(r["struct"] for r in cert)/max(1,len(cert))}))
by = collections.defaultdict(list)
for r in res: by[r["topic"]].append(r["struct"])
print({k: round(sum(v)/len(v),2) for k,v in by.items()})
