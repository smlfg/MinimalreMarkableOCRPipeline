"""LaTeX-Grundlagen für Pipeline und Metrik (eine Quelle): normalize, parse, equivalent."""
import re

import sympy
from latex2sympy2_extended import latex2sympy


def normalize(s: str) -> str:
    s = s.strip().strip("$")
    # TexTeller-Artefakte: Fontgrößen-Kommandos und innere $-Begrenzer sind semantisch leer.
    s = re.sub(r"\\(?:huge|Huge|LARGE|Large|large|normalsize|small|footnotesize|scriptsize|tiny)\b", "", s)
    s = s.replace("$", "")
    # einspaltige array-Umgebung -> Inhalt (TexTeller wrappt z. B. Integrale so); nur {c} ist
    # strukturgleich, mehrspaltige {cc} usw. (Matrizen) bleiben unangetastet. \s* toleriert
    # Zeilenumbrüche/Leerzeichen, die TexTeller um die Umgebung herum ausgibt.
    s = re.sub(r"\\begin\{array\}\s*\{c\}([\s\S]*?)\\end\{array\}", r"\1", s)
    s = re.sub(r"\\(left|right|,|;|!|quad|qquad)\b|\\[,;! ]", "", s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    # LaTeX-Synonyme: identische Glyphe/Bedeutung
    s = re.sub(r"\\geq?(?![A-Za-z])", r"\\ge ", s); s = re.sub(r"\\leq?(?![A-Za-z])", r"\\le ", s); s = re.sub(r"\\neq?(?![A-Za-z])", r"\\ne ", s)
    s = re.sub(r"\^\{?(o|\\circ)\}?", r"^{\\circ}", s)
    s = re.sub(r"(?<![\\A-Za-z])(ln|log|sin|cos|tan|lim)(?![A-Za-z])", r"\\\1", s)
    s = re.sub(r"\\gt(?![A-Za-z])", ">", s); s = re.sub(r"\\lt(?![A-Za-z])", "<", s)
    s = re.sub(r"\\(no)?limits(?![A-Za-z])", "", s)
    # TexTeller-Artefakte: \mbox{...}, \text{...}, \mathrm{...} -> Inhalt (eine Ebene, keine
    # Verschachtelung). Funktionsnamen (sin, cos, …) wurden oben bereits mit Backslash versehen.
    for cmd in ("mbox", "text", "mathrm"):
        s = re.sub(r"\\" + cmd + r"\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\{?((?:'|\\prime)+)\}?", lambda m: "'" * (m.group(1).count("'") + m.group(1).count("prime")), s)  # f^{'} == f'
    s = re.sub(r"\s+", "", s)
    # Einzeltoken-Index/Exponent: x^2 == x^{2}, a_\alpha == a_{\alpha} (gleiche Darstellung)
    s = re.sub(r"([_^])(\\[A-Za-z]+|[A-Za-z0-9])", r"\1{\2}", s)
    return s


def parse(latex: str):
    try:
        return latex2sympy(latex)
    except Exception:
        return None


def _is_zero(a, b) -> bool:
    """a == b symbolisch: Differenz ist 0 (Skalar) bzw. die Nullmatrix (Matrix).
    sympy.simplify(Matrix - Matrix) == 0 ist immer False, weil die Nullmatrix
    kein Skalar ist — deshalb wird hier is_zero_matrix geprueft."""
    d = sympy.simplify(a - b)
    if isinstance(d, sympy.MatrixBase):
        return bool(d.is_zero_matrix)
    return d == 0


def equivalent_expr(a, b) -> bool:
    if isinstance(a, sympy.Equality) and isinstance(b, sympy.Equality):
        return ((_is_zero(a.lhs, b.lhs) and _is_zero(a.rhs, b.rhs))
                or (_is_zero(a.lhs, b.rhs) and _is_zero(a.rhs, b.lhs)))
    if isinstance(a, sympy.Equality) != isinstance(b, sympy.Equality):
        return False
    return _is_zero(a, b)



def same(a: str, b: str) -> bool:
    """Zwei LaTeX-Strings gleich: identisch nach normalize oder SymPy-äquivalent."""
    if normalize(a) == normalize(b):
        return True
    ea, eb = parse(a), parse(b)
    if ea is None or eb is None:
        return False
    try:
        return bool(equivalent_expr(ea, eb))
    except Exception:
        return False
