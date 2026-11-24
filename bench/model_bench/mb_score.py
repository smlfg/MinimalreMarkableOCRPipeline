"""Bewertet raw/<model>/<split>.jsonl -> BENCHMARK_RESULTS.csv (+ per_item.jsonl). Rein lesend auf Rohdaten.
  ../../.venv_mb/bin/python -I mb_score.py
Metriken je (Modell, Split):
  cer            = 1 - Zeichengenauigkeit auf normalisiertem LaTeX (prepare.char_acc)      [Zeichen/Transkription]
  exact          = normalisiertes LaTeX identisch zur GT                                    [Formel/Transkription]
  parse_ok       = SymPy (latex2sympy2_extended) kann die Vorhersage parsen
  struct         = SymPy-Äquivalenz GT vs. Vorhersage (structure_bench.score)               [mathematische Struktur/Semantik]
  tree_sim       = APTED-Baumähnlichkeit (nur wo beide parsen)
  halluc         = Entartung: Wiederholungsschleife (>=6x gleiches Token hintereinander), Länge > 2*GT+30, Chat-Reste ('assistant','<think>')
  silent_corr    = GT ist eine numerisch FALSCHE Gleichung, Vorhersage ist (anders geschrieben und) numerisch WAHR -> Modell hat still 'repariert'
  Baselines: TexTeller allein (aus cache.sqlite, read-only) und Pipeline TexTeller+GLM (aus last_<split>.jsonl der Hauptkopie, nicht neu berechnet)."""
import csv, hashlib, json, re, sqlite3, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parent / "formula_flywheel"
MAIN = Path("/Users/samuelfleig/Projects/01_WORK/Remarkable/MinimalreMarkableOCRPipeline/bench/formula_flywheel")
sys.path.insert(0, str(FW)); sys.path.insert(0, str(HERE.parent))
import sympy, prepare, structure_bench as sb
from ocr.latex import parse

SPLITS = ["own_probe", "own_ketten", "dev", "synth", "synth_hard"]
REG = {m["key"]: m for m in json.load(open(HERE / "MODEL_REGISTRY.json"))["models"]}


def clean(raw):
    s = re.split(r"\nassistant\b|<think>|<\|im_end\|>", raw)[0]            # Stop-Reste (Stop-Token fehlt bei manchen Finetunes)
    s = re.sub(r"```(latex)?", "", s).strip()
    s = re.sub(r"^\\\[|\\\]$|^\\begin\{align\*\}|\\end\{align\*\}$", "", s.strip()).strip()
    return re.sub(r"^\s*\${1,2}|\${1,2}\s*$", "", s).strip()


def truth(latex):
    """True/False wenn rein numerische Gleichung entscheidbar, sonst None."""
    e = parse(latex)
    try:
        if isinstance(e, sympy.Equality) and not (e.lhs.free_symbols | e.rhs.free_symbols):
            return bool(sympy.simplify(e.lhs - e.rhs) == 0)
    except Exception:
        pass
    return None


def consistent(prev, step):
    """Folgt 'step' aus 'prev' (gleiche Lösungsmenge bzw. gleicher Wert)? True/False, None wenn nicht entscheidbar."""
    a, b = parse(prev), parse(step)
    if a is None or b is None: return None
    try:
        if isinstance(a, sympy.Equality) and isinstance(b, sympy.Equality):
            syms = sorted((a.free_symbols | b.free_symbols), key=str)
            if len(syms) == 1: return bool(sympy.solveset(a, syms[0]) == sympy.solveset(b, syms[0]))
            return bool(sympy.simplify((a.lhs - a.rhs) - (b.lhs - b.rhs)) == 0)
    except Exception:
        return None
    return None


def chain_prev():
    """own_ketten: Vorgänger-GT je Bild (Aufgabenzeile = steps[0]); label==1 = Kette mit Fehler."""
    gt = {}
    for l in open(FW / "kalib" / "ketten" / "ketten_gt.jsonl"):
        c = json.loads(l); gt[c["id"]] = c
    return gt


def halluc(gt, raw, pred):
    if re.search(r"(\S+?)(\s*\1){5,}", pred.replace("\\ ", " ")) and len(pred) > 40: return True
    if len(pred) > 2 * len(gt) + 30: return True
    return bool(re.search(r"assistant|<think>", raw)) and False  # Chat-Reste zählen als Stop-Fehler, nicht als Halluzination (separat gemeldet)


