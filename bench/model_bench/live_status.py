"""Schreibt live/status.json (Rangliste je Split) alle 15 s. Nur lesend auf raw/."""
import json, sys, time
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); import mb_score as S
SPL = S.SPLITS; sizes = {s: len(S.prepare.load(s)) for s in SPL}
GT = {s: {r["id"]: r["gt_latex"] for r in S.prepare.load(s)} for s in SPL}
CACHE = {}
def items(mdl, s):
    f = H / "raw" / mdl / f"{s}.jsonl"
    if not f.exists(): return []
    rows = [json.loads(l) for l in open(f)]; have = CACHE.get((mdl, s), [])
    if len(rows) > len(have): have = have + S.score_rows(rows[len(have):], GT[s], s); CACHE[(mdl, s)] = have
    return have
def metrics(name, it, total):
    a = S.agg(name, "", it, {}) if it else None
    return {"n": len(it), "total": total, **({"struct": a["struct"], "exact": a["exact"], "cer": a["cer"], "halluc": a["halluc"], "p50": a["warm_p50_s"], "sc": a["silent_corr_n"], "scn": a["false_gt_n"]} if a else {})}
BASE = {}
def baseline(s):
    if s not in BASE:
        out = {}
        for name, (rows, _) in S.baselines(s, GT[s], S.prepare.load(s)).items(): out[name] = S.score_rows(rows, GT[s], s)
        BASE[s] = out
    return BASE[s]
LABEL = {"BASELINE_pipeline_tt+glm": "Bisherige Pipeline (TexTeller + GLM)", "BASELINE_texteller": "TexTeller allein"}
while True:
    lf = H / "logs" / "run_all3.out"; cur = None
    for l in (lf.read_text().splitlines() if lf.exists() else []):
        if l.startswith("#####"): cur = l.split()[1]
    views = {"own": ["own_probe", "own_ketten"], **{s: [s] for s in SPL}}
    out = {"t": time.strftime("%H:%M:%S"), "cur": cur, "views": {}, "log": lf.read_text()[-500:] if lf.exists() else ""}
    prog = {}
    for mdl, cfg in S.REG.items():
        done = sum(len(items(mdl, s)) for s in SPL); tot = sum(sizes.values())
        d = H / "hf_cache" / mdl
        got = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e9 if d.exists() else 0
        ready = (d / ".done").exists()
        if cfg["family"] == "custom_blocked": st = "Blockiert: Modellcode fehlt"
        elif mdl == "clzoro_8b": st = "Blockiert: 17,5 GB, Platte zu klein"
        elif done >= tot: st = "Fertig"
        elif done: st = "Rechnet"
        elif mdl == cur and ready: st = "Rechnet"
        elif ready: st = "Geladen, wartet auf Rechenzeit"
        elif d.exists(): st = f"Lädt {got:.1f}/{cfg['weights_gb']:.1f} GB"
        else: st = "Wartet auf Download"
        prog[mdl] = {"done": done, "total": tot, "state": st}
    for v, parts in views.items():
        total = sum(sizes[p] for p in parts); rows = []
        for name, b in sorted(baseline(parts[0]).items()) if len(parts) == 1 else []: rows.append({"name": LABEL[name], "ref": True, **metrics(name, b, total)})
        if len(parts) == 2:
            for name in ("BASELINE_pipeline_tt+glm", "BASELINE_texteller"):
                b = [i for p in parts for i in baseline(p).get(name, [])]
                if len(b) == total: rows.append({"name": LABEL[name], "ref": True, **metrics(name, b, total)})
        tt = {i["id"]: bool(i.get("struct")) for p in parts for i in baseline(p).get("BASELINE_texteller", [])}
        for mdl in S.REG:
            it = [i for p in parts for i in items(mdl, p)]
            rs = S.rescue(it, {k: v for k, v in tt.items() if k in {i["id"] for i in it}}) if it else {}   # nur bereits gerechnete Bilder zählen
            rows.append({**rs, "name": mdl, "ref": False, "repo": S.REG[mdl]["repo"], "weights_gb": S.REG[mdl]["weights_gb"], **prog[mdl], **metrics(mdl, it, total)})
        out["views"][v] = rows
    (H / "live" / "status.json.tmp").write_text(json.dumps(out)); (H / "live" / "status.json.tmp").replace(H / "live" / "status.json")
    time.sleep(15)
