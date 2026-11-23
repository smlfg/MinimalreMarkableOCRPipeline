"""LaTeX-Grundlagen für Pipeline und Metrik (eine Quelle): normalize, parse, equivalent."""
import re

import sympy
from latex2sympy2_extended import latex2sympy


def normalize(s: str) -> str:
    s = s.strip().strip("$")
    s = re.sub(r"\\(left|right|,|;|!|quad|qquad)\b|\\[,;! ]", "", s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    # LaTeX-Synonyme: identische Glyphe/Bedeutung
    s = re.sub(r"\\geq?(?![A-Za-z])", r"\\ge ", s); s = re.sub(r"\\leq?(?![A-Za-z])", r"\\le ", s); s = re.sub(r"\\neq?(?![A-Za-z])", r"\\ne ", s)
    s = re.sub(r"\^\{?(o|\\circ)\}?", r"^{\\circ}", s)
    s = re.sub(r"(?<![\\A-Za-z])(ln|log|sin|cos|tan|lim)(?![A-Za-z])", r"\\\1", s)
    s = re.sub(r"\\gt(?![A-Za-z])", ">", s); s = re.sub(r"\\lt(?![A-Za-z])", "<", s)
    s = re.sub(r"\\(no)?limits(?![A-Za-z])", "", s)
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


def equivalent_expr(a, b) -> bool:
    if isinstance(a, sympy.Equality) and isinstance(b, sympy.Equality):
        d = lambda x, y: sympy.simplify(x - y) == 0
        return (d(a.lhs, b.lhs) and d(a.rhs, b.rhs)) or (d(a.lhs, b.rhs) and d(a.rhs, b.lhs))
    if isinstance(a, sympy.Equality) != isinstance(b, sympy.Equality):
        return False
    return sympy.simplify(a - b) == 0



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