import signal
class _TO(Exception): pass
def _alarm(*_): raise _TO()
signal.signal(signal.SIGALRM, _alarm)
TIMEOUT_S = 10   # SymPy kann an entarteten Ausgaben ewig rechnen: >10 s je Zeile zählt als 'nicht äquivalent' (im Report vermerkt)


def score_rows(rows, gts, split=None):
    return [_score_one(r, gts, split) for r in rows]


def _score_one(r, gts, split):
    signal.alarm(TIMEOUT_S)
    try: return _score_row(r, gts, split)
    except _TO: return {"id": r["id"], "gt": gts[r["id"]], "pred": clean(r["raw"]), "s": r["s"], "cer": 1 - prepare.char_acc(gts[r["id"]], clean(r["raw"])) if clean(r["raw"]) else 1.0, "exact": False, "parse_ok": False, "struct": False, "tree_sim": None, "halluc": True, "stop_leak": False, "false_gt": False, "silent_corr": False, "timeout": True}
    finally: signal.alarm(0)


_CH = {}
def _score_row(r, gts, split):
    if split == "own_ketten" and "c" not in _CH: _CH["c"] = chain_prev()
    chains = _CH.get("c") if split == "own_ketten" else {}
    gt = gts[r["id"]]; raw = r["raw"]; pred = clean(raw)
    if r.get("error"): return {"id": r["id"], "error": r["error"], "s": r["s"], "pred": "", "gt": gt}
    s = sb.score(gt, pred) if pred else {"exact": False, "sympy_equal": None, "parse_ok": False, "tree_sim": None}
    tg, tp = truth(gt), truth(pred) if pred else None
    sc = bool(tg is False and tp is True and sb.normalize(gt) != sb.normalize(pred))
    if chains:  # Ketten: GT-Schritt folgt NICHT aus Vorgänger (echter Fehler), Vorhersage folgt aber doch -> stille Korrektur
        m = re.match(r"ketten_(K\d+)_s(\d+)", r["id"]); c = chains.get(m.group(1)) if m else None
        if c:
            prev = c["steps"][int(m.group(2)) - 1]; cg, cp = consistent(prev, gt), consistent(prev, pred) if pred else None
            tg = False if cg is False else tg; tp = cp if cp is not None else tp
            sc = bool(cg is False and cp is True and sb.normalize(gt) != sb.normalize(pred))
    return {"id": r["id"], "gt": gt, "pred": pred, "raw_len": len(raw), "s": r["s"],
            "cer": 1 - prepare.char_acc(gt, pred) if pred else 1.0, "exact": bool(s["exact"]), "parse_ok": bool(s["parse_ok"]),
            "struct": bool(s["sympy_equal"]), "tree_sim": s["tree_sim"], "halluc": halluc(gt, raw, pred),
            "stop_leak": bool(re.search(r"\nassistant\b|<think>", raw)), "false_gt": tg is False, "silent_corr": sc}


