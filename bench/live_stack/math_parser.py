"""Deterministischer LaTeX-Normalisierer & multivariater Polynom-/Term-Parser (reines Python + `Fraction`).

Ersetzt das enge 1-Variablen-Grad-1-Limit durch:
- Rekursive LaTeX-Normalisierung (`\\frac{a}{b}`, `\\left`/`\\right`, `\\cdot`, `\\sqrt`, Unicode-Potenzen)
- Exakte multivariate rationale Polynom-Arithmetik (`dict[Monom, Fraction]`) für beliebige Grade & Variablen
- Sicheren AST-Funktions-Evaluator (`sqrt`, `sin`, `cos`, `tan`, `!`) als exakter numerischer Fallback
- Klassifikation unvollständiger Zeilen (`LHS =`, `= RHS`, reine Terme, Fragen, Freitext)
"""
from __future__ import annotations

import ast
import math
import re
from fractions import Fraction
from typing import Any

_SUPERSCRIPTS = str.maketrans({
    "⁰": "^0", "¹": "^1", "²": "^2", "³": "^3", "⁴": "^4",
    "⁵": "^5", "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9",
})
_OP_TRANS = str.maketrans({
    "−": "-", "–": "-", "—": "-",
    "·": "*", "⋅": "*", "∙": "*", "×": "*", "✕": "*",
    "÷": "/", ":": "/",
})

_TEX_FUNCS = ("sqrt", "sin", "cos", "tan", "log", "ln", "abs")
_ALLOWED_WORDS = frozenset((*_TEX_FUNCS, "pi", "sum", "or", "oder", "and", "und"))
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+")
_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|\.\d+|[a-zA-Z]+|[+\-*/^()!]|=")
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$|^\.\d+$")
_QUESTION_WORDS = ("wie", "how", "warum", "why", "hilfe", "help", "was", "welch")
_SUM_RE = re.compile(r"sum\s*[_^]|\\sum|\bsum\b|Σ|∑", re.IGNORECASE)

Monom = tuple[tuple[str, int], ...]
Poly = dict[Monom, Fraction]


def _replace_latex_frac(s: str) -> str:
    """Ersetzt verschachtelte `\\frac{num}{den}` (auch ohne Backslash) rekursiv durch `((num)/(den))`."""
    pattern = re.compile(r"\\?frac\s*\{")
    while True:
        m = pattern.search(s)
        if not m:
            break
        idx = m.end() - 1  # auf '{'

        def _extract_group(pos: int) -> tuple[str, int] | None:
            if pos >= len(s) or s[pos] != "{":
                return None
            depth = 0
            start = pos + 1
            for j in range(pos, len(s)):
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                    if depth == 0:
                        return s[start:j], j + 1
            return None

        g1 = _extract_group(idx)
        if g1 is None:
            break
        num, after1 = g1
        while after1 < len(s) and s[after1].isspace():
            after1 += 1
        g2 = _extract_group(after1)
        if g2 is None:
            break
        den, after2 = g2
        s = s[:m.start()] + f"(({num})/({den}))" + s[after2:]
    return s


def _insert_implicit_mul(tokens: list[str]) -> list[str]:
    """Fügt fehlendes `*` ein, z. B. `2x` -> `2*x`, `2ab` -> `2*a*b`, `(x+1)(x-1)` -> `(x+1)*(x-1)`."""
    out: list[str] = []
    for tok in tokens:
        if len(tok) > 1 and tok.isalpha() and tok.lower() not in (*_TEX_FUNCS, "pi"):
            # Zerlege `ab`, `xy` in Einzelvariablen `a`, `*`, `b`
            chars = list(tok.lower())
            for k, ch in enumerate(chars):
                if k > 0:
                    out.append("*")
                out.append(ch)
            continue
        out.append(tok.lower())

    res: list[str] = []
    for tok in out:
        if res:
            prev = res[-1]
            prev_is_val = prev in (")", "!") or _NUM_RE.match(prev) or (prev.isalpha() and prev not in _TEX_FUNCS)
            cur_is_val = tok == "(" or _NUM_RE.match(tok) or tok.isalpha()
            if prev_is_val and cur_is_val:
                res.append("*")
        res.append(tok)
    return res


