"""Ouroboros (ADR-009): synthetische Kettenseiten — der AI-Student schreibt GT, die Schriftsimulation schreibt ab.

10 Seiten im Kalibrierungs-Layout (1404x1872, ROW=106, SPLIT=660 wie kalib/ketten/build.py).
Ketten nur in Formen, die der Validator prüfen kann (Vokabular aus kalib/ketten/items.py):
linear, Klammer, quadratisch (+-k und pq), Bruch, Zahlterm, Potenz — ca. die Hälfte mit
bekanntem Erstfehler (label), konsistent weitergeschrieben (wie K02/K06).

Schlangen-Schwanz-Gate: jede Kette wird VOR dem Rendern durch chain_bench.judge() geschickt.
pred != label => Kette wird verworfen (und gezählt). GT wird nie nachträglich korrigiert.

Schriftsimulation: SchlangebeißtinSchwanz/dynamic_writer (read-only, Importmuster wie
bench/formula_flywheel/synth/gen.py). Potenzen als hochgestellte kleine Ziffern,
Brüche inline (5/2 => \\frac{5}{2}). Slot-PNGs wie kalib_eval.render: Breite 4, Pad 20 —
dieselbe Pixelverteilung wie der reale Pfad (Fetch -> rmscene -> PIL-Linien).

Ausgabe (alle relativ zu bench/synth/):
  ketten_gt.jsonl    Schema wie kalib/ketten/ketten_gt.jsonl (id, topic, steps, label, error_kind, slots)
  synth_ketten.jsonl Schema wie own_ketten.jsonl (Schritte >= 1; Schritt 0 ist Aufgabe, bleibt GT)
  png/               Slot-PNGs, png/synth_S01_s1.png etc. (Pfade relativ zu bench/synth/)
  pages/page_NN.png  ganze Seiten fuer claudebench / Augenschein

Aufruf: .venv_structure/bin/python bench/synth/gen_ketten.py [seiten=10] [seed=23]
"""
from __future__ import annotations

import json
import random
import sys
from math import gcd
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SCHWANZ = ROOT.parent / "SchlangebeißtinSchwanz"
sys.path.insert(0, str(ROOT / "bench"))          # chain_bench.judge (Validierung des GT)
sys.path.insert(0, str(SCHWANZ))                 # dynamic_writer (read-only)
from chain_bench import judge  # noqa: E402
import dynamic_writer as W      # noqa: E402

OUT = Path(__file__).resolve().parent
PAGE_W, PAGE_H, MARGIN = 1404, 1872, 70
TOP, ROW, BOTTOM, SPLIT = 100, 106, 30, 660
ROWS_PER_PAGE = (PAGE_H - TOP - BOTTOM) // ROW   # 16

ERR_RATE = 0.45


def fr(n: int, d: int) -> str:
    return "\\frac{" + str(n) + "}{" + str(d) + "}"


# ---------------------------------------------------------------- AI-Student: Ketten
# Jeder Generator -> dict(topic, steps, disp, label, error_kind) oder None (neu würfeln).
# steps = LaTeX-GT, disp = Schreib-Token je Schritt (str = Basislinie, (txt, "s") = hochgestellt).

def g_linear(rng, err):
    kind = rng.choice(("vorzeichen", "division", "rechen")) if err else None
    for _ in range(30):
        a = rng.randint(2, 6); b = rng.randint(1, 9); sol = rng.randint(2, 9); c = a * sol + b
        if kind == "vorzeichen":
            if (c + b) % a:
                continue
            steps = [f"{a}x+{b}={c}", f"{a}x={c + b}", f"x={(c + b) // a}"]
            return dict(topic="linear", steps=steps, disp=steps, label=1,
                        error_kind="Vorzeichen beim Seitenwechsel")
        if kind == "division":
            steps = [f"{a}x+{b}={c}", f"{a}x={c - b}", f"x+{b}={sol}", f"x={sol - b}"]
            return dict(topic="linear", steps=steps, disp=steps, label=2, error_kind="Divisionsregel")
        if kind == "rechen":
            steps = [f"{a}x+{b}={c}", f"{a}x={c - b}", f"x={sol + rng.choice((-1, 1))}"]
            return dict(topic="linear", steps=steps, disp=steps, label=2, error_kind="Rechenfehler")
        steps = [f"{a}x+{b}={c}", f"{a}x={c - b}", f"x={sol}"]
        return dict(topic="linear", steps=steps, disp=steps, label=-1, error_kind=None)
    return None