def agg(model, split, items, meta):
    ok = [i for i in items if "error" not in i]; n = len(items)
    f = lambda k: sum(1 for i in ok if i[k]) / n
    lat = sorted(i["s"] for i in ok[1:]) or [0]; fg = [i for i in ok if i["false_gt"]]
    m = meta or {}
    return {"model": model, "split": split, "n": n, "errors": n - len(ok),
            "cer": round(sum(i["cer"] for i in ok) / n + (n - len(ok)) / n, 4), "exact": round(f("exact"), 4), "parse_ok": round(f("parse_ok"), 4),
            "struct": round(f("struct"), 4), "tree_sim": round(statistics.mean([i["tree_sim"] for i in ok if i["tree_sim"] is not None] or [0]), 4),
            "halluc": round(f("halluc"), 4), "stop_leak": round(f("stop_leak"), 4), "false_gt_n": len(fg), "silent_corr_n": sum(i["silent_corr"] for i in ok),
            "silent_corr_of_false_gt": round(sum(i["silent_corr"] for i in fg) / len(fg), 4) if fg else "",
            "cold_load_s": round(m.get("load_s", 0), 2), "first_inf_s": round(m.get("first_inference_s") or 0, 2),
            "warm_p50_s": round(lat[len(lat) // 2], 3), "warm_p95_s": round(lat[max(int(len(lat) * .95) - 1, 0)], 3),
            "peak_rss_mb": round(m.get("peak_rss_mb", 0)), "mps_mb": round(m.get("mps_driver_mb", 0)), "weights_mb": round(m.get("weights_disk_mb", 0))}


def baselines(split, gts, rows_gt):
    res = {}
    db = sqlite3.connect(f"file:{MAIN / 'cache.sqlite'}?mode=ro", uri=True)
    items = []
    for r in rows_gt:
        k = hashlib.sha1(b"texteller" + (FW / r["png"]).read_bytes()).hexdigest()
        row = db.execute("select latex,s from c where k=?", (k,)).fetchone()
        if row: items.append({"id": r["id"], "raw": re.sub(r"^\\\[|\\\]$", "", row[0].strip()).strip(), "s": row[1], "error": None})
    if len(items) == len(rows_gt): res["BASELINE_texteller"] = (items, {})
    lp = MAIN / f"last_{split}.jsonl"
    if lp.exists():
        L = [json.loads(l) for l in open(lp)]
        if len(L) == len(rows_gt): res["BASELINE_pipeline_tt+glm"] = ([{"id": x["id"], "raw": x["pred"], "s": x["s"], "error": None} for x in L], {})
    return res


def rescue(items, tt):
    """Komplementarität zu TexTeller allein: Anteil der Bilder, die TexTeller falsch hat (struct) und das Modell richtig; union = einer von beiden richtig."""
    ok = {i["id"]: bool(i.get("struct")) for i in items if "error" not in i}
    wrong = [k for k, v in tt.items() if not v]
    got = sum(1 for k in wrong if ok.get(k))
    union = sum(1 for k, v in tt.items() if v or ok.get(k))
    return {"rescue_n": got, "tt_wrong_n": len(wrong), "rescue_rate": round(got / len(wrong), 4) if wrong else "", "union_struct": round(union / len(tt), 4) if tt else ""}


def main():
    table, per = [], []
    for split in SPLITS:
        rows_gt = prepare.load(split); gts = {r["id"]: r["gt_latex"] for r in rows_gt}
        bl = baselines(split, gts, rows_gt); tt = {}
        if "BASELINE_texteller" in bl: tt = {i["id"]: bool(i.get("struct")) for i in score_rows(bl["BASELINE_texteller"][0], gts, split)}
        for mdl in sorted(REG):
            f = HERE / "raw" / mdl / f"{split}.jsonl"
            if not f.exists(): continue
            rows = [json.loads(l) for l in open(f)]
            meta = json.load(open(f.with_suffix(".meta.json"))) if f.with_suffix(".meta.json").exists() else {}
            if len(rows) < len(rows_gt): print(f"WARN {mdl}/{split}: nur {len(rows)}/{len(rows_gt)}", file=sys.stderr)
            it = score_rows(rows, gts, split); table.append({**agg(mdl, split, it, meta), **rescue(it, tt)}); per += [{"model": mdl, "split": split, **i} for i in it]
        for name, (rows, meta) in bl.items():
            it = score_rows(rows, gts, split); table.append({**agg(name, split, it, meta), **({} if name == 'BASELINE_texteller' else rescue(it, tt))}); per += [{"model": name, "split": split, **i} for i in it]
    if not table: sys.exit("keine Rohdaten")
    with open(HERE / "BENCHMARK_RESULTS.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for t in table for k in t}, key=lambda k: ([*table[0], 'rescue_n', 'tt_wrong_n', 'rescue_rate', 'union_struct'].index(k))), restval=''); w.writeheader(); w.writerows(table)
    (HERE / "per_item.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in per))
    for t in table: print(f"{t['model']:28} {t['split']:11} n={t['n']:3} cer={t['cer']:.3f} exact={t['exact']:.3f} struct={t['struct']:.3f} parse={t['parse_ok']:.2f} hall={t['halluc']:.2f} sc={t['silent_corr_n']}/{t['false_gt_n']} p50={t['warm_p50_s']}s")


if __name__ == "__main__":
    main()