def normalize_math_text(raw: str) -> str:
    """Bereinigt LaTeX-, Markdown- und Unicode-Schreibweisen in einen kanonischen Rechenstring."""
    s = str(raw).strip()
    if not s:
        return ""
    s = s.replace("\\(", " ").replace("\\)", " ").replace("\\[", " ").replace("\\]", " ")
    s = s.replace("$", "")
    # Optionale Aufzählungs-/Verbindungspräfixe wie `1.`, `5. a)`, `or `, `oder `
    s = re.sub(r"^\s*(?:or|oder|and|und)\b\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*\d+\.\s*(?:[a-z]\)\s*)?(?=[(\[\-+\d\\a-zA-Z])", "", s)
    s = re.sub(r"\\text\s*\{[^{}]*\}", " ", s)
    s = re.sub(r"\\mathrm\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\left|\\right|\\,|\\;|\\:|\\!|\\quad|\\qquad|\\pm|\\mp", " ", s)
    s = s.translate(_SUPERSCRIPTS).translate(_OP_TRANS)
    s = re.sub(r"\\(?:cdot|times|ast|bullet)", "*", s)
    s = re.sub(r"\\div\b", "/", s)
    s = re.sub(r"\\pi\b", "pi", s)
    for fn in _TEX_FUNCS:
        s = re.sub(rf"\\{fn}\b", fn, s)
    s = _replace_latex_frac(s)
    # Übrige `{...}`-Exponenten oder Klammer-Gruppen in `(...)` überführen
    s = s.replace("{", "(").replace("}", ")")
    s = s.replace("**", "^")
    return s.strip()


# --------------------------------------------------------------------------- Exakte Polynom-Arithmetik

def _poly_clean(p: Poly) -> Poly:
    return {m: c for m, c in p.items() if c != 0}


def _poly_const(val: Fraction) -> Poly:
    return {(): val} if val != 0 else {}


def _poly_var(name: str) -> Poly:
    return {((name, 1),): Fraction(1)}


def _poly_add(a: Poly, b: Poly) -> Poly:
    res = dict(a)
    for m, c in b.items():
        res[m] = res.get(m, Fraction(0)) + c
    return _poly_clean(res)


def _poly_sub(a: Poly, b: Poly) -> Poly:
    res = dict(a)
    for m, c in b.items():
        res[m] = res.get(m, Fraction(0)) - c
    return _poly_clean(res)


def _poly_neg(a: Poly) -> Poly:
    return {m: -c for m, c in a.items()}


def _monom_mul(m1: Monom, m2: Monom) -> Monom:
    d: dict[str, int] = dict(m1)
    for v, e in m2:
        d[v] = d.get(v, 0) + e
    return tuple(sorted((v, e) for v, e in d.items() if e > 0))


def _poly_mul(a: Poly, b: Poly) -> Poly:
    res: Poly = {}
    for m1, c1 in a.items():
        for m2, c2 in b.items():
            m = _monom_mul(m1, m2)
            res[m] = res.get(m, Fraction(0)) + c1 * c2
    return _poly_clean(res)


def _poly_pow(a: Poly, exp: int) -> Poly:
    if exp < 0 or exp > 12:
        raise ValueError("exponent out of range")
    res = _poly_const(Fraction(1))
    for _ in range(exp):
        res = _poly_mul(res, a)
    return res


def _poly_div(a: Poly, b: Poly) -> Poly:
    if not b:
        raise ValueError("division by zero")
    if len(b) == 1 and () in b:
        c = b[()]
        return _poly_clean({m: coef / c for m, coef in a.items()})
    raise ValueError("non-constant denominator")


def _poly_degree(p: Poly) -> int:
    return max((sum(e for _, e in m) for m in p), default=0)


def _poly_vars(p: Poly) -> set[str]:
    return {v for m in p for v, _ in m}


