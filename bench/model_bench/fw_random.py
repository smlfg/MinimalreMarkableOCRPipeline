"""Zufallssuche als KONTROLLE zum Haiku-Flywheel. Gleiche Stellschrauben (fw_step.SPACE), gleiche Batches (Seed 1000+iter, 10/20 abwechselnd), gleiche feste dev-Kontrolle,
gleiche Annahmeregel, gleiches Budget (12 Iterationen) und gleicher Start (Standardkonfiguration). Einziger Unterschied: die Änderung wird zufällig statt vom Sprachmodell gewählt.
  python fw_random.py --model uni_qwen3vl_2b --iters 12 --seed 7      -> fw_random/<modell>/{log.jsonl,state.json}"""
import argparse, json, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import fw_step as F, mb_run, mb_score as S

ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--iters", type=int, default=12); ap.add_argument("--seed", type=int, default=7); a = ap.parse_args()
cfgm = next(m for m in mb_run.REG if m["key"] == a.model)
d = HERE / "fw_random" / a.model; d.mkdir(parents=True, exist_ok=True)
train, dev = S.prepare.load("train"), S.prepare.load("dev")
gts = {r["id"]: r["gt_latex"] for r in train + dev}
control = random.Random(0).sample(dev, F.CONTROL_N)
runner = F.Runner(cfgm, mb_run.fetch(cfgm))
cfg = dict(F.DEFAULT); ce = F.evaluate(runner, control, cfg, gts); ctl = ce["struct"]
rng = random.Random(a.seed); tried = set(); accepted = []
cands = [(k, (i if k == "prompt" else v)) for k, vs in F.SPACE.items() for i, v in enumerate(vs)]
with open(d / "log.jsonl", "w") as lf:
    for it in range(1, a.iters + 1):
        opts = [(k, v) for k, v in cands if cfg[k] != v and (k, v, json.dumps(cfg, sort_keys=True)) not in tried]
        k, v = rng.choice(opts); tried.add((k, v, json.dumps(cfg, sort_keys=True)))
        cand = dict(cfg); cand[k] = v
        N = 10 if it % 2 == 1 else 20
        pool = random.Random(1000 + it).sample(train, 4 * N)
        pe = F.evaluate(runner, pool, cfg, gts)
        worst = sorted(pe["items"], key=lambda i: -i.get("cer", 1))[:N]; ids = {i["id"] for i in worst}
        batch = [r for r in pool if r["id"] in ids]
        bb = {"struct": sum(i["struct"] for i in worst if "error" not in i) / N, "cer": sum(i.get("cer", 1) for i in worst) / N}
        bc = F.evaluate(runner, batch, cand, gts)
        gain = bc["struct"] > bb["struct"] or (bc["struct"] == bb["struct"] and bb["cer"] - bc["cer"] >= 0.01)
        cc = F.evaluate(runner, control, cand, gts) if gain else None
        acc = bool(gain and cc["struct"] >= ctl)
        rec = {"iter": it, "batch_n": N, "change": {"key": k, "value": v}, "batch_base": {x: round(bb[x], 4) for x in bb}, "batch_cand": {x: round(bc[x], 4) for x in ("struct", "cer")},
               "control_base_struct": round(ctl, 4), "control_cand_struct": None if cc is None else round(cc["struct"], 4), "accepted": acc, "cfg_after": cand if acc else cfg}
        lf.write(json.dumps(rec, ensure_ascii=False) + "\n"); lf.flush()
        if acc: cfg, ctl = cand, cc["struct"]; accepted.append(rec["change"])
        (d / "state.json").write_text(json.dumps({"cfg": cfg, "control_struct": ctl, "iters_done": it, "accepted": accepted, "seed": a.seed}))
print("fertig", a.model, cfg, round(ctl, 4))
