import sys, json, collections
sys.path.insert(0, "/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline"); sys.path.insert(0, "/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench"); sys.path.insert(0, "/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/formula_flywheel")
import sympy
from ocr.latex import normalize, parse
def meq(a,b):
    if hasattr(a,"shape"):
        return hasattr(b,"shape") and a.shape==b.shape and all(sympy.simplify(sympy.expand(x-y))==0 for x,y in zip(a,b))
    try: return sympy.simplify(sympy.expand(a-b))==0
    except Exception: return False
def struct(gt, pred):
    g,p=normalize(gt),normalize(pred)
    if g==p: return True
    try: ge,pe=parse(gt),parse(pred)
    except Exception: return False
    if ge is None or pe is None: return False
    try:
        if isinstance(ge,sympy.Equality) and isinstance(pe,sympy.Equality):
            return meq(ge.lhs.doit(),pe.lhs.doit()) and meq(ge.rhs.doit(),pe.rhs.doit())
    except Exception: pass
    return False
for v in ["main","A","B"]:
    rows=[json.loads(l) for l in open("/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/evidence_branches_2026-11-24/pred_L6_%s.jsonl"%v)]
    for r in rows: r["ok"]=struct(r["gt"],r["pred"])
    cert=[r for r in rows if not r["unc"]]
    by=collections.defaultdict(list)
    for r in rows: by[r["topic"]].append(r["ok"])
    print(v, "n",len(rows),"struct %.3f"%(sum(r["ok"] for r in rows)/len(rows)),"coverage %.3f"%(len(cert)/len(rows)),
          "prec_certain %.3f"%(sum(r["ok"] for r in cert)/max(1,len(cert))), {k:round(sum(x)/len(x),2) for k,x in by.items()})
    json.dump(rows, open("/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/evidence_branches_2026-11-24/scored_L6_%s.json"%v,"w"), ensure_ascii=False)