def parse_poly(expr_str: str) -> Poly:
    """Parst einen Ausdruck in ein exaktes multivariates rationales Polynom."""
    norm = normalize_math_text(expr_str)
    if not norm or "=" in norm:
        raise ValueError("empty or contains =")
    raw_tokens = _TOKEN_RE.findall(norm)
    # Prüfe, ob unverstandene Zeichen übrig blieben (außer Whitespace)
    stripped = re.sub(r"\s+", "", norm)
    rejoined = "".join(raw_tokens)
    if stripped != rejoined:
        raise ValueError("unsupported characters")
    tokens = _insert_implicit_mul(raw_tokens)
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def take() -> str:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_expr() -> Poly:
        p = parse_term()
        while peek() in ("+", "-"):
            op = take()
            p = _poly_add(p, parse_term()) if op == "+" else _poly_sub(p, parse_term())
        return p

    def parse_term() -> Poly:
        p = parse_signed()
        while peek() in ("*", "/"):
            op = take()
            rhs = parse_signed()
            p = _poly_mul(p, rhs) if op == "*" else _poly_div(p, rhs)
        return p

    def parse_signed() -> Poly:
        sign = 1
        while peek() in ("+", "-"):
            if take() == "-":
                sign = -sign
        p = parse_atom()
        while peek() == "^":
            take()
            exp_p = parse_signed()
            if not exp_p:
                exp = 0
            elif len(exp_p) == 1 and () in exp_p and exp_p[()].denominator == 1:
                exp = int(exp_p[()])
            else:
                raise ValueError("non-integer exponent")
            p = _poly_pow(p, exp)
        return _poly_neg(p) if sign < 0 else p

    def parse_atom() -> Poly:
        tok = peek()
        if tok == "(":
            take()
            p = parse_expr()
            if peek() != ")":
                raise ValueError("missing )")
            take()
            return p
        if tok and _NUM_RE.match(tok):
            take()
            return _poly_const(Fraction(tok))
        if tok and len(tok) == 1 and tok.isalpha():
            take()
            return _poly_var(tok)
        raise ValueError(f"unexpected token {tok!r}")

    poly = parse_expr()
    if pos != len(tokens):
        raise ValueError("trailing tokens")
    return poly


# --------------------------------------------------------------------------- AST-Funktions-Fallback

_SAFE_FUNCS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "ln": math.log,
    "abs": abs,
    "fact": math.factorial,
}


def _to_python_expr(expr_str: str) -> str:
    norm = normalize_math_text(expr_str)
    if not norm or "=" in norm:
        raise ValueError("empty or =")
    raw_tokens = _TOKEN_RE.findall(norm)
    if re.sub(r"\s+", "", norm) != "".join(raw_tokens):
        raise ValueError("unsupported chars")
    tokens = _insert_implicit_mul(raw_tokens)
    out: list[str] = []
    for tok in tokens:
        if tok == "!":
            if not out:
                raise ValueError("dangling !")
            arg = out.pop()
            out.append(f"fact({arg})")
        elif tok == "^":
            out.append("**")
        else:
            out.append(tok)
    return "".join(out)