def g_klammer(rng, err):
    a = rng.randint(2, 5); b = rng.randint(1, 5); sol = rng.randint(2, 9); c = a * (sol + b)
    if not err:
        steps = [f"{a}(x+{b})={c}", f"{a}x+{a * b}={c}", f"{a}x={c - a * b}", f"x={sol}"]
        return dict(topic="linear", steps=steps, disp=steps, label=-1, error_kind=None)
    steps = [f"{a}(x+{b})={c}", f"{a}x+{b}={c}", f"{a}x={c - b}"]
    return dict(topic="linear", steps=steps, disp=steps, label=1, error_kind="Distributivgesetz")


def g_quad(rng, err):
    k = rng.randint(2, 7)
    task = f"x^{{2}}-{k * k}=0"
    d_task = ["x", ("2", "s"), f"-{k * k}=0"]
    s1, d1 = f"x^{{2}}={k * k}", ["x", ("2", "s"), f"={k * k}"]
    if not err:
        fac = f"(x-{k})(x+{k})=0"
        return dict(topic="quadratisch", steps=[task, s1, fac], disp=[d_task, d1, [fac]],
                    label=-1, error_kind=None)
    if rng.random() < 0.5:
        steps = [task, s1, f"x={k}"]
        return dict(topic="quadratisch", steps=steps, disp=[d_task, d1, [f"x={k}"]],
                    label=2, error_kind="Wurzelziehen: zweite Lösung fehlt")
    fac = f"(x-{k})(x-{k})=0"
    return dict(topic="quadratisch", steps=[task, s1, fac], disp=[d_task, d1, [fac]],
                 label=2, error_kind="Vorzeichen in der Faktorform")


def g_quad_pq(rng, err):
    for _ in range(30):
        r1, r2 = sorted(rng.sample(range(1, 7), 2))
        s, q, d2 = r1 + r2, r1 * r2, (r2 - r1) ** 2
        if q == d2:  # sieht wie ein Setzen aus, vermeiden
            continue
        task = f"x^{{2}}-{s}x+{q}=0"
        d_task = ["x", ("2", "s"), f"-{s}x+{q}=0"]
        erg = rf"(x-\frac{{{s}}}{{2}})^{{2}}=\frac{{{d2}}}{{4}}"
        d_erg = [f"(x-{s}/2)", ("2", "s"), f"={d2}/4"]
        fac = f"(x-{r1})(x-{r2})=0"
        if not err:
            return dict(topic="quadratisch", steps=[task, erg, fac],
                        disp=[d_task, d_erg, [fac]], label=-1, error_kind=None)
        if rng.random() < 0.5:
            erg_w = rf"(x-\frac{{{s}}}{{2}})^{{2}}=\frac{{{d2 + 2}}}{{4}}"
            return dict(topic="quadratisch", steps=[task, erg_w, fac],
                        disp=[d_task, [f"(x-{s}/2)", ("2", "s"), f"={d2 + 2}/4"], [fac]],
                         label=1, error_kind="quadratische Ergänzung")
        fac_w = f"(x-{r1})(x+{r2})=0"
        return dict(topic="quadratisch", steps=[task, erg, fac_w],
                    disp=[d_task, d_erg, [fac_w]], label=2, error_kind="Vorzeichen in der Faktorform")
    return None


