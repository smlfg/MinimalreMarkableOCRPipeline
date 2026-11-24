"""Ouroboros v2: schwere Formeln als Flywheel-Split `synth_hard` (ADR-008/009).

Der AI-Student schreibt schwere Schul-/Uni-Mathematik mit bekanntem GT, die
Schriftsimulation schreibt sie ab, das Flywheel misst struct/char wie bei jedem
Split (prepare.py eingefroren, nur der Zaehler hier ist neu).

Themen: unbestimmte und bestimmte Integrale, Summen (Gauss, k^2, gerade, geometrisch),
Algebra-Identitaeten (binomisch (a+b)^3, Potenzgesetze), Wurzeln, pi, Bruch-Identitaeten.

Schlangen-Schwanz-Gate: jede Formel wird VOR dem Rendern gegen SymPy verifiziert
(ocr.latex.parse + doit/expand; Integrationskonstante C mit C->0; sonst numerische
Stichprobe an festen Substituten). Definitionen (A=pi r^2) durchlaufen nur den Parse-Gate.
GT wird nie nachtraeglich korrigiert.

Glyphen: int, Sigma und pi fehlen in SchlangebeißtinSchwanz/font.py — sie werden
LOKAL in den importierten Glyph-Spiegel ergaenzt (nur im RAM, das Repo bleibt unangetastet).

Ausgabe (relativ zu bench/formula_flywheel/):
  data/synth_hard.jsonl   Zeilen {id, src: "synth_hard", png, gt_latex} wie jeder Split
  synth/images_hard/       Zeilen-PNGs im kalib_eval.render-Stil (Breite 4, Pad 20)

Aufruf: .venv_structure/bin/python synth/gen_hard.py [n=129] [seed=31]
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import sympy
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent            # .../formula_flywheel/synth
FW = HERE.parent                                  # .../formula_flywheel
ROOT = FW.parents[1]                             # Repo
SCHWANZ = ROOT.parent / "SchlangebeißtinSchwanz"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCHWANZ))
from ocr.latex import parse  # noqa: E402
import dynamic_writer as W   # noqa: E402
import font as F             # noqa: E402

# ---------------------------------------------------------------- lokale Glyphen
# Koordinatensystem wie font.py: y 0 (Basislinie) bis 14 (Grosse Hoehe), x in Advance-Einheiten.
F.GLYPHS["∫"] = (7.0, [
    [[6.5, 17.5], [5.2, 17.9], [4.1, 16.6], [3.6, 14.2], [3.2, 11.0], [2.9, 7.2],
     [2.7, 3.6], [2.2, 0.6], [1.1, -1.7], [-0.1, -2.3]],
    [[-0.3, -2.5], [0.7, -2.6], [1.5, -2.0], [2.0, -1.0]],
])
F.GLYPHS["Σ"] = (9.0, [
    [[1.2, 14.0], [7.8, 14.0]],
    [[7.8, 14.0], [1.5, 7.6], [7.6, 0.6]],
    [[7.6, 0.6], [1.2, 0.6]],
])
F.GLYPHS["π"] = (9.0, [
    [[0.8, 11.8], [8.2, 11.8]],
    [[2.2, 11.8], [2.4, 0.2]],
    [[6.2, 11.8], [6.0, 0.2]],
    [[3.0, 9.0], [5.4, 9.0]],
])

# ---------------------------------------------------------------- SymPy-Gate
SUBS = {"a": 2, "b": 8, "m": 3, "n": 4, "q": 3, "r": 5, "x": 2, "y": 3,
        "c": 1, "d": 6, "e": 7, "k": 1, "A": 9, "U": 10}


def gt_ok(gt: str, definition: bool = False) -> bool:
    g = gt.replace("+C", "")                      # Integrationskonstante: mit C->0 pruefen
    e = parse(g)
    if e is None:
        return False
    if definition:
        return True
    if not isinstance(e, sympy.Equality):
        return False
    try:
        if sympy.simplify(sympy.expand((e.lhs - e.rhs).doit())) == 0:
            return True
    except Exception:
        pass
    try:                                           # numerische Stichprobe an festen Punkten
        d = (e.lhs - e.rhs).doit()
        return sympy.simplify(sympy.expand(d.subs(SUBS))) == 0
    except Exception:
        return False


def fr(n, d):
    return "\\frac{" + str(n) + "}{" + str(d) + "}"


# ---------------------------------------------------------------- Formel-Katalog
# Jeder Generator -> (topic, gt_latex, tokens, definition). tokens: str = Basislinie,
# ("txt", "s") = hochgestellt, ("txt", "t") = tiefgestellt (Summen-/Integralgrenzen).

def m_integral_unb(rng):
    n = rng.randint(2, 5)
    gt = "\\int x^{" + str(n) + "} dx=" + fr("x^{" + str(n + 1) + "}", str(n + 1)) + "+C"
    toks = ["∫", "x", (str(n), "s"), "dx=x", (str(n + 1), "s"), "/" + str(n + 1) + "+C"]
    return ("integral", gt, toks, False)


def m_integral_lin(rng):
    a = rng.randint(2, 5); b = rng.randint(1, 9)
    gt = "\\int (" + str(a) + "x+" + str(b) + ") dx=" + fr(str(a), "2") + "x^{2}+" + str(b) + "x+C"
    toks = ["∫(", f"{a}x+", f"{b})", f"dx={a}/2·", "x", ("2", "s"), f"+{b}x+", "C"]
    return ("integral", gt, toks, False)


def m_integral_best(rng):
    lo = rng.randint(0, 2); hi = lo + 2 * rng.randint(1, 3)   # gerade Differenz: (hi²-lo²)/2 ganzzahlig
    val = (hi * hi - lo * lo) // 2
    gt = "\\int_{" + str(lo) + "}^{" + str(hi) + "} x dx=" + str(val)
    toks = ["∫", (str(lo), "t"), (str(hi), "s"), "xdx=", str(val)]
    return ("integral", gt, toks, False)


def m_sum_gauss(rng):
    gt = "\\sum_{k=1}^{n} k=" + fr("n(n+1)", "2")
    toks = ["Σ", ("k=1", "t"), ("n", "s"), "k=n(n+1)/2"]
    return ("summe", gt, toks, False)


def m_sum_quad(rng):
    gt = "\\sum_{k=1}^{n} k^{2}=" + fr("n(n+1)(2n+1)", "6")
    toks = ["Σ", ("k=1", "t"), ("n", "s"), "k", ("2", "s"), "=n(n+1)(2n+1)/6"]
    return ("summe", gt, toks, False)


def m_sum_gerad(rng):
    a = rng.randint(1, 4)
    gt = "\\sum_{k=1}^{n} " + str(2 * a) + "k=" + str(a) + "n(n+1)"
    toks = ["Σ", ("k=1", "t"), ("n", "s"), f"{2 * a}k={a}n(n+1)"]
    return ("summe", gt, toks, False)


def m_sum_geo(rng):
    gt = "\\sum_{k=0}^{n} q^{k}=" + fr("q^{n+1}-1", "q-1")
    toks = ["Σ", ("k=0", "t"), ("n", "s"), "q", ("k", "s"), "=(q", ("n+1", "s"), "-1)/(q-1)"]
    return ("summe", gt, toks, False)


def m_alg_binom2(rng):
    gt = "(a+b)^{2}=a^{2}+2ab+b^{2}"
    toks = ["(a+b)", ("2", "s"), "=a", ("2", "s"), "+2ab+b", ("2", "s")]
    return ("algebra", gt, toks, False)


def m_alg_binom3(rng):
    gt = "(a+b)^{3}=a^{3}+3a^{2}b+3ab^{2}+b^{3}"
    toks = ["(a+b)", ("3", "s"), "=a", ("3", "s"), "+3a", ("2", "s"), "b+3ab", ("2", "s"), "+b", ("3", "s")]
    return ("algebra", gt, toks, False)


def m_alg_diff(rng):
    gt = "(a-b)(a+b)=a^{2}-b^{2}"
    toks = ["(a-b)(a+b)=a", ("2", "s"), "-b", ("2", "s")]
    return ("algebra", gt, toks, False)


def m_alg_potenz(rng):
    gt = "a^{m}\\cdot a^{n}=a^{m+n}"
    toks = ["a", ("m", "s"), "·a", ("n", "s"), "=a", ("m+n", "s")]
    return ("algebra", gt, toks, False)


def m_alg_potenz_kl(rng):
    gt = "(a^{m})^{n}=a^{mn}"
    toks = ["(a", ("m", "s"), ")", ("n", "s"), "=a", ("mn", "s")]
    return ("algebra", gt, toks, False)


def m_wurzel_prod(rng):
    a, b = rng.choice([(2, 8), (3, 12), (5, 20), (6, 24), (4, 9), (7, 63)])
    root = int((a * b) ** 0.5)
    gt = "\\sqrt{" + str(a) + "}\\cdot\\sqrt{" + str(b) + "}=" + str(root)
    toks = [f"√{a}·√{b}={root}"]
    return ("wurzel", gt, toks, False)


def m_wurzel_ident(rng):
    gt = "\\sqrt{a b}=\\sqrt{a}\\sqrt{b}"
    toks = ["√(ab)=√a·√b"]
    return ("wurzel", gt, toks, False)


def m_wurzel_zahl(rng):
    a = rng.randint(4, 15)
    gt = "\\sqrt{" + str(a * a) + "}=" + str(a)
    toks = [f"√{a * a}={a}"]
    return ("wurzel", gt, toks, False)


def m_pi_flaeche(rng):
    gt = "A=\\pi r^{2}"
    toks = ["A=π", "r", ("2", "s")]
    return ("pi", gt, toks, True)                 # Definition: nur Parse-Gate


def m_pi_umfang(rng):
    gt = "U=2\\pi r"
    toks = ["U=2π", "r"]
    return ("pi", gt, toks, True)


def m_bruch_ident(rng):
    gt = fr("1", "x") + "+" + fr("1", "y") + "=" + fr("x+y", "xy")
    toks = ["1/x+1/y=(x+y)/xy"]
    return ("bruch", gt, toks, False)


def m_bruch_gleich(rng):
    b = rng.choice((3, 5, 7, 9))
    gt = fr("a", str(b)) + "+" + fr("c", str(b)) + "=" + fr("a+c", str(b))
    toks = [f"a/{b}+c/{b}=(a+c)/{b}"]
    return ("bruch", gt, toks, False)


KATALOG = [(m_integral_unb, 14), (m_integral_lin, 14), (m_integral_best, 12),
           (m_sum_gauss, 8), (m_sum_quad, 8), (m_sum_gerad, 6), (m_sum_geo, 6),
           (m_alg_binom2, 8), (m_alg_binom3, 8), (m_alg_diff, 6),
           (m_alg_potenz, 6), (m_alg_potenz_kl, 5),
           (m_wurzel_prod, 8), (m_wurzel_ident, 4), (m_wurzel_zahl, 4),
           (m_pi_flaeche, 4), (m_pi_umfang, 3),
           (m_bruch_ident, 6), (m_bruch_gleich, 6)]


# ---------------------------------------------------------------- Schriftsimulation
def write_tokens(tokens, x0, baseline, scale, seed):
    strokes, pen, sd = [], x0, seed
    for tok in tokens:
        text, mode = (tok, "b") if isinstance(tok, str) else tok
        if mode == "s":
            s = W.synthesize_handwriting_line(text, pen, baseline - scale * 8.5,
                                              scale=scale * 0.55, style="student", seed=sd)
            pen += W.measure_text_width(text, scale * 0.55) + scale * 1.1
        elif mode == "t":                          # tiefgestellt: Summen-/Integralgrenzen
            s = W.synthesize_handwriting_line(text, pen, baseline + scale * 3.0,
                                              scale=scale * 0.55, style="student", seed=sd)
            pen += W.measure_text_width(text, scale * 0.55) + scale * 1.1
        else:
            s = W.synthesize_handwriting_line(text, pen, baseline, scale=scale,
                                              style="student", seed=sd)
            pen += W.measure_text_width(text, scale) + scale * 1.1
        strokes.extend(s)
        sd += 17
    return strokes


def render(strokes, pad=20, width=4):
    pts = [(p[0], p[1]) for s in strokes for p in s["points"]]
    x0, y0 = min(x for x, _ in pts) - pad, min(y for _, y in pts) - pad
    im = Image.new("L", (int(max(x for x, _ in pts) - x0 + pad), int(max(y for _, y in pts) - y0 + pad)), 255)
    d = ImageDraw.Draw(im)
    for s in strokes:
        d.line([(p[0] - x0, p[1] - y0) for p in s["points"]], fill=0, width=width, joint="curve")
    return im


# ---------------------------------------------------------------- Hauptprogramm
def main():
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 31
    rng = random.Random(seed)
    out_dir = HERE / "images_hard"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()

    rows, dropped, topics = [], [], {}
    i = 0
    for gen, n in KATALOG:
        for _ in range(n):
            topic, gt, toks, definition = gen(rng)
            i += 1
            if not gt_ok(gt, definition):
                dropped.append({"id": f"h{i:03d}", "topic": topic, "gt": gt})
                continue
            topics[topic] = topics.get(topic, 0) + 1
            mood = rng.uniform(2.6, 3.3)
            st = write_tokens(toks, 0, 60, mood, rng.randint(1, 10**6))
            cid = f"h{len(rows) + 1:03d}"
            render(st).save(out_dir / f"{cid}.png")
            rows.append({"id": cid, "src": "synth_hard",
                         "png": f"synth/images_hard/{cid}.png", "gt_latex": gt})

    (FW / "data" / "synth_hard.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"seed": seed, "formeln": len(rows), "verworfen": len(dropped),
                      "topics": topics, "drops": dropped}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
