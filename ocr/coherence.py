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


def variants(second: str) -> list[str]:
    """Artefakt-Interpretationen einer Zweitmeinung. GLM-Artefakte: Leerzeichen zwischen
    Ziffern (zerrissene Zahl '2 5' oder verschluckter Operator '3 3') und Punkt/Gedankenstrich
    statt Malpunkt ('3. 1 0'). Im deutschen Schulkontext ist ein Punkt zwischen Ziffern primaer
    ein Malpunkt (Dezimalzeichen ist das Komma), deshalb als Variante, nie als Ersatz."""
    num = re.sub(r"(?<=\d) (?=\d)", "", second)
    mul = re.sub(r"(?<=\d) (?=\d)", r"\\cdot ", second)
    dot = re.sub(r"(?<=\d)[.\-] ?(?=\d)", r"\\cdot ", second)
    both = re.sub(r"(?<=\d) (?=\d)", "", dot)
    vs = [second]
    for v in (num, mul, dot, both):
        if v != second and v not in vs:
            vs.append(v)
    return vs


def agree(latex: str, second: str) -> bool:
    """True, wenn die Lesart semantisch mit der Zweitmeinung (inkl. Artefakt-Interpretationen) übereinstimmt."""
    return any(same(latex, v) for v in variants(second))


def coherent(latex: str, second: str | None = None):
    """-> (latex, repair|None, trusted). trusted: Zweitmeinung stützt die Lesart (ggf. nach
    Artefakt-Normalisierung) oder korroboriert einen CONFUSE-Tausch. Ein Tausch OHNE Stütze
    (nur closed_truth) bleibt wie bisher unsicher (ADR-007: nie still raten)."""
    if second is None:
        return latex, None, closed_truth(latex) is not False
    if agree(latex, second):
        return latex, None, True
    for pat, rep in CONFUSE:
        rx = pat if pat.startswith(("(", "\\")) else re.escape(pat)
        for m in re.finditer(rx, latex):
            cand = latex[:m.start()] + m.expand(rep) + latex[m.end():]
            if closed_truth(cand) is True and closed_truth(latex) is False:
                return cand, f"{latex} -> {cand}", False
            if agree(cand, second):
                return cand, f"{latex} -> {cand}", True
    return latex, None, False


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