def g_bruch_add(rng, err):
    for _ in range(30):
        a, c = rng.randint(1, 5), rng.randint(1, 5)
        b, d = rng.randint(2, 6), rng.randint(2, 6)
        if b == d:
            continue
        num, den = a * d + c * b, b * d
        if gcd(num, den) != 1 and num // gcd(num, den) == 1:  # trivial 1/x
            continue
        steps = [fr(a, b) + "+" + fr(c, d), "=" + fr(a * d, den) + "+" + fr(c * b, den),
                 "=" + fr(num, den)]
        disp = [f"{a}/{b}+{c}/{d}", f"={a * d}/{den}+{c * b}/{den}", f"={num}/{den}"]
        g = gcd(num, den)
        if g > 1:
            steps.append("=" + fr(num // g, den // g))
            disp.append(f"={num // g}/{den // g}")
        if not err:
            return dict(topic="bruch", steps=steps, disp=disp, label=-1, error_kind=None)
        if rng.random() < 0.5:
            return dict(topic="bruch", steps=[steps[0], "=" + fr(a + c, b + d)],
                        disp=[disp[0], f"={a + c}/{b + d}"], label=1, error_kind="Nenner addiert")
        if g > 1:
            i = len(steps) - 1
            steps[i] = "=" + fr(num // g + 1, den // g)
            disp[i] = f"={num // g + 1}/{den // g}"
            return dict(topic="bruch", steps=steps, disp=disp, label=i, error_kind="falsch gekürzt")
        steps[2] = "=" + fr(num + 1, den)
        disp[2] = f"={num + 1}/{den}"
        return dict(topic="bruch", steps=steps, disp=disp, label=2, error_kind="Rechenfehler")
    return None


def g_bruch_mul(rng, err):
    for _ in range(30):
        a, c = rng.randint(1, 5), rng.randint(1, 5)
        b, d = rng.randint(2, 6), rng.randint(2, 6)
        if b == d or a == c:
            continue
        num, den = a * c, b * d
        g = gcd(num, den)
        steps = [fr(a, b) + r"\cdot" + fr(c, d), "=" + fr(num, den)]
        disp = [f"{a}/{b}·{c}/{d}", f"={num}/{den}"]
        if g > 1:
            steps.append("=" + fr(num // g, den // g))
            disp.append(f"={num // g}/{den // g}")
        if not err:
            return dict(topic="bruch", steps=steps, disp=disp, label=-1, error_kind=None)
        if rng.random() < 0.5:
            return dict(topic="bruch", steps=[steps[0], "=" + fr(a * c, b + d)],
                        disp=[disp[0], f"={a * c}/{b + d}"], label=1, error_kind="Nenner addiert")
        i = len(steps) - 1
        num_w = (num // g if g > 1 else num) + 1
        steps[i] = "=" + (fr(num_w, den // g) if g > 1 else fr(num_w, den))
        disp[i] = f"={num_w}/{den // g if g > 1 else den}"
        return dict(topic="bruch", steps=steps, disp=disp, label=i, error_kind="falsch gekürzt")
    return None


def g_zahl(rng, err):
    m = rng.randint(11, 19); n = rng.randint(3, 9); rest = m - 10
    if not err:
        steps = [f"{m}\\cdot{n}", f"={n}\\cdot10+{n}\\cdot{rest}",
                 f"={n * 10}+{n * rest}", f"={m * n}"]
        disp = [f"{m}·{n}", f"={n}·10+{n}·{rest}", f"={n * 10}+{n * rest}", f"={m * n}"]
        return dict(topic="zahl", steps=steps, disp=disp, label=-1, error_kind=None)
    if rng.random() < 0.5:
        steps = [f"{m}\\cdot{n}", f"={n}\\cdot10+{rest}"]
        return dict(topic="zahl", steps=steps, disp=[f"{m}·{n}", f"={n}·10+{rest}"],
                    label=1, error_kind="Distributivgesetz")
    off = rng.choice((1, 2))
    steps = [f"{m}\\cdot{n}", f"={n}\\cdot10+{n}\\cdot{rest}", f"={n * 10}+{n * rest}",
             f"={m * n + off}"]
    disp = [f"{m}·{n}", f"={n}·10+{n}·{rest}", f"={n * 10}+{n * rest}", f"={m * n + off}"]
    return dict(topic="zahl", steps=steps, disp=disp, label=3, error_kind="Additionsfehler")


def g_potenz(rng, err):
    base = rng.randint(2, 5); m_, n_ = rng.randint(2, 4), rng.randint(2, 4)
    task = f"{base}^{{{m_}}}\\cdot{base}^{{{n_}}}"
    d_task = [f"{base}", (f"{m_}", "s"), "·", f"{base}", (f"{n_}", "s")]
    if not err:
        steps = [task, f"={base}^{{{m_ + n_}}}", f"={base ** (m_ + n_)}"]
        disp = [d_task, ["=", f"{base}", (f"{m_ + n_}", "s")], [f"={base ** (m_ + n_)}"]]
        return dict(topic="potenz", steps=steps, disp=disp, label=-1, error_kind=None)
    if rng.random() < 0.5:
        steps = [task, f"={base}^{{{m_ * n_}}}", f"={base ** (m_ * n_)}"]
        disp = [d_task, ["=", f"{base}", (f"{m_ * n_}", "s")], [f"={base ** (m_ * n_)}"]]
        return dict(topic="potenz", steps=steps, disp=disp, label=1,
                    error_kind="Exponenten multipliziert")
    steps = [task, f"={base}^{{{m_ + n_}}}", f"={base ** (m_ + n_) + base}"]
    disp = [d_task, ["=", f"{base}", (f"{m_ + n_}", "s")], [f"={base ** (m_ + n_) + base}"]]
    return dict(topic="potenz", steps=steps, disp=disp, label=2, error_kind="Rechenfehler")


GENS = [g_linear, g_linear, g_klammer, g_quad, g_quad_pq, g_quad_pq,
        g_bruch_add, g_bruch_mul, g_zahl, g_potenz]


# ---------------------------------------------------------------- Schriftsimulation
def write_tokens(tokens, x0, baseline, scale, seed):
    """Token-Liste -> Stiche; ('txt','s') wird klein und hochgestelllt gesetzt."""
    strokes, pen, sd = [], x0, seed
    for tok in tokens:
        text, sup = (tok, "b") if isinstance(tok, str) else tok
        if sup == "s":
            s = W.synthesize_handwriting_line(text, pen, baseline - scale * 6.5,
                                              scale=scale * 0.62, style="student", seed=sd)
            pen += W.measure_text_width(text, scale * 0.62) + scale * 1.1
        else:
            s = W.synthesize_handwriting_line(text, pen, baseline, scale=scale,
                                              style="student", seed=sd)
            pen += W.measure_text_width(text, scale) + scale * 1.1
        strokes.extend(s)
        sd += 17
    return strokes


def render(strokes, pad=20, width=4):
    """Slot-PNG exakt im Stil von kalib_eval.render (Breite 4, Pad 20)."""
    pts = [(p[0], p[1]) for s in strokes for p in s["points"]]
    x0, y0 = min(x for x, _ in pts) - pad, min(y for _, y in pts) - pad
    im = Image.new("L", (int(max(x for x, _ in pts) - x0 + pad), int(max(y for _, y in pts) - y0 + pad)), 255)
    d = ImageDraw.Draw(im)
    for s in strokes:
        d.line([(p[0] - x0, p[1] - y0) for p in s["points"]], fill=0, width=width, joint="curve")
    return im


# ---------------------------------------------------------------- Seiten zusammenbauen
def main():
    npages = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 23
    rng = random.Random(seed)
    for sub in ("png", "pages"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        for old in (OUT / sub).glob("*.png"):
            old.unlink()          # kein Mischbestand aus frueheren Laeufen

    pages, cur, mood = [], None, 0.0
    gt_rows, ketten_rows, dropped = [], [], []
    topics = {}

    def new_page():
        nonlocal cur, mood
        cur = {"strokes": [], "used": 0}
        pages.append(cur)
        mood = rng.uniform(2.6, 3.3)

    new_page()
    while len(pages) <= npages:
        cand = rng.choice(GENS)(rng, rng.random() < ERR_RATE)
        if cand is None:
            continue
        pred, _, _ = judge(cand["steps"])
        if pred != cand["label"]:
            dropped.append({"topic": cand["topic"], "label": cand["label"], "pred": pred})
            continue
        need = len(cand["steps"])
        if cur["used"] + need > ROWS_PER_PAGE:
            if len(pages) == npages:
                break
            new_page()
        cid = f"S{len(gt_rows) + 1:02d}"
        topics[cand["topic"]] = topics.get(cand["topic"], 0) + 1
        page_i, row0 = len(pages) - 1, TOP + cur["used"] * ROW

        task_strokes = write_tokens(cand["disp"][0], MARGIN + 6, row0 + 78,
                                    mood, rng.randint(1, 10**6))
        cur["strokes"].extend(task_strokes)
        slots = []
        for k in range(1, need):
            y = row0 + k * ROW
            st = write_tokens(cand["disp"][k], SPLIT + 30, y + 78,
                              mood * rng.uniform(0.94, 1.06), rng.randint(1, 10**6))
            cur["strokes"].extend(st)
            slots.append({"step": k, "page": page_i, "slot_y": [y + 4, y + ROW - 16],
                          "x_min": SPLIT})
            render(st).save(OUT / "png" / f"synth_{cid}_s{k}.png")
            ketten_rows.append({"id": f"synth_{cid}_s{k}", "src": "synth",
                                "png": f"png/synth_{cid}_s{k}.png",
                                "gt_latex": cand["steps"][k], "chain_id": cid, "step": k})
        cur["used"] += need
        gt_rows.append({"id": cid, "topic": cand["topic"], "steps": cand["steps"],
                        "label": cand["label"], "error_kind": cand["error_kind"], "slots": slots})

    for i, pg in enumerate(pages):
        im = Image.new("L", (PAGE_W, PAGE_H), 255)
        d = ImageDraw.Draw(im)
        for s in pg["strokes"]:
            d.line([(p[0], p[1]) for p in s["points"]], fill=0, width=4, joint="curve")
        im.save(OUT / "pages" / f"page_{i:02d}.png")

    (OUT / "ketten_gt.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gt_rows), encoding="utf-8")
    (OUT / "synth_ketten.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ketten_rows), encoding="utf-8")

    n_ok = sum(1 for r in gt_rows if r["label"] == -1)
    print(json.dumps({"seed": seed, "pages": len(pages), "ketten": len(gt_rows),
                      "davon_korrekt": n_ok, "mit_fehler": len(gt_rows) - n_ok,
                      "slots": len(ketten_rows), "verworfen": dropped, "topics": topics},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
