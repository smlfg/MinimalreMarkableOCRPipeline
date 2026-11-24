"""Ouroboros v3 — Kampagne: 1000 Ketten von L1 (linear) bis L6 (Matrixmultiplikation).

Erzeugt EINMAL deterministisch (Seed) und komplett: Gates vor dem Rendern, GT nie gebogen.
Die Messung laeuft batchweise (run_batches.py, Batches à 50, Sprachausgabe je Batch).

Stufen:
  L1 200  linear einfach          (gen_ketten.g_linear)          -> chain_bench-Tier
  L2 200  Klammer/beidseitig/2-fach verschachtelt                -> chain_bench-Tier
  L3 150  quadratisch (+-k, pq)                                  -> chain_bench-Tier
  L4 150  Bruchgleichung/Potenz/Zahlterm/Bruch-Arithmetik         -> chain_bench-Tier
  L5 150  schwere Formeln (Integral/Summe/Algebra/Wurzel/Pi)      -> Formel-Tier (gen_hard)
  L6 150  Matrixmultiplikation (2x2·2x2, 2x2·2x1, s·A, A^2, 2-Zeiler) -> Formel-Tier (neu)

Gates: L1-L4 gegen chain_bench.judge (pred == label), L5 gegen SymPy-Wahrheit
(gen_hard.gt_ok), L6 gegen SymPy-Matrixverifikation (lhs.doit() == rhs, elementweise).
Drops werden gezaehlt und protokolliert.

Glyphen: hohe Klammern (Matrizen) und Sigma v2 werden LOKAL in den importierten
Glyph-Spiegel von SchlangebeißtinSchwanz geschrieben — nur im RAM, das Repo bleibt unangetastet.
Sigma v1 (v2-Fund: als z/3/s gelesen) bleibt Standard; 'glyph_sigma' ist die Stellschraube.

Stellschrauben (plan.json): seed, level-Mix, err_rate, schrift (scale_min/max,
sup_raise, sup_scale), glyph_sigma.

Aufruf: .venv_structure/bin/python bench/synth/campaign_v3/gen_campaign.py [seed=314] [glyph_sigma=v1]
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import sympy
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCHWANZ = ROOT.parent / "SchlangebeißtinSchwanz"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(SCHWANZ))
sys.path.insert(0, str(ROOT / "bench" / "synth"))          # gen_ketten (L1-L4-Templates)
sys.path.insert(0, str(ROOT / "bench" / "formula_flywheel" / "synth"))  # gen_hard (L5)

from chain_bench import judge  # noqa: E402
from ocr.latex import parse    # noqa: E402
import dynamic_writer as W     # noqa: E402
import font as F                # noqa: E402
import gen_ketten as K          # noqa: E402  (auch: Seiten-Geometrie + render)
import gen_hard as H            # noqa: E402  (registriert ∫ Σ π lokal im RAM)

# ---------------------------------------------------------------- Stellschrauben
PLAN = {
    "seed": int(sys.argv[1]) if len(sys.argv) > 1 else 314,
    "batch_size": 50,
    "levels": {"L1": 200, "L2": 200, "L3": 150, "L4": 150, "L5": 150, "L6": 150},
    "err_rate": 0.45,
    "schrift": {"scale_min": 2.6, "scale_max": 3.3, "sup_raise": 8.5, "sup_scale": 0.55},
    "glyph_sigma": sys.argv[2] if len(sys.argv) > 2 else "v1",
}

SIGMA_V2 = (11.0, [
    [[1.0, 16.0], [10.0, 16.0]],
    [[10.0, 16.0], [2.2, 8.5], [9.6, 0.5]],
    [[9.6, 0.5], [1.0, 0.5]],
])
if PLAN["glyph_sigma"] == "v2":
    F.GLYPHS["Σ"] = SIGMA_V2

F.GLYPHS["︵"] = (7.5, [[[6.0, 22.0], [4.4, 19.0], [3.4, 14.0], [3.0, 9.0],
                        [3.0, 4.0], [4.2, -3.0], [6.0, -8.0]]])   # hohe Klammer links
F.GLYPHS["︶"] = (7.5, [[[1.5, 22.0], [3.1, 19.0], [4.1, 14.0], [4.5, 9.0],
                        [4.5, 4.0], [3.3, -3.0], [1.5, -8.0]]])   # hohe Klammer rechts

# ---------------------------------------------------------------- Schriftsimulation (Knobs)
def write_tokens(tokens, x0, baseline, scale, seed):
    """str = Basislinie, ('t','s') = hoch-, ('t','t') = tiefgestellt. sup-Parameter aus PLAN."""
    su, sc = PLAN["schrift"]["sup_raise"], PLAN["schrift"]["sup_scale"]
    strokes, pen, sd = [], x0, seed
    for tok in tokens:
        text, mode = (tok, "b") if isinstance(tok, str) else tok
        if mode == "s":
            strokes += W.synthesize_handwriting_line(text, pen, baseline - scale * su,
                                                     scale=scale * sc, style="student", seed=sd)
            pen += W.measure_text_width(text, scale * sc) + scale * 1.1
        elif mode == "t":
            strokes += W.synthesize_handwriting_line(text, pen, baseline + scale * 3.0,
                                                     scale=scale * sc, style="student", seed=sd)
            pen += W.measure_text_width(text, scale * sc) + scale * 1.1
        else:
            strokes += W.synthesize_handwriting_line(text, pen, baseline, scale=scale,
                                                     style="student", seed=sd)
            pen += W.measure_text_width(text, scale) + scale * 1.1
        sd += 17
    return strokes


def write_matrix(cells, x0, center, scale, seed):
    """Zahlen-Matrix mit hohen Klammern; Zeile 0 oben. -> (strokes, end_x)."""
    n, m = len(cells), len(cells[0])
    rh = scale * 16
    strokes = W.synthesize_handwriting_line("︵", x0, center, scale=scale, style="student", seed=seed)
    x = x0 + W.measure_text_width("︵", scale) + scale * 1.0
    colw = []
    for c in range(m):
        w = max(W.measure_text_width(str(cells[r][c]), scale) for r in range(n))
        colw.append(w + scale * 2.2)
        for r in range(n):
            base = center + (r - (n - 1) / 2) * rh
            cell = str(cells[r][c])
            strokes += W.synthesize_handwriting_line(cell, x + (colw[-1] - scale * 2.2 -
                              W.measure_text_width(cell, scale)) / 2, base,
                              scale=scale, style="student", seed=seed + 31 * r + c)
        x += colw[c]
    x += scale * 1.0
    strokes += W.synthesize_handwriting_line("︶", x, center, scale=scale, style="student", seed=seed + 7)
    return strokes, x + W.measure_text_width("︶", scale)


def write_parts(parts, x0, center, scale, seed):
    """parts: ('mat', cells) | ('txt', tokens). -> (strokes, end_x)."""
    strokes, pen, sd = [], x0, seed
    for kind, val in parts:
        if kind == "mat":
            st, pen = write_matrix(val, pen, center, scale, sd)
            strokes += st
        else:
            st = write_tokens(val, pen, center, scale, sd)
            strokes += st
            xs = [p[0] for s in st for p in s["points"]]
            pen = max(xs) + scale * 1.2 if xs else pen
        sd += 23
    return strokes, pen


# ---------------------------------------------------------------- L6: Matrixmultiplikation
def bmat(rows):
    return "\\begin{bmatrix}" + "\\\\".join("&".join(str(v) for v in r) for r in rows) + "\\end{bmatrix}"


def matrix_ok(gt):
    try:
        e = parse(gt)
    except Exception:
        return False
    if not isinstance(e, sympy.Equality):
        return False
    try:
        lhs, rhs = e.lhs.doit(), e.rhs.doit()
        if hasattr(lhs, "shape") and hasattr(rhs, "shape"):
            return lhs.shape == rhs.shape and all(
                sympy.simplify(sympy.expand(a - b)) == 0 for a, b in zip(lhs, rhs))
        return sympy.simplify(sympy.expand(e.lhs - e.rhs)) == 0
    except Exception:
        return False


def m_mat_mm(rng):
    A = [[rng.randint(1, 9) for _ in range(2)] for _ in range(2)]
    B = [[rng.randint(0, 9) for _ in range(2)] for _ in range(2)]
    C = [[A[i][0] * B[0][j] + A[i][1] * B[1][j] for j in range(2)] for i in range(2)]
    gt = bmat(A) + "\\cdot" + bmat(B) + "=" + bmat(C)
    parts = [("mat", A), ("txt", ["·"]), ("mat", B), ("txt", ["="]), ("mat", C)]
    return ("matrix_mm", gt, parts, False)


def m_mat_mv(rng):
    A = [[rng.randint(1, 9) for _ in range(2)] for _ in range(2)]
    v = [[rng.randint(1, 9)], [rng.randint(1, 9)]]
    w = [[A[0][0] * v[0][0] + A[0][1] * v[1][0]], [A[1][0] * v[0][0] + A[1][1] * v[1][0]]]
    gt = bmat(A) + "\\cdot" + bmat(v) + "=" + bmat(w)
    parts = [("mat", A), ("txt", ["·"]), ("mat", v), ("txt", ["="]), ("mat", w)]
    return ("matrix_mv", gt, parts, False)


def m_mat_sm(rng):
    s = rng.randint(2, 9)
    A = [[rng.randint(1, 9) for _ in range(2)] for _ in range(2)]
    B = [[s * A[r][c] for c in range(2)] for r in range(2)]
    gt = str(s) + "\\cdot" + bmat(A) + "=" + bmat(B)
    parts = [("txt", [f"{s}·"]), ("mat", A), ("txt", ["="]), ("mat", B)]
    return ("matrix_sm", gt, parts, False)


def m_mat_pow(rng):
    A = [[rng.randint(1, 9) for _ in range(2)] for _ in range(2)]
    P = [[A[i][0] * A[0][j] + A[i][1] * A[1][j] for j in range(2)] for i in range(2)]
    gt = bmat(A) + "^{2}=" + bmat(P)
    parts = [("mat", A), ("txt", [("2", "s")]), ("txt", ["="]), ("mat", P)]
    return ("matrix_pow", gt, parts, False)


def m_mat_two(rng):
    """2-Zeilen-Kette: A·B=C, danach C·v=w."""
    A = [[rng.randint(1, 9) for _ in range(2)] for _ in range(2)]
    B = [[rng.randint(1, 9) for _ in range(2)] for _ in range(2)]
    C = [[A[i][0] * B[0][j] + A[i][1] * B[1][j] for j in range(2)] for i in range(2)]
    v = [[rng.randint(1, 9)], [rng.randint(1, 9)]]
    w = [[C[0][0] * v[0][0] + C[0][1] * v[1][0]], [C[1][0] * v[0][0] + C[1][1] * v[1][0]]]
    l1 = ("matrix_2step", bmat(A) + "\\cdot" + bmat(B) + "=" + bmat(C),
          [("mat", A), ("txt", ["·"]), ("mat", B), ("txt", ["="]), ("mat", C)], False)
    l2 = ("matrix_2step", bmat(C) + "\\cdot" + bmat(v) + "=" + bmat(w),
          [("mat", C), ("txt", ["·"]), ("mat", v), ("txt", ["="]), ("mat", w)], False)
    return [l1, l2]


L5_PLAN = [(H.m_integral_unb, 20), (H.m_integral_lin, 18), (H.m_integral_best, 12),
           (H.m_sum_gauss, 12), (H.m_sum_quad, 10), (H.m_sum_gerad, 8), (H.m_sum_geo, 10),
           (H.m_alg_binom2, 8), (H.m_alg_binom3, 7), (H.m_alg_diff, 5), (H.m_alg_potenz, 5),
           (H.m_wurzel_prod, 6), (H.m_wurzel_ident, 4), (H.m_wurzel_zahl, 5),
           (H.m_bruch_ident, 5), (H.m_bruch_gleich, 5),
           (H.m_pi_flaeche, 5), (H.m_pi_umfang, 5)]

L6_PLAN = [(m_mat_mm, 50), (m_mat_mv, 40), (m_mat_sm, 30), (m_mat_pow, 15), (m_mat_two, 15)]


# ---------------------------------------------------------------- Erzeugen
def main():
    rng = random.Random(PLAN["seed"])
    for sub in ("png/slots", "png/lines", "pages"):
        (HERE / sub).mkdir(parents=True, exist_ok=True)
        for old in (HERE / sub).rglob("*.png"):
            old.unlink()

    chains, rows, formulas, drops = [], [], [], []
    t0 = time.time()

    def mood():
        return rng.uniform(PLAN["schrift"]["scale_min"], PLAN["schrift"]["scale_max"])

    # ---- L1-L4: Ketten-Tier (Seiten-Layout wie Kalibrierungsblatt, Gate: judge)
    ketten_gens = {
        "L1": [K.g_linear],
        "L2": [K.g_klammer, K.g_beidseitig, K.g_klammer2],
        "L3": [K.g_quad, K.g_quad_pq],
        "L4": [K.g_bruchgl, K.g_potenz, K.g_zahl, K.g_bruch_add, K.g_bruch_mul],
    }
    pages, cur, m = [], None, 0.0
    for level in ("L1", "L2", "L3", "L4"):
        gens = ketten_gens[level]
        got = 0
        while got < PLAN["levels"][level]:
            g = gens[got % len(gens)]
            cand = g(rng, rng.random() < PLAN["err_rate"])
            if cand is None:
                drops.append({"level": level, "grund": "template None"})
                continue
            pred, _, _ = judge(cand["steps"])
            if pred != cand["label"]:
                drops.append({"level": level, "topic": cand["topic"],
                              "label": cand["label"], "pred": pred})
                continue
            if cur is None or cur["used"] + len(cand["steps"]) > K.ROWS_PER_PAGE:
                cur = {"strokes": [], "used": 0}
                pages.append(cur)
                m = mood()
            got += 1
            cid = f"C{len(chains) + 1:03d}"
            page_i, row0 = len(pages) - 1, K.TOP + cur["used"] * K.ROW
            cur["strokes"] += write_tokens(cand["disp"][0], K.MARGIN + 6, row0 + 78, m, rng.randint(1, 10**6))
            slots = []
            for k in range(1, len(cand["steps"])):
                y = row0 + k * K.ROW
                st = write_tokens(cand["disp"][k], K.SPLIT + 30, y + 78,
                                  m * rng.uniform(0.94, 1.06), rng.randint(1, 10**6))
                cur["strokes"] += st
                slots.append({"step": k, "page": page_i, "slot_y": [y + 4, y + K.ROW - 16],
                             "x_min": K.SPLIT})
                K.render(st).save(HERE / "png" / "slots" / f"{cid}_s{k}.png")
                rows.append({"id": f"{cid}_s{k}", "src": "synth",
                             "png": f"png/slots/{cid}_s{k}.png",
                             "gt_latex": cand["steps"][k], "chain_id": cid, "step": k})
            cur["used"] += len(cand["steps"])
            chains.append({"id": cid, "level": level, "topic": cand["topic"],
                          "steps": cand["steps"], "label": cand["label"],
                          "error_kind": cand["error_kind"], "slots": slots})

    # ---- L5: schwere Formeln (Gate: SymPy-Wahrheit aus gen_hard)
    for gen, n in L5_PLAN:
        for _ in range(n):
            topic, gt, toks, definition = gen(rng)
            if not H.gt_ok(gt, definition):
                drops.append({"level": "L5", "topic": topic, "gt": gt[:70]})
                continue
            hid = f"H{len(formulas) + 1:03d}"
            st = write_tokens(toks, 0, 60, mood(), rng.randint(1, 10**6))
            K.render(st).save(HERE / "png" / "lines" / f"{hid}.png")
            formulas.append({"id": hid, "level": "L5", "topic": topic, "gt_latex": gt,
                             "png": f"png/lines/{hid}.png"})

    # ---- L6: Matrixmultiplikation (Gate: SymPy-Matrixverifikation)
    for gen, n in L6_PLAN:
        for _ in range(n):
            out = gen(rng)
            if not isinstance(out, list):
                out = [out]
            ok = [matrix_ok(o[1]) or o[3] for o in out]   # Definitionen ohne Wahrheits-Gate
            if not all(ok):
                drops.append({"level": "L6", "topic": out[0][0], "gt": out[0][1][:70]})
                continue
            chain_id = f"H{len(formulas) + 1:03d}"
            for step, (topic, gt, parts, definition) in enumerate(out):
                hid = f"H{len(formulas) + 1:03d}"
                st, _ = write_parts(parts, 0, 60, mood(), rng.randint(1, 10**6))
                K.render(st).save(HERE / "png" / "lines" / f"{hid}.png")
                formulas.append({"id": hid, "level": "L6", "topic": topic, "gt_latex": gt,
                                 "png": f"png/lines/{hid}.png",
                                 "chain_id": chain_id, "step": step})

    # ---- Seiten rendern
    for i, pg in enumerate(pages):
        im = Image.new("L", (K.PAGE_W, K.PAGE_H), 255)
        d = ImageDraw.Draw(im)
        for s in pg["strokes"]:
            d.line([(p[0], p[1]) for p in s["points"]], fill=0, width=4, joint="curve")
        im.save(HERE / "pages" / f"page_{i:03d}.png")

    # ---- alles wegschreiben
    def dump(name, list_):
        (HERE / name).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in list_), encoding="utf-8")
    dump("all_gt.jsonl", chains)
    dump("all_rows.jsonl", rows)
    dump("formulas.jsonl", formulas)
    PLAN["erzeugt"] = {"ketten": len(chains), "slots": len(rows),
                       "formeln": len(formulas), "seiten": len(pages),
                       "drops": len(drops), "dauer_s": round(time.time() - t0)}
    (HERE / "plan.json").write_text(json.dumps(PLAN, ensure_ascii=False, indent=1), encoding="utf-8")
    levels = {}
    for c in chains:
        levels[c["level"]] = levels.get(c["level"], 0) + 1
    for f in formulas:
        levels[f["level"]] = levels.get(f["level"], 0) + 1
    print(json.dumps({"plan": PLAN["erzeugt"], "levels": levels,
                      "drops": drops[:20], "n_drops": len(drops)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
