"""Flywheel-Schritt (Stufe 2) für EIN Modell. Der Betreuer (Haiku) schlägt pro Iteration GENAU EINE Änderung vor; diese Datei misst und entscheidet.
Annahmeregel (vom Evaluator erzwungen, nicht vom Betreuer): Änderung wird nur akzeptiert, wenn
  (a) auf dem Batch struct strictly steigt (oder struct gleich und CER um >=0.01 sinkt) UND
  (b) auf der festen dev-Kontrolle (80 Bilder, seed 0) struct nicht sinkt.
Daten: nur train (Batch) und dev (Kontrolle). own_probe/own_ketten/test werden hier NIE geladen.
  python fw_step.py --model uni_qwen3vl_2b --iter 0                         # Baseline/State anlegen
  python fw_step.py --model uni_qwen3vl_2b --iter 1 --change '{"key":"height","value":128}'
Batchgröße: ungerade Iteration 10, gerade 20. Batch = die N schwersten (höchste CER) von 4N zufälligen train-Bildern unter der akzeptierten Konfiguration."""
import argparse, json, os, random, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if (HERE / "hf_cache").exists(): os.environ.setdefault("HF_HUB_OFFLINE", "1")
import mb_run, mb_score as S
from PIL import Image, ImageOps

SPACE = {   # gleiche Auswahl für beide Modelle (gleiches Budget, faire Suche)
    "prompt": ["MODELL-STANDARD", "Transcribe the handwritten math expression in this image into LaTeX. Output only the LaTeX, no $ signs, no explanation.",
               "Convert this mathematical formula to LaTeX.", "Transcribe exactly what is written, including any mistakes. Output only LaTeX.",
               "Write the LaTeX representation for this image."],
    "height": [None, 64, 96, 128, 192, 256],       # Höhe in Pixel, Seitenverhältnis bleibt; None = Originalgröße
    "pad_frac": [0.0, 0.125, 0.25],                 # weißer Rand als Anteil der Höhe
    "autocontrast": [False, True],
    "beams": [1, 3, 5],
    "strip_font": [False, True],                    # \mathrm{..}/\boldmath/\cal/\mathbf-Hüllen entfernen (Nachbearbeitung)
    "decimal_comma": [False, True],                 # Ziffer,Ziffer -> Ziffer.Ziffer (Nachbearbeitung)
}
DEFAULT = {"prompt": 0, "height": None, "pad_frac": 0.0, "autocontrast": False, "beams": 1, "strip_font": False, "decimal_comma": False}
CONTROL_N = 80


def prep(img, c):
    img = img.convert("RGB")
    if c["autocontrast"]: img = ImageOps.autocontrast(img.convert("L")).convert("RGB")
    if c["height"]:
        w, h = img.size; img = img.resize((max(1, round(w * c["height"] / h)), c["height"]), Image.LANCZOS)
    if c["pad_frac"]:
        img = ImageOps.expand(img, border=round(img.size[1] * c["pad_frac"]), fill=(255, 255, 255))
    return img


def post(raw, c):
    import re
    if c["strip_font"]: raw = re.sub(r"\\(?:mathrm|mathbf|mathit|cal|boldmath|bf|rm)\s*(?:\{([^{}]*)\})?", lambda m: m.group(1) or "", raw)
    if c["decimal_comma"]: raw = re.sub(r"(\d),(\d)", r"\1.\2", raw)
    return raw