def _eval_ast_node(node: ast.AST, env: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return math.pi
        if node.id in env:
            return env[node.id]
        raise ValueError(f"unknown var {node.id}")
    if isinstance(node, ast.UnaryOp):
        v = _eval_ast_node(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return v
        if isinstance(node.op, ast.USub):
            return -v
        raise ValueError("unsupported unary op")
    if isinstance(node, ast.BinOp):
        l = _eval_ast_node(node.left, env)
        r = _eval_ast_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return l + r
        if isinstance(node.op, ast.Sub):
            return l - r
        if isinstance(node.op, ast.Mult):
            return l * r
        if isinstance(node.op, ast.Div):
            return l / r
        if isinstance(node.op, ast.Pow):
            return l ** r
        raise ValueError("unsupported binop")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
        args = [_eval_ast_node(a, env) for a in node.args]
        return float(_SAFE_FUNCS[node.func.id](*args))
    raise ValueError("disallowed ast node")


def try_compile_numeric(expr_str: str) -> tuple[ast.Expression, set[str]] | None:
    """Kompiliert einen Term (inkl. `sqrt`, `tan`, `!`, `pi`) in einen sicheren AST, falls valide."""
    try:
        py_src = _to_python_expr(expr_str)
        tree = ast.parse(py_src, mode="eval")
        names = {
            n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and n.id not in _SAFE_FUNCS and n.id != "pi"
        }
        # Trocken-Evaluierung an einem Testpunkt prüft Knotentypen
        test_env = {v: 0.73 for v in names}
        _eval_ast_node(tree, test_env)
        return tree, names
    except Exception:
        return None


def numeric_sides_equivalent(lhs_str: str, rhs_str: str) -> bool | None:
    """Prüft numerisch an mehreren Testpunkten, ob `lhs == rhs` identisch gilt (None falls nicht auswertbar)."""
    c1 = try_compile_numeric(lhs_str)
    c2 = try_compile_numeric(rhs_str)
    if c1 is None or c2 is None:
        return None
    t1, n1 = c1
    t2, n2 = c2
    all_vars = sorted(n1 | n2)
    if not all_vars:
        try:
            v1 = _eval_ast_node(t1, {})
            v2 = _eval_ast_node(t2, {})
            return math.isclose(v1, v2, rel_tol=1e-9, abs_tol=1e-9)
        except Exception:
            return None

    samples = (0.37, 0.71, 1.13, 1.89, 2.41)
    ok_points = 0
    for idx in range(len(samples)):
        env = {v: samples[(idx + vi) % len(samples)] for vi, v in enumerate(all_vars)}
        try:
            v1 = _eval_ast_node(t1, env)
            v2 = _eval_ast_node(t2, env)
            if not (math.isfinite(v1) and math.isfinite(v2)):
                continue
            ok_points += 1
            if not math.isclose(v1, v2, rel_tol=1e-7, abs_tol=1e-7):
                return False
        except Exception:
            continue
    return ok_points >= 3 if ok_points else None


# --------------------------------------------------------------------------- Hochstufige Zeilen-Klassifikation

def _linear_coeffs_for_var(p: Poly, var: str) -> tuple[Fraction, Fraction, Fraction]:
    """Extrahiert `(c0, c1, c2)` für univariates Polynom bis Grad 2."""
    c0 = p.get((), Fraction(0))
    c1 = p.get(((var, 1),), Fraction(0))
    c2 = p.get(((var, 2),), Fraction(0))
    return (c0, c1, c2)


def _looks_like_question(raw: str) -> bool:
    low = raw.lower().strip()
    if "?" in low:
        return True
    return any(re.search(rf"\b{w}\b", low) for w in _QUESTION_WORDS)


def _is_scalar_only(raw: str, norm: str) -> bool:
    s = norm.replace(" ", "")
    return bool(_NUM_RE.match(s) or re.fullmatch(r"[+\-]?\d+(?:\.\d+)?|[a-z](?:_[0-9]+)?", s))


def _has_prose_words(raw: str) -> bool:
    """Erkennt natürliche Wörter (3+ Buchstaben außerhalb erlaubter Mathe-/LaTeX-Tokens)."""
    cleaned = _LATEX_CMD_RE.sub(" ", str(raw))
    for w in re.findall(r"[a-zA-ZäöüßÄÖÜ]{3,}", cleaned):
        if w.lower() not in _ALLOWED_WORDS:
            return True
    return False


def classify_line(line: str) -> dict[str, Any]:
    """Klassifiziert eine gelesene VLM-Zeile in Struktur-Kind, Polynom-Daten und Parse-Status."""
    raw = str(line).strip()
    if not raw:
        return {"ok": False, "parsed": False, "kind": "empty", "raw": raw, "norm": ""}

    if _SUM_RE.search(raw):
        return {"ok": False, "parsed": False, "kind": "sum", "raw": raw, "norm": raw}

    if _looks_like_question(raw) and "=" not in raw:
        return {"ok": False, "parsed": False, "kind": "question", "raw": raw, "norm": raw}

    if "=" not in raw and _has_prose_words(raw):
        return {"ok": False, "parsed": False, "kind": "text", "raw": raw, "norm": raw}

    norm = normalize_math_text(raw)
    eq_count = norm.count("=")

    # Fall 1: Zeile endet offen mit `=` (z. B. `(3x + 4y)^3 =`)
    if eq_count >= 1 and norm.rstrip().endswith("="):
        lhs_part = norm.rsplit("=", 1)[0].strip()
        try:
            poly = parse_poly(lhs_part)
            return {"ok": False, "parsed": True, "kind": "incomplete_rhs", "raw": raw, "norm": norm,
                    "lhs_str": lhs_part, "lhs_poly": poly}
        except Exception:
            if try_compile_numeric(lhs_part) is not None:
                return {"ok": False, "parsed": True, "kind": "incomplete_rhs", "raw": raw, "norm": norm,
                        "lhs_str": lhs_part, "lhs_poly": None}
            return {"ok": False, "parsed": False, "kind": "incomplete_rhs_text", "raw": raw, "norm": norm}

    # Fall 2: Zeile beginnt mit `=` (Fortsetzung `= RHS1 = RHS2`)
    if eq_count >= 1 and norm.lstrip().startswith("="):
        parts = [p.strip() for p in norm.lstrip()[1:].split("=") if p.strip()]
        return {"ok": False, "parsed": bool(parts), "kind": "chained_rhs", "raw": raw, "norm": norm, "parts": parts}

    # Fall 3: Term oder Einzelwert OHNE `=`
    if eq_count == 0:
        if _is_scalar_only(raw, norm):
            return {"ok": False, "parsed": True, "kind": "scalar", "raw": raw, "norm": norm}
        try:
            poly = parse_poly(norm)
            return {
                "ok": False, "parsed": True, "kind": "term", "raw": raw, "norm": norm,
                "poly": poly, "vars": sorted(_poly_vars(poly)), "is_const": not bool(_poly_vars(poly)),
            }
        except Exception:
            if try_compile_numeric(norm) is not None:
                return {"ok": False, "parsed": True, "kind": "term_numeric", "raw": raw, "norm": norm}
            return {"ok": False, "parsed": False, "kind": "text", "raw": raw, "norm": raw}

    # Fall 4: Mehrere `=` in einer Zeile (Kettenrechnung `A = B = C`)
    if eq_count > 1:
        parts = [p.strip() for p in norm.split("=")]
        if any(not p for p in parts):
            return {"ok": False, "parsed": False, "kind": "malformed_chain", "raw": raw, "norm": norm}
        parsed_polys: list[Poly] = []
        try:
            parsed_polys = [parse_poly(p) for p in parts]
            all_vars = sorted({v for p in parsed_polys for v in _poly_vars(p)})
            all_equal = all(_poly_sub(parsed_polys[i], parsed_polys[i + 1]) == {} for i in range(len(parsed_polys) - 1))
            return {
                "ok": True, "parsed": True, "kind": "chained_equation", "raw": raw, "norm": norm,
                "parts": parts, "polys": parsed_polys, "vars": all_vars,
                "arithmetic": len(all_vars) == 0, "all_equal": all_equal,
                "is_identity": all_equal,
                "left_val": parsed_polys[0].get((), Fraction(0)) if not all_vars else None,
            }
        except Exception:
            # Fallback über numerischen AST für Ketten mit sqrt/!
            pair_checks = [numeric_sides_equivalent(parts[i], parts[i + 1]) for i in range(len(parts) - 1)]
            if all(c is not None for c in pair_checks):
                all_equal = all(bool(c) for c in pair_checks)
                return {
                    "ok": True, "parsed": True, "kind": "chained_equation_num", "raw": raw, "norm": norm,
                    "parts": parts, "arithmetic": False, "all_equal": all_equal, "is_identity": all_equal,
                }
            return {"ok": False, "parsed": False, "kind": "text_eq", "raw": raw, "norm": norm}

    # Fall 5: Klassische Gleichung `LHS = RHS` (`eq_count == 1`)
    lhs_s, rhs_s = (part.strip() for part in norm.split("=", 1))
    if not lhs_s or not rhs_s:
        return {"ok": False, "parsed": False, "kind": "malformed_eq", "raw": raw, "norm": norm}

    try:
        pl = parse_poly(lhs_s)
        pr = parse_poly(rhs_s)
    except Exception:
        eq_num = numeric_sides_equivalent(lhs_s, rhs_s)
        if eq_num is not None:
            return {
                "ok": True, "parsed": True, "kind": "numeric_identity", "raw": raw, "norm": norm,
                "side_raw": (lhs_s, rhs_s), "arithmetic": False,
                "is_identity": bool(eq_num), "solved": bool(eq_num), "solution": None, "var": None,
            }
        return {"ok": False, "parsed": False, "kind": "text_eq", "raw": raw, "norm": norm}

    diff = _poly_sub(pl, pr)
    all_vars = sorted(_poly_vars(pl) | _poly_vars(pr))
    deg_max = max(_poly_degree(pl), _poly_degree(pr))

    if len(all_vars) == 0:
        l_val = pl.get((), Fraction(0))
        r_val = pr.get((), Fraction(0))
        is_correct = (l_val == r_val)
        return {
            "ok": True, "parsed": True, "kind": "arithmetic", "raw": raw, "norm": norm,
            "arithmetic": True, "var": None, "vars": [],
            "sides": ((l_val, Fraction(0), Fraction(0)), (r_val, Fraction(0), Fraction(0))),
            "side_raw": (lhs_s, rhs_s), "correct": is_correct, "solution": None,
            "solved": is_correct, "left_val": l_val, "right_val": r_val,
            "is_identity": is_correct,
        }

    # 1 Variable & Grad <= 2 (kompatibel zur bestehenden Tutor-Diagnose!)
    if len(all_vars) == 1 and _poly_degree(diff) <= 2:
        var = all_vars[0]
        sl = _linear_coeffs_for_var(pl, var)
        sr = _linear_coeffs_for_var(pr, var)
        d0, d1, d2 = sl[0] - sr[0], sl[1] - sr[1], sl[2] - sr[2]
        if d2 == 0 and d1 != 0:
            sol = -d0 / d1
            solved = (
                (sl == (Fraction(0), Fraction(1), Fraction(0)) and sr[1] == 0 and sr[2] == 0)
                or (sr == (Fraction(0), Fraction(1), Fraction(0)) and sl[1] == 0 and sl[2] == 0)
            )
            return {
                "ok": True, "parsed": True, "kind": "linear_1var", "raw": raw, "norm": norm,
                "var": var, "vars": all_vars, "sides": (sl, sr), "side_raw": (lhs_s, rhs_s),
                "solution": sol, "solved": solved, "poly_sides": (pl, pr), "diff_poly": diff,
                "is_identity": False,
            }
        # Identität (`x = x`, `x^2 + 1 = x^2 + 1`) oder Widerspruch (`x + 1 = x`) oder Quadratisch
        both_have_vars = bool(_poly_vars(pl) & _poly_vars(pr))
        return {
            "ok": True, "parsed": True, "kind": "poly_1var", "raw": raw, "norm": norm,
            "var": var, "vars": all_vars, "sides": (sl, sr), "side_raw": (lhs_s, rhs_s),
            "solution": None, "solved": False, "poly_sides": (pl, pr), "diff_poly": diff,
            "degree": _poly_degree(diff), "is_identity": (len(diff) == 0),
            "is_contradiction": (len(diff) == 1 and () in diff),
            "has_expansion_on_lhs": both_have_vars and ("(" in lhs_s or "^" in lhs_s) and deg_max >= 2,
        }

    # Multivariate Polynomgleichung oder Grad >= 3 (z. B. `(a+b)^2 = a^2 + 2ab + b^2`)
    both_have_vars = bool(_poly_vars(pl) & _poly_vars(pr))
    return {
        "ok": True, "parsed": True, "kind": "poly_multi", "raw": raw, "norm": norm,
        "var": all_vars[0] if len(all_vars) == 1 else None, "vars": all_vars,
        "side_raw": (lhs_s, rhs_s), "poly_sides": (pl, pr), "diff_poly": diff,
        "degree": deg_max, "solution": None, "solved": False,
        "is_identity": (len(diff) == 0),
        "has_expansion_on_lhs": both_have_vars and ("(" in lhs_s or "^" in lhs_s) and deg_max >= 2,
    }
