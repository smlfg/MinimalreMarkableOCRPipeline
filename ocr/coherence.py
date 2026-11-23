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


def tt_render_artifacts(latex: str) -> str:
    """TexTeller-CPU: mathtext render quirks (\\mbox integral glyph, \\tfrac alias)."""
    s = re.sub(r"\\mbox\{\\Large\$\\int\$\}", r"\\int", latex)
    s = s.replace(r"\tfrac", r"\frac")
    s = re.sub(r"\\text\{(sin|cos|tan|log|ln|det|lim)\}", r"\\\1", s)
    if "\\mbox{" not in s:
        s = re.sub(r"\\operatorname\{det\}", r"\\det", s)
    return s


def texttt_artifacts(latex: str) -> str:
    """TexTeller-CPU: \\backslash\\texttt{…} statt \\begin/\\end, \\texttt{token}-Hüllen, \\&."""
    if not re.search(
        r"\\backslash\\(?:text|math)tt|\\(?:text|math)tt\{|\\backslash\s+\\|\\backslash\s+begin|@"
        r"|\\mbox\{\\Large\$\\int\$\}|\\,\{=|\}\{=",
        latex,
    ):
        if "\\&" not in latex and r"\backslash\backslash" not in latex and not re.search(r"\\\{", latex):
            return latex
    s = latex
    s = re.sub(r"\\backslash\s*\\(?:text|math)tt\{begin\}", r"\\begin", s)
    s = re.sub(r"\\backslash\s*\\(?:text|math)tt\{end\}", r"\\end", s)
    s = re.sub(r"\\backslash\\(?:text|math)tt\{det\}", r"\\det", s)
    s = re.sub(r"\\(?:text|math)tt\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\\{", "{", s)
    s = re.sub(r"\\\}", "}", s)
    s = s.replace(r"\backslash\backslash", r"\\")
    s = re.sub(r"\\backslash\s+\\backslash", r"\\\\", s)
    s = re.sub(r"\\backslash\s+begin\{", r"\\begin{", s)
    s = re.sub(r"\\backslash\s+end\{", r"\\end{", s)
    s = re.sub(r"\\\\\s+", r"\\\\", s)
    s = re.sub(r"\}\{=([^}]*)\}", r"}=\1", s)
    s = s.replace("@", "&")
    s = s.replace(r"\&", "&")
    return s


def integral_eq_artifact(latex: str) -> str:
    """TexTeller: \\,{=6} statt =6 nach Integrand."""
    return re.sub(r"\\,\{=([^}]*)\}", r"=\1", latex)


def array_single_cell_artifact(latex: str) -> str:
    """Unwrap \\begin{array}{c}… single formula …\\end{array} (TT line wrapper only)."""
    m = re.fullmatch(
        r"\\begin\{array\}\s*(?:\n\s*)?\{[lcr|]+\}\s*(?:\\vspace\{[^}]*\})?\s*(.+?)\s*\\end\{array\}\s*",
        latex.strip(),
        flags=re.DOTALL,
    )
    if not m:
        return latex
    inner = m.group(1).strip()
    if "\\\\" in inner or "&" in inner:
        return latex
    if re.search(r"\\begin\{", inner):
        return latex
    return inner


def tt_postprocess(latex: str) -> str:
    """Product pipe before coherent(): decimal + render/texttt/integral artifacts."""
    s = tt_render_artifacts(texttt_artifacts(decimal_comma(latex)))
    s = array_single_cell_artifact(s)
    return integral_eq_artifact(s)


def variants(second: str) -> list[str]:
    """Artefakt-Interpretationen einer Zweitmeinung. GLM-Artefakte: Leerzeichen zwischen
    Ziffern (zerrissene Zahl '2 5' oder verschluckter Operator '3 3') und Punkt/Gedankenstrich
    statt Malpunkt ('3. 1 0'). Im deutschen Schulkontext ist ein Punkt zwischen Ziffern primaer
    ein Malpunkt (Dezimalzeichen ist das Komma), deshalb als Variante, nie als Ersatz."""
    second = tt_postprocess(second)
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


_POWER_DIGIT = re.compile(r"(?<![0-9{\\^_])(\d)(\d)(?!\d)")


def _power_digit_cands(latex: str):
    """Fusions-Artefakt: zwei Ziffern ohne Klammern evtl. als b^{e} lesen (nur mit GLM-Korroboration)."""
    seen = set()
    for m in _POWER_DIGIT.finditer(latex):
        cand = latex[:m.start()] + f"{m.group(1)}^{{{m.group(2)}}}" + latex[m.end():]
        if cand != latex and cand not in seen:
            seen.add(cand)
            yield cand


def coherent(latex: str, second: str | None = None):
    """-> (latex, repair|None, trusted). trusted ist OCR-Vertrauen, nicht mathematische
    Korrektheit (Issue #1): ohne Zweitmeinung immer False; bei Übereinstimmung ohne Reparatur
    True; jede Reparatur (auch GLM-korroboriert) False. closed_truth fließt nicht in trusted."""
    if second is None:
        return latex, None, False
    if agree(latex, second):
        return latex, None, True
    for pat, rep in CONFUSE:
        rx = pat if pat.startswith(("(", "\\")) else re.escape(pat)
        for m in re.finditer(rx, latex):
            cand = latex[:m.start()] + m.expand(rep) + latex[m.end():]
            if closed_truth(cand) is True and closed_truth(latex) is False:
                return cand, f"{latex} -> {cand}", False
            if agree(cand, second):
                return cand, f"{latex} -> {cand}", False
    for cand in _power_digit_cands(latex):
        if agree(cand, second):
            return cand, f"{latex} -> {cand}", False
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