class Runner(mb_run.QwenVL):
    def go(self, img, c):
        torch = self.torch
        p = SPACE["prompt"][c["prompt"]]; p = self.cfg["prompt"] if p == "MODELL-STANDARD" else p
        msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": p}]}]
        try: text = self.proc.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False)
        except TypeError: text = self.proc.apply_chat_template(msgs, add_generation_prompt=True)
        inp = self.proc(text=[text], images=[prep(img, c)], return_tensors="pt").to("mps")
        with torch.no_grad():
            out = self.model.generate(**inp, max_new_tokens=256, do_sample=False, num_beams=c["beams"], eos_token_id=self.eos)
        torch.mps.synchronize()
        return self.proc.batch_decode(out[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0]


def evaluate(runner, rows, c, gts):
    its = []
    for r in rows:
        img = Image.open(mb_run.FW / r["png"])
        try: raw = post(runner.go(img, c), c); err = None
        except Exception as e: raw, err = "", f"{type(e).__name__}: {e}"
        row = {"id": r["id"], "raw": raw, "s": 0.0, "error": err}
        its.append(S.score_rows([row], gts)[0])
    ok = [i for i in its if "error" not in i]
    n = max(len(its), 1)
    return {"struct": sum(i["struct"] for i in ok) / n, "cer": (sum(i["cer"] for i in ok) + (len(its) - len(ok))) / n, "items": its}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--iter", type=int, required=True); ap.add_argument("--change")
    a = ap.parse_args()
    cfgm = next(m for m in mb_run.REG if m["key"] == a.model)
    d = HERE / "fw" / a.model; d.mkdir(parents=True, exist_ok=True)
    sf, lf = d / "state.json", d / "log.jsonl"
    train, dev = S.prepare.load("train"), S.prepare.load("dev")
    gts = {r["id"]: r["gt_latex"] for r in train + dev}
    control = random.Random(0).sample(dev, CONTROL_N)
    path = mb_run.fetch(cfgm); runner = Runner(cfgm, path)
    if a.iter == 0:
        c = dict(DEFAULT); t0 = time.time(); ev = evaluate(runner, control, c, gts)
        sf.write_text(json.dumps({"cfg": c, "control_struct": ev["struct"], "control_cer": ev["cer"], "iters_done": 0, "accepted": []}))
        print(json.dumps({"iter": 0, "baseline_control_struct": round(ev["struct"], 4), "control_cer": round(ev["cer"], 4), "space": {k: v for k, v in SPACE.items()}, "s": round(time.time() - t0)})); return
    st = json.loads(sf.read_text())
    if a.iter != st["iters_done"] + 1: sys.exit(f"erwartet --iter {st['iters_done'] + 1}")
    ch = json.loads(a.change); k, v = ch["key"], ch["value"]
    if k not in SPACE: sys.exit(f"unbekannter Schlüssel {k}; erlaubt: {list(SPACE)}")
    vi = v if k == "prompt" else SPACE[k].index(v) if v in SPACE[k] else None
    if vi is None or (k == "prompt" and not (0 <= v < len(SPACE["prompt"]))): sys.exit(f"Wert {v} nicht erlaubt für {k}: {SPACE[k]}")
    base = st["cfg"]; cand = dict(base); cand[k] = v
    if cand == base: sys.exit("Änderung ist identisch zur akzeptierten Konfiguration")
    N = 10 if a.iter % 2 == 1 else 20
    rnd = random.Random(1000 + a.iter); pool = rnd.sample(train, 4 * N)
    pe = evaluate(runner, pool, base, gts)
    worst = sorted(pe["items"], key=lambda i: -i.get("cer", 1))[:N]; batch_ids = {i["id"] for i in worst}
    batch = [r for r in pool if r["id"] in batch_ids]
    b_base = {"struct": sum(i["struct"] for i in worst if "error" not in i) / N, "cer": sum(i.get("cer", 1) for i in worst) / N}
    b_cand = evaluate(runner, batch, cand, gts)
    gain = b_cand["struct"] > b_base["struct"] or (b_cand["struct"] == b_base["struct"] and b_base["cer"] - b_cand["cer"] >= 0.01)
    c_cand = evaluate(runner, control, cand, gts) if gain else None
    accept = bool(gain and c_cand["struct"] >= st["control_struct"])
    fails = [{"gt": i["gt"], "pred": i["pred"]} for i in sorted(b_cand["items"], key=lambda i: -i.get("cer", 1))[:6] if not i.get("struct")]
    rec = {"iter": a.iter, "batch_n": N, "change": ch, "batch_base": {x: round(b_base[x], 4) for x in ("struct", "cer")}, "batch_cand": {x: round(b_cand[x], 4) for x in ("struct", "cer")},
           "control_base_struct": round(st["control_struct"], 4), "control_cand_struct": None if c_cand is None else round(c_cand["struct"], 4),
           "accepted": accept, "reason": ("kein Gewinn auf Batch" if not gain else "Kontrolle verschlechtert" if not accept else "Gewinn auf Batch, Kontrolle nicht schlechter"),
           "cfg_after": cand if accept else base, "remaining_failures": fails}
    with open(lf, "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    st["iters_done"] = a.iter
    if accept: st.update(cfg=cand, control_struct=c_cand["struct"], control_cer=c_cand["cer"]); st["accepted"].append(rec["change"])
    sf.write_text(json.dumps(st)); print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
