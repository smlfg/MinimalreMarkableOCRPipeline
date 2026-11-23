"""Kohärenz-Schicht (ADR-007): Verwechslungspaare nur tauschen, wenn die Rechnung dadurch stimmt; nie still."""
import re

import sympy

from ocr.latex import parse, same

# (Muster, Ersatz). Muster mit "(" oder "\" sind Regex, sonst wörtlich.
CONFUSE = [(r"(?<=\d) ?(?=\d)", r"\\cdot "), (r"(?<=\d)\.(?=\d)", r"\\cdot "), (r"\\div", r"\\cdot"),
           (r"(?<=\d)-(?=\d)", r"\\cdot "),
           ("0", "a"), ("0", "o"), ("2", "z"), ("1", "l"), ("9", "q"), ("5", "s"), ("6", "b")]


def closed_truth(latex: str):
    """True/False für eine variablenfreie Gleichungskette, None wenn nicht prüfbar."""
    parts = [p for p in re.split(r"(?<![<>!\\])=", latex) if p.strip()]
    if len(parts) < 2:
        return None
    es = [parse(p) for p in parts]
    if any(e is None for e in es) or any(e.free_symbols for e in es):
        return None
    try:
        return all(sympy.simplify(es[0] - e) == 0 for e in es[1:])
    except Exception:
        return None


def coherent(latex: str, second: str | None = None):
    """-> (latex, repair|None). Tausch nur, wenn die Kette wahr wird oder (Buchstabe) die Zweitmeinung ihn stützt."""
    if closed_truth(latex) is not False:
        return latex, None
    for pat, rep in CONFUSE:
        rx = pat if pat.startswith(("(", "\\")) else re.escape(pat)
        for m in re.finditer(rx, latex):
            cand = latex[:m.start()] + m.expand(rep) + latex[m.end():]
            t = closed_truth(cand)
            if t is True or (t is None and second is not None and same(cand, second)):
                return cand, f"{latex} -> {cand}"
    return latex, None


def decimal_comma(latex: str) -> str:
    """Deutsches Dezimalkomma 0,5 -> 0.5; nicht in Klammern/Mengen, wo das Komma trennt."""
    out, depth = [], 0
    for i, ch in enumerate(latex):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if ch == "," and depth == 0 and 0 < i < len(latex) - 1 and latex[i - 1].isdigit() and latex[i + 1].isdigit():
            ch = "."
        out.append(ch)
    return "".join(out)
