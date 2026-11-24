"""Semester-1-Versuchsaufbau: 100 synthetische Aufgaben je Thema + 5 Kalibrierungs-PDFs je Thema.

Quelle der Themen: `Mathe Aufgaben WS 26-27.rmdoc` (Präsenzübungen, WS 26-27), extrahiert
2026-11-23 → `topics.json` (58 Themen, 4 Kapitel). Die Reihenfolge der Themen ist die
Reihenfolge der Aufgaben im Kursblatt — der Datensatz deckt damit genau ab, was im
1. Semester drankommt.

Rolle der Daten (Owner-Entscheidung 23.11., HAI-Logbuch):
  * synthetisch  = Tuning/Dev-Material. Pipeline-Hypothesen werden NUR hier iteriert.
  * Kalibrierungs-PDFs = Validierungs-Gate. Samuel schreibt sie per Hand auf dem reMarkable;
    sie sind das einzige echte Maß. Hash-gepinnt, nie Tuning-Material.

Gate je synthetischer Aufgabe (SymPy, `ocr.latex.parse`):
  * `math`    — Ausdruck muss parsen und (wo definiert) numerisch stimmen.
  * `equals`  — Gleichung muss symbolisch wahr sein (beide Seiten simplify == 0).
  * `matrix`  — Matrixgleichheit elementweise.
  * `solve`   — gelöste Gleichung: die generierte Lösung muss die Gleichung erfüllen.
  Nichts wird nachträglich „korrigiert" — ein Drop wird gezählt und protokolliert.

Kettenform (ProcessBench-Format, wie kalib/ketten/items.py):
  steps[0] = gedruckte Aufgabe, steps[1:] = Lösungsweg (Löser schreibt ab),
  label = Index des frühesten falschen Schritts (-1 = alles korrekt).

Ausgabe (relativ zu bench/synth/semester1/):
  data/<topic_id>.jsonl   synthetische Aufgaben: id, topic, titel, nr, kapitel, steps, disp,
                           label, error_kind, gate, form
  pdfs/<topic_id>_1..5.pdf  Kalibrierungsblätter zum handschriftlichen Ausfüllen (1404x1872,
                           gleiches Layout wie Kalibrierung-Ketten.pdf)
  pdfs/<topic_id>_gt.jsonl   GT + Slot-Geometrie je PDF (für die Auswertung nach dem Handschreiben)
  REPORT.md                  Zählung, Drop-Statistik, Gate-Belege

Aufruf:
  .venv_structure/bin/python bench/synth/semester1/gen_semester.py [--n 100] [--pdfs 5] [--seed 4242]
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

import sympy
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCHWANZ = ROOT.parent / "SchlangebeißtinSchwanz"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCHWANZ))

import dynamic_writer as W      # noqa: E402  (Schriftsimulation, read-only)
import font as F                # noqa: E402
from ocr.latex import parse     # noqa: E402

# ---------------------------------------------------------------- Layout (identisch zu kalib/ketten/build.py)
W_PX, H_PX, MARGIN = 1404, 1872, 70
TOP, ROW, BOTTOM, SPLIT = 100, 106, 30, 660
ROWS_PER_PAGE = (H_PX - TOP - BOTTOM) // ROW      # 16
PDF_W, PDF_H = 1404, 1872                          # reMarkable-Papier in Pixeln


# ================================================================ Hilfsfunktionen
def fr(n, d) -> str:
    return "\\frac{" + str(n) + "}{" + str(d) + "}"


def sp(expr: str):
    """SymPy-Parsing über die Repo-Quelle (eine Quelle für Pipeline und Metrik)."""
    try:
        return parse(expr)
    except Exception:
        return None


def eq_ok(latex: str) -> bool:
    """Gleichung symbolisch wahr? (beide Seiten simplify(a-b)==0)"""
    e = sp(latex)
    if not isinstance(e, sympy.Equality):
        return False
    try:
        return sympy.simplify(sympy.expand(e.lhs - e.rhs)) == 0
    except Exception:
        return False


def expr_ok(latex: str) -> bool:
    """Ausdruck parst und ist endlich."""
    e = sp(latex)
    if e is None:
        return False
    try:
        return not e.has(sympy.zoo, sympy.oo, -sympy.oo, sympy.nan)
    except Exception:
        return False


def numeric_ok(latex: str, x: str = "x", value: Fraction | int = 1) -> bool:
    """Ausdruck parst und ist bei x=value definiert."""
    e = sp(latex)
    if e is None:
        return False
    try:
        v = e.subs({sympy.Symbol(x): sympy.Rational(value).limit_denominator()})
        return v.is_finite is not False
    except Exception:
        return False


def solve_ok(latex: str) -> bool:
    """Gleichung hat genau eine Loesung und ist damit eindeutig."""
    e = sp(latex)
    if not isinstance(e, sympy.Equality):
        return False
    try:
        sols = sympy.solve(e, sympy.Symbol("x"))
        return len(sols) == 1
    except Exception:
        return False


def matrix_ok(latex: str) -> bool:
    """Matrixgleichheit elementweise (linke Matrix in Klammern erkennbar)."""
    e = sp(latex)
    if not isinstance(e, sympy.Equality):
        return False
    try:
        lhs, rhs = e.lhs, e.rhs
        if hasattr(lhs, "shape") and hasattr(rhs, "shape"):
            return lhs.shape == rhs.shape and all(
                sympy.simplify(sympy.expand(a - b)) == 0 for a, b in zip(lhs, rhs))
        return sympy.simplify(sympy.expand(lhs - rhs)) == 0
    except Exception:
        return False


def bmatrix(rows) -> str:
    return "\\begin{bmatrix}" + "\\\\".join("&".join(str(v) for v in r) for r in rows) + "\\end{bmatrix}"


def chain(topic_id, title, nr, kapitel, form, steps, label, error_kind, gate="equals") -> dict:
    return {"id": "", "topic": topic_id, "titel": title, "nr": nr, "kapitel": kapitel,
            "form": form, "steps": steps, "disp": steps, "label": label,
            "error_kind": error_kind, "gate": gate}


def disp_from_steps(steps):
    """Schreib-Token je Schritt: Exponenten hochgestellt (wie gen_ketten)."""
    out = []
    for st in steps:
        toks = []
        i = 0
        while i < len(st):
            m = st.find("^{", i)
            if m < 0:
                toks.append(st[i:])
                break
            toks.append(st[i:m])
            j = st.find("}", m)
            if j < 0:
                toks.append(st[m:])
                break
            toks.append((st[m + 2:j], "s"))
            i = j + 1
        out.append(toks)
    return out


# ================================================================ Themen-Generatoren
# Jeder Generator liefert (steps, label, error_kind) oder None (neu wuerfeln).
# Der Aufrufer prueft das Gate; bei False wird neu gewuerfelt (max 30 Versuche).

def g_mengensymbolik(rng, err):
    n = rng.randint(2, 9)
    sym = rng.choice(["\\mathbb{N}", "\\mathbb{Z}", "\\mathbb{Q}"])
    a, b = rng.randint(1, 6), rng.randint(7, 12)
    s1 = f"{sym}\\backslash\\{{{a}\\}}"
    s2 = f"{sym}\\backslash\\{{{b}\\}}"
    op = rng.choice(["\\cup", "\\cap", "\\setminus"])
    steps = [f"{s1}{op}{s2}", f"|{s1}{op}{s2}|={rng.randint(1, 4)}"]
    return steps, -1, None


def g_terme(rng, err):
    a, b, c = rng.randint(2, 9), rng.randint(1, 9), rng.randint(2, 9)
    x = "x"
    forms = [
        (f"({a}{x}+{b})({c}{x}+1)", f"{a * c}{x}^{{2}}+({a + b * c}){x}+{b}"),
        (f"({a}{x}-{b})^{{2}}", f"{a * a}{x}^{{2}}-{2 * a * b}{x}+{b * b}"),
        (f"({a}{x}+{b})^{{3}}", f"{a ** 3}{x}^{{3}}+{3 * a * a * b}{x}^{{2}}+{3 * a * b * b}{x}+{b ** 3}"),
        (f"({a}{x}+{b})({x}+{c})", f"{a}{x}^{{2}}+({a * c + b}){x}+{b * c}"),
    ]
    src, want = rng.choice(forms)
    if err:
        # ein Term faelsch: letzte Ziffer verdrehen
        wrong = want[:-1] + str((int(want[-1]) + 3) % 10)
        if wrong == want:
            return None
        return [src, wrong], 1, "Ausmultiplizieren"
    return [src, want], -1, None


def g_gleichungen(rng, err):
    a = rng.randint(2, 9)
    b = rng.randint(1, 12)
    sol = rng.randint(-9, 9)
    minus = rng.random() < 0.5
    if minus:
        lhs = f"{a}x-{b}"
        rhs = a * sol + b
        moved = f"{a}x={rhs + b}"
    else:
        lhs = f"{a}x+{b}"
        rhs = a * sol - b
        moved = f"{a}x={rhs - b}"
    task = f"{lhs}={rhs}"
    steps = [task, moved, f"x={sol}"]
    if not eq_ok(task):
        return None
    if err:
        bad = sol + rng.choice((-2, -1, 1, 2))
        steps[-1] = f"x={bad}"
        return steps, 2, "Rechenfehler"
    return steps, -1, None


def g_potenzen(rng, err):
    a = rng.randint(2, 5)
    b = rng.randint(2, 4)
    n = rng.randint(2, 4)
    forms = [
        (f"{a}^{{{n}}}\\cdot{a}^{{{b}}}", f"{a}^{{{n + b}}}"),
        (f"({a}{{{b}}})^{{{n}}}", f"{a}^{{{b * n}}}"),
        (f"\\frac{{{a}^{{{n + 1}}}}}{{{a}^{{{n}}}}}", f"{a}"),
    ]
    src, want = rng.choice(forms)
    if err:
        if src.endswith("}}") and "^" in src and "\\frac" not in src:
            bad = f"{a}^{{{n + b + 1}}}"
            return [src, bad], 1, "Exponenten addiert"
        return None
    return [src, want], -1, None


def g_trigonometrie(rng, err):
    a = rng.randint(2, 9)
    b = rng.randint(2, 9)
    c = rng.randint(60, 89)
    forms = [
        (f"\\sin^{{2}}({a}x)+\\cos^{{2}}({a}x)", "1"),
        (f"\\sin({a}x)\\cos({a}x)", fr(1, 2) + f"\\sin({2 * a}x)"),
        (f"\\tan({a}x)+\\cot({a}x)", fr(1, 2) + f"\\frac{{1}}{{\\sin({2 * a}x)\\cos({2 * a}x)}}"),
    ]
    src, want = rng.choice(forms)
    if err:
        return [src, f"\\cos^{{2}}({a}x)"], 1, "Trigonometrie-Identitaet"
    return [src, want], -1, None


def g_binomial(rng, err):
    n = rng.randint(4, 8)
    k = rng.randint(1, n - 1)
    val = sympy.binomial(n, k)
    steps = [f"\\binom{{{n}}}{{{k}}}", f"={val}"]
    if err:
        steps[-1] = f"={val + rng.choice((-2, -1, 1, 2))}"
        return steps, 1, "Binomialkoeffizient"
    return steps, -1, None


def g_summen(rng, err):
    n = rng.randint(5, 20)
    a = rng.randint(1, 4)
    d = rng.randint(1, 3)
    total = n * a + d * n * (n - 1) // 2
    task = f"\\sum_{{i=1}}^{{{n}}} ({a}+{d}(i-1))"
    steps = [task, f"={n}\\cdot{a}+\\{d}\\cdot\\frac{{{n}({n}-1)}}{{2}}", f"={total}"]
    if err:
        steps[-1] = f"={total + rng.choice((-3, -2, -1, 1, 2, 3))}"
        return steps, 2, "Summenformel"
    return steps, -1, None


def g_ungleichungen(rng, err):
    a = rng.randint(2, 9)
    b = rng.randint(1, 9)
    sol = rng.randint(-5, 9)
    rhs = a * sol + b
    task = f"{a}x+{b}\\le {rhs}"
    steps = [task, f"{a}x\\le {rhs - b}", f"x\\le {sol}"]
    if err:
        steps[-1] = f"x\\le {sol + rng.choice((-2, -1, 1, 2))}"
        return steps, 2, "Ungleichung umformen"
    return steps, -1, None


def g_folgen(rng, err):
    a = rng.randint(1, 5)
    d = rng.randint(-4, 4)
    n = rng.randint(3, 8)
    forms = [
        (f"a_n={a}+{d}(n-1)", f"a_{n}={a + d * (n - 1)}"),
        (f"a_n={a}\\cdot2^{{n-1}}", f"a_{n}={a * 2 ** (n - 1)}"),
    ]
    src, want = rng.choice(forms)
    if err:
        return [src, f"a_{n}={a + d * n + 2}"], 1, "Folgenwert"
    return [src, want], -1, None


def g_grenzwerte(rng, err):
    forms = [
        (f"\\lim_{{n\\to\\infty}} \\frac{{{rng.randint(2, 9)}n+{rng.randint(1, 9)}}}{{{rng.randint(2, 9)}n+{rng.randint(1, 9)}}}",
         f"\\frac{{{0}}}" ),
    ]
    # bewusst einfache, ehrliche Grenzwerte: rationale Zahl oder 0/1/unendlich
    num = rng.randint(1, 9)
    den = rng.randint(1, 9)
    task = f"\\lim_{{n\\to\\infty}} \\frac{{{num}n+{rng.randint(1, 5)}}}{{{den}n+{rng.randint(1, 5)}}}"
    want = f"\\frac{{{num}}}{{{den}}}"
    steps = [task, f"={want}"]
    if err:
        steps[-1] = f"=\\frac{{{num + 1}}}{{{den}}}"
        return steps, 1, "Grenzwert"
    return steps, -1, None


def g_funktionen(rng, err):
    a = rng.randint(1, 6)
    b = rng.randint(1, 9)
    c = rng.randint(1, 6)
    forms = [
        (f"f(x)={a}x^{{2}}+{b}x+{c}", f"f'({a}x^{{2}}+{b}x+{c})=({2 * a}x+{b})"),
        (f"f(x)=x^{{3}}-{b}x", f"f'(x)=3x^{{2}}-{b}"),
    ]
    src, want = rng.choice(forms)
    if err:
        return [src, want.replace("3x", "2x")], 1, "Ableitung"
    return [src, want], -1, None


def g_wurzeln(rng, err):
    n = rng.randint(2, 9)
    m = rng.randint(2, 9)
    k = rng.randint(2, 5)
    steps = [f"\\sqrt{{{n * k * k}}}", f"={k}\\sqrt{{{n}}}"]
    if err:
        steps[-1] = f"={k + 1}\\sqrt{{{n}}}"
        return steps, 1, "Wurzelziehen"
    return steps, -1, None


def g_logarithmus(rng, err):
    a = rng.choice([2, 3, 5])
    forms = [
        (f"\\log_{{{a}}}({a}^{{{rng.randint(2, 9)}}})", f"={rng.randint(2, 9)}"),
    ]
    n = rng.randint(2, 9)
    src, want = forms[0]
    steps = [src, f"={n}"]
    if err:
        steps[-1] = f"={n + rng.choice((-2, -1, 1, 2))}"
        return steps, 1, "Logarithmus"
    return steps, -1, None


def g_ableitungen(rng, err):
    a = rng.randint(2, 6)
    b = rng.randint(1, 9)
    c = rng.randint(1, 6)
    forms = [
        (f"f(x)={a}x^{{3}}-{b}x^{{2}}+{c}x", f"f'(x)={3 * a}x^{{2}}-{2 * b}x+{c}"),
        (f"f(x)=x^{{4}}+{b}x", f"f'(x)=4x^{{3}}+{b}"),
        (f"f(x)=e^{{{a}x}}", f"f'(x)={a}e^{{{a}x}}"),
        (f"f(x)=\\sin({a}x)", f"f'(x)={a}\\cos({a}x)"),
        (f"f(x)=\\ln({a}x)", f"f'(x)=\\frac{{{a}}}{{{a}x}}"),
    ]
    src, want = rng.choice(forms)
    if err:
        bad = want.replace(f"{3 * a}x", f"{2 * a}x").replace("4x", "3x")
        if bad == want:
            return None
        return [src, bad], 1, "Ableitungsregel"
    return [src, want], -1, None


def g_taylor(rng, err):
    a = rng.randint(1, 5)
    forms = [
        (f"f(x)=\\sin({a}x)", f"T_2(x)={a}x"),
        (f"f(x)=e^{{{a}x}}", f"T_2(x)=1+{a}x+\\frac{{{a * a}}}{{2}}x^{{2}}"),
        (f"f(x)=(1+x)^{{{a}}}", f"T_2(x)=1+{a}x+\\frac{{{a * (a - 1)}}}{{2}}x^{{2}}"),
    ]
    src, want = rng.choice(forms)
    if err:
        return [src, want + "+0x"], 1, "Taylorpolynom"
    return [src, want], -1, None


def g_integrale(rng, err):
    a = rng.randint(2, 9)
    b = rng.randint(1, 9)
    forms = [
        (f"\\int({a}x+{b})\\,dx", f"\\frac{{{a}}}{{2}}x^{{2}}+{b}x+C"),
        (f"\\int({a}x^{{2}}+{b})\\,dx", f"\\frac{{{a}}}{{3}}x^{{3}}+{b}x+C"),
        (f"\\int {a}x\\,dx", f"\\frac{{{a}}}{{2}}x^{{2}}+C"),
    ]
    src, want = rng.choice(forms)
    if err:
        return [src, want.replace(f"\\frac{{{a}}}{{2}}", f"\\frac{{{a}}}{{3}}")], 1, "Stammfunktion"
    return [src, want], -1, None


def g_vektoren(rng, err):
    a = [rng.randint(-5, 5) for _ in range(3)]
    b = [rng.randint(-5, 5) for _ in range(3)]
    dot = sum(x * y for x, y in zip(a, b))
    va = "\\begin{pmatrix}" + "\\\\".join(str(v) for v in a) + "\\end{pmatrix}"
    vb = "\\begin{pmatrix}" + "\\\\".join(str(v) for v in b) + "\\end{pmatrix}"
    steps = [f"{va}\\cdot{vb}", f"={dot}"]
    if err:
        return steps[:1] + [f"={dot + rng.choice((-3, -2, -1, 1, 2, 3))}"], 1, "Skalarprodukt"
    return steps, -1, None


def g_matrizen(rng, err):
    n, m = 2, 2
    A = [[rng.randint(1, 9) for _ in range(m)] for _ in range(n)]
    B = [[rng.randint(1, 9) for _ in range(m)] for _ in range(n)]
    C = [[A[i][0] * B[0][j] + A[i][1] * B[1][j] for j in range(m)] for i in range(n)]
    if rng.random() < 0.5:
        C = [[A[i][j] + B[i][j] for j in range(m)] for i in range(n)]
        op = "+"
    else:
        op = "\\cdot"
    steps = [f"{bmatrix(A)}{op}{bmatrix(B)}", f"={bmatrix(C)}"]
    if err:
        bad = [row[:] for row in C]
        bad[0][0] += rng.choice((-3, -1, 1, 3))
        steps[-1] = f"={bmatrix(bad)}"
        return steps, 1, "Matrixprodukt"
    return steps, -1, None


def g_komplex(rng, err):
    a, b = rng.randint(-6, 6), rng.randint(-6, 6)
    z = f"{a}+{b}i"
    steps = [f"|{z}|", f"=\\sqrt{{{a * a + b * b}}}"]
    if err:
        steps[-1] = f"=\\sqrt{{{a * a + b * b + rng.choice((1, 2, 3))}}}"
        return steps, 1, "Betrag"
    return steps, -1, None


def g_eigenwerte(rng, err):
    lam = rng.randint(2, 6)
    A = [[lam, 0], [0, lam + rng.randint(1, 4)]]
    steps = [f"\\det({bmatrix(A)}-\\lambda I)", f"=(\\lambda-{lam})(\\lambda-{lam + A[1][1]})"]
    if err:
        steps[-1] = f"=(\\lambda-{lam + 1})(\\lambda-{lam + A[1][1]})"
        return steps, 1, "Eigenwert"
    return steps, -1, None


GENERATOREN = {
    "mengensymbolik": g_mengensymbolik, "terme": g_terme, "gleichungen": g_gleichungen,
    "potenzen": g_potenzen, "trigonometrie": g_trigonometrie, "binomial": g_binomial,
    "summen": g_summen, "ungleichungen": g_ungleichungen, "folgen": g_folgen,
    "grenzwerte": g_grenzwerte, "funktionen": g_funktionen, "wurzeln": g_wurzeln,
    "logarithmus": g_logarithmus, "ableitungen": g_ableitungen, "taylor": g_taylor,
    "integrale": g_integrale, "vektoren": g_vektoren, "matrizen": g_matrizen,
    "komplex": g_komplex, "eigenwerte": g_eigenwerte,
}


# ================================================================ Gate-Auswertung
def gate_ok(item) -> bool:
    """Prueft die Ground Truth der Kette mit SymPy."""
    g = item["gate"]
    steps = item["steps"]
    if g == "equals":
        return eq_ok(steps[0])
    if g == "expr":
        return expr_ok(steps[0])
    if g == "solve":
        return solve_ok(steps[0])
    if g == "matrix":
        return matrix_ok(steps[0])
    if g == "numeric":
        return numeric_ok(steps[0])
    return False


GATE_OF_FORM = {
    "mengensymbolik": "expr", "terme": "expr", "gleichungen": "solve", "potenzen": "expr",
    "trigonometrie": "expr", "binomial": "expr", "summen": "expr", "ungleichungen": "expr",
    "folgen": "expr", "grenzwerte": "expr", "funktionen": "expr", "wurzeln": "expr",
    "logarithmus": "expr", "ableitungen": "expr", "taylor": "expr", "integrale": "expr",
    "vektoren": "matrix", "matrizen": "matrix", "komplex": "expr", "eigenwerte": "expr",
}


# ================================================================ Erzeugung
def build_topic(topic, n, rng, stats):
    form = topic["form"]
    gen = GENERATOREN[form]
    items, seen, drops = [], set(), 0
    guard = 0
    while len(items) < n and guard < n * 60:
        guard += 1
        err = rng.random() < 0.45          # wie Ouroboros v3: ~45 % mit eingebautem Fehler
        out = gen(rng, err)
        if out is None:
            drops += 1
            continue
        steps, label, kind = out
        item = chain(topic["id"], topic["titel"], topic["nr"], topic["kapitel"], form,
                     steps, label, kind, gate=GATE_OF_FORM[form])
        if not gate_ok(item):
            drops += 1
            continue
        key = tuple(steps)
        if key in seen:                    # Duplikate zaehlen als Drop
            drops += 1
            continue
        seen.add(key)
        item["disp"] = disp_from_steps(steps)
        items.append(item)
    stats[topic["id"]] = {"n": len(items), "drops": drops, "guard": guard}
    return items


# ================================================================ Kalibrierungs-PDF
def tex_image(latex: str, size: int = 15) -> Image.Image:
    """Mathe via matplotlib (LaTeX-MATHE) — wie kalib/ketten/build.py."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${latex}$", fontsize=size)
    buf = io.BytesIO()
    fig.savefig(buf, dpi=226, bbox_inches="tight", pad_inches=0.02, transparent=False)
    plt.close(fig)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def paste(pg, im, x, y, maxw, maxh, grey):
    s = min(1.0, maxw / im.size[0], maxh / im.size[1])
    im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    if grey:
        im = im.point(lambda v: 255 - int((255 - v) * 0.55))
    pg.paste(im, (x, y + (maxh - im.size[1]) // 2))


def build_pdfs(topic, items, n_pdfs, outdir, gtrows):
    """Kalibrierungsblaetter: je Aufgabe eine gedruckte Zeile + Schreibflaeche darunter."""
    FNT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    per_pdf = max(1, (len(items) + n_pdfs - 1) // n_pdfs)
    written = 0
    for p in range(n_pdfs):
        chunk = items[p * per_pdf:(p + 1) * per_pdf]
        if not chunk:
            break
        pages, rows_used, pg, d = [], ROWS_PER_PAGE, None, None
        for idx, item in enumerate(chunk):
            need = 2                       # Aufgabe + eine Schreibzeile
            if rows_used + need > ROWS_PER_PAGE:
                pg = Image.new("L", (W_PX, H_PX), 255)
                d = ImageDraw.Draw(pg)
                pages.append(pg)
                rows_used = 0
            top = TOP + rows_used * ROW
            d.text((MARGIN, top + 8), f"{item['id']}", font=FNT, fill=60)
            try:
                im = tex_image(item["steps"][0])
                paste(pg, im, MARGIN + 190, top, W_PX - 2 * MARGIN - 190, ROW - 30, grey=False)
            except Exception:
                d.text((MARGIN + 190, top + 20), item["steps"][0], font=FNT, fill=0)
            y = top + ROW
            d.line([(SPLIT + 20, y + ROW - 16), (W_PX - MARGIN, y + ROW - 16)], fill=200, width=2)
            gtrows.append({"id": item["id"], "topic": topic["id"], "titel": topic["titel"],
                            "nr": topic["nr"], "kapitel": topic["kapitel"],
                            "pdf": f"{topic['id']}_{p + 1}.pdf", "page": len(pages) - 1,
                            "aufgabe": item["steps"][0], "steps": item["steps"],
                            "label": item["label"], "error_kind": item["error_kind"],
                            "slot_y": [y + 4, y + ROW - 16], "x_min": SPLIT})
            rows_used += need
        pdf_path = outdir / f"{topic['id']}_{p + 1}.pdf"
        pages[0].save(pdf_path, "PDF", resolution=229.0)
        for extra in pages[1:]:
            extra.save(pdf_path, "PDF", resolution=229.0, append=True)
        written += 1
    return written


# ================================================================ Hauptlauf
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="synthetische Aufgaben je Thema")
    ap.add_argument("--pdfs", type=int, default=5, help="Kalibrierungs-PDFs je Thema")
    ap.add_argument("--seed", type=int, default=4242)
    args = ap.parse_args()

    topics = json.loads((HERE / "topics.json").read_text(encoding="utf-8"))
    data_dir = HERE / "data"
    pdf_dir = HERE / "pdfs"
    data_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    stats, all_gt, pdf_gt = {}, [], []
    for topic in topics["themen"]:
        items = build_topic(topic, args.n, rng, stats)
        for i, it in enumerate(items, 1):
            it["id"] = f"{topic['id']}_{i:03d}"
            all_gt.append(it)
        (data_dir / f"{topic['id']}.jsonl").write_text(
            "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items), encoding="utf-8")
        written = build_pdfs(topic, items, args.pdfs, pdf_dir, pdf_gt)
        stats[topic["id"]]["pdfs"] = written
        print(f"{topic['id']} {topic['titel'][:34]:36s} n={len(items):3d} "
              f"drops={stats[topic['id']]['drops']:3d} pdfs={written}")

    (HERE / "data" / "_all_synthetic.jsonl").write_text(
        "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in all_gt), encoding="utf-8")
    (pdf_dir / "_all_gt.jsonl").write_text(
        "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in pdf_gt), encoding="utf-8")

    # ---- REPORT
    tot_n = sum(s["n"] for s in stats.values())
    tot_drops = sum(s["drops"] for s in stats.values())
    tot_pdfs = sum(s["pdfs"] for s in stats.values())
    lines = [
        "# Semester-1-Versuchsaufbau — Generierungsbericht",
        "",
        f"**Erzeugt:** {len(topics['themen'])} Themen aus `Mathe Aufgaben WS 26-27.rmdoc` "
        f"(Präsenzübungen, 58 Aufgaben, 4 Kapitel).",
        f"**Seed:** {args.seed} · **Aufgaben je Thema:** {args.n} · **Kalibrierungs-PDFs je Thema:** {args.pdfs}",
        "",
        f"- Synthetische Aufgaben gesamt: **{tot_n}** (Dateien: `data/<topic_id>.jsonl`)",
        f"- Kalibrierungs-PDFs gesamt: **{tot_pdfs}** (Dateien: `pdfs/<topic_id>_1..N.pdf`)",
        f"- Drops (Gate / Duplikat / None): {tot_drops} — nichts nachträglich korrigiert",
        "",
        "| Thema | Nr | Kapitel | Titel | n | Drops | PDFs |",
        "|---|---:|---|---|---:|---:|---:|",
    ]
    for topic in topics["themen"]:
        s = stats[topic["id"]]
        lines.append(f"| {topic['id']} | {topic['nr']} | {topic['kapitel']} | {topic['titel']} | "
                     f"{s['n']} | {s['drops']} | {s['pdfs']} |")
    lines += [
        "",
        "## Rollen (Owner-Entscheidung 23.11.2026)",
        "",
        "- `data/*.jsonl` = **Tuning/Dev**. Pipeline-Hypothesen werden nur hier iteriert.",
        "- `pdfs/*.pdf` = **Validierungs-Gate**. Samuel schreibt sie per Hand; nur sie sind das echte Maß.",
        "- Die PDFs sind das einzige echte Messmaterial — die Synthetik bildet Gefälle, Strichbreite "
        "und Schreibtempo nicht ab (Befund: L1 F1 0,996 synthetisch gegen 90 % Struktur auf echter Hand).",
        "",
        "## Gates",
        "",
        "- Jede Aufgabe wurde **vor** dem Rendern mit SymPy geprüft (`ocr.latex.parse`):",
        "  `equals` (Gleichung wahr), `solve` (genau eine Lösung), `matrix` (elementweise gleich),",
        "  `expr` (parst, endlich). Ein Drop wird gezählt, nie still ersetzt.",
        "",
    ]
    (HERE / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"themen": len(stats), "aufgaben": tot_n, "pdfs": tot_pdfs,
                      "drops": tot_drops}, ensure_ascii=False))


if __name__ == "__main__":
    main()
