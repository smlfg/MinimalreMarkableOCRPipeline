"""Multi-line calculation grouping (Pass 5).

Groups recognized math lines into step chains without mutating line fields.
Chains are informational: they never set line.uncertain (no Domino-uncertainty).
"""
from __future__ import annotations

import re
import statistics
from typing import Any

# Leading operators that signal continuation of the previous line
_LEAD_CONT = re.compile(
    r"^\s*("
    r"=|<=>|=>|\\approx|\\equiv|\\sim|\\Rightarrow|\\Leftrightarrow|"
    r"\\implies|\\iff|<|>|\\leq|\\geq|\\neq"
    r")"
)

_TRANSFORM_ANNOT = re.compile(r"^\s*(?:\||\\mid)\s")
_TRAIL_TRANSFORM = re.compile(r"(?:\||\\mid)\s+[^\|=]+$")

_TRAIL_OPEN = re.compile(
    r"(?:"
    r"[\+\-\=]$|"
    r"(?:\\cdot|\\times)\s*$|"
    r"[+\-\=](?:\\cdot|\\times)?\s*$|"
    r"[\(\[\{](?:[^\)\]\}]*)$"
    r")",
    re.MULTILINE,
)

_LABEL_BREAK = re.compile(
    r"^\s*(?:\d+\.\s|\d+\)\s|[a-zA-ZäöüÄÖÜ]\)\s|Aufgabe\b|Aufg\.|Exercise\b|Übung\b)",
    re.IGNORECASE,
)

_ARITH_BODY = re.compile(
    r"^[\s\d\+\-\*\/\(\)\[\]\{\}\.,\\a-zA-Z\|^_]+$"
)

_GAP_TIGHT = 2.4
_GAP_BREAK = 4.0
_GAP_FRESH = 1.45  # slot gap between exercises on ketten pages (~126px vs ~20px in-chain)
_COL_SLACK = 0.35  # fraction of median width


def _text(line: dict) -> str:
    return (line.get("latex") or line.get("text") or "").strip()


def _geom(line: dict, default_h: float = 48.0) -> tuple[float, float, float, float, float]:
    bb = line.get("bbox")
    if isinstance(bb, (list, tuple)) and len(bb) >= 4:
        x, y, w, h = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        return y, y + h, x, x + w, h
    y = float(line.get("y", 0))
    h = float(line.get("h", default_h))
    x = float(line.get("x", 0))
    w = float(line.get("w", max(120.0, len(_text(line)) * 12)))
    return y, y + h, x, x + w, h


def _median_height(lines: list[dict]) -> float:
    hs = [_geom(ln)[4] for ln in lines if _text(ln)]
    return statistics.median(hs) if hs else 48.0


def _line_id(line: dict, idx: int) -> str:
    return str(line.get("id") or f"l{idx + 1}")


def leading_continuation(latex: str) -> bool:
    return bool(_LEAD_CONT.match(latex or ""))


def transform_annotation_line(latex: str) -> bool:
    """Step that is primarily a | … or \\mid … equivalence annotation."""
    s = (latex or "").strip()
    if not s:
        return False
    if _TRANSFORM_ANNOT.match(s):
        return True
    if re.search(r"(?:\||\\mid)\s", s) and "=" not in s:
        return True
    return False


def trailing_transform_annotation(latex: str) -> bool:
    s = (latex or "").rstrip()
    return bool(_TRAIL_TRANSFORM.search(s))


def trailing_open(latex: str) -> bool:
    s = (latex or "").rstrip()
    if not s:
        return False
    if _TRAIL_OPEN.search(s):
        return True
    if s.endswith((r"\cdot", r"\times", "+", "-", "=", "\\cdot", "\\times")):
        return True
    # unclosed delimiters
    for o, c in (("(", ")"), ("[", "]"), ("{", "}")):
        if s.count(o) > s.count(c):
            return True
    return False


def label_breaker(latex: str) -> bool:
    return bool(_LABEL_BREAK.match(latex or ""))


def bare_continuation_body(latex: str) -> bool:
    """K25 rule: arithmetic-looking line without leading '=' may still continue a chain."""
    s = (latex or "").strip()
    if not s or leading_continuation(s) or "=" in s:
        return False
    if label_breaker(s):
        return False
    if re.match(r"^-?\d+(?:\.\d+)?$", s):
        return True
    if re.search(r"[\+\-\*]|\\cdot|\\frac|\\times", s):
        return _ARITH_BODY.match(s) is not None
    return False


def standalone_equation_breaker(latex: str) -> bool:
    """Fresh two-sided equation that likely starts a new exercise."""
    s = (latex or "").strip()
    if not s or leading_continuation(s) or label_breaker(s):
        return False
    if "=" not in s:
        return False
    left, _, right = s.partition("=")
    if not (left.strip() and right.strip()):
        return False
    # Single-variable solve steps (x=5) stay in-chain; multi-term starts break.
    if re.match(r"^[a-zA-Z]\s*=", s) and not re.search(r"[\+\-\*\\/]", left):
        return False
    return True


def finished_solve_step(latex: str) -> bool:
    """Terminal assignment like x=5 after a solve chain (triggers fresh-equation break)."""
    s = (latex or "").strip()
    if not s or "=" not in s:
        return False
    left, _, right = s.partition("=")
    if not (left.strip() and right.strip()):
        return False
    return (
        bool(re.match(r"^[a-zA-Z]\s*=", s))
        and not re.search(r"[\+\-\*\\/]", left)
        and not leading_continuation(s)
    )


def _fresh_equation_after_solve(prev_tex: str, cur_tex: str) -> bool:
    """Break merge when a new multi-term equation follows a bare x=n step."""
    return (
        finished_solve_step(prev_tex)
        and standalone_equation_breaker(cur_tex)
        and not trailing_open(prev_tex)
        and not trailing_transform_annotation(prev_tex)
        and not leading_continuation(cur_tex)
    )


def _column_ok(x0_a: float, x0_b: float, med_w: float) -> bool:
    slack = max(24.0, med_w * _COL_SLACK)
    return abs(x0_a - x0_b) <= slack


def _links(prev: dict, cur: dict, prev_idx: int, med_h: float, med_w: float) -> bool:
    pt, pb, px0, _, _ = _geom(prev)
    ct, cb, cx0, _, _ = _geom(cur)
    gap = ct - pb
    if gap > med_h * _GAP_BREAK:
        return False
    if gap < 0:
        # Missing bbox/y (all default 0) or slight overlap: use reading order, not reject.
        gap = 0.0
    if not _column_ok(px0, cx0, med_w):
        return False

    prev_tex, cur_tex = _text(prev), _text(cur)
    if label_breaker(cur_tex):
        return False

    if (
        gap > med_h * _GAP_FRESH
        and not leading_continuation(cur_tex)
        and not trailing_open(prev_tex)
        and not trailing_transform_annotation(prev_tex)
        and not transform_annotation_line(cur_tex)
    ):
        return False

    if gap > med_h * _GAP_TIGHT and not leading_continuation(cur_tex):
        if standalone_equation_breaker(cur_tex) and not trailing_open(prev_tex):
            return False

    if leading_continuation(cur_tex):
        return gap <= med_h * _GAP_TIGHT
    if trailing_open(prev_tex) or trailing_transform_annotation(prev_tex):
        return gap <= med_h * _GAP_TIGHT
    if transform_annotation_line(cur_tex):
        return gap <= med_h * _GAP_TIGHT
    if bare_continuation_body(cur_tex) and prev_idx >= 0:
        return gap <= med_h * _GAP_TIGHT
    if (
        "=" in cur_tex
        and not standalone_equation_breaker(cur_tex)
        and gap <= med_h * _GAP_TIGHT
    ):
        return True
    if (
        gap <= med_h * _GAP_TIGHT
        and "=" in prev_tex
        and "=" in cur_tex
        and not label_breaker(cur_tex)
        and not _fresh_equation_after_solve(prev_tex, cur_tex)
    ):
        return True
    if prev_idx == 0 and "=" not in cur_tex and gap <= med_h * _GAP_TIGHT:
        return bare_continuation_body(cur_tex) or bool(re.search(r"\\cdot|\\times|[\+\-]", cur_tex))
    return False


def group_calculations(lines: list[dict]) -> list[dict]:
    """Group lines into calculation chains. Never mutates input line dicts."""
    if not lines:
        return []

    indexed = list(enumerate(lines))
    med_h = _median_height(lines)
    ws = [_geom(ln)[3] - _geom(ln)[2] for ln in lines]
    med_w = statistics.median(ws) if ws else 120.0

    chains: list[list[int]] = []
    cur_chain: list[int] = []

    def flush():
        nonlocal cur_chain
        if cur_chain:
            chains.append(cur_chain)
            cur_chain = []

    for i, line in indexed:
        if not _text(line):
            flush()
            continue
        if not cur_chain:
            cur_chain = [i]
            continue
        prev_i = cur_chain[-1]
        if _links(lines[prev_i], line, prev_i, med_h, med_w):
            cur_chain.append(i)
        else:
            flush()
            cur_chain = [i]
    flush()

    out: list[dict] = []
    for ci, idxs in enumerate(chains):
        line_ids = [_line_id(lines[j], j) for j in idxs]
        unc_idx = [
            k
            for k, j in enumerate(idxs)
            if bool(lines[j].get("uncertain"))
        ]
        out.append(
            {
                "id": f"c{ci + 1}",
                "line_ids": line_ids,
                "has_uncertain_step": bool(unc_idx),
                "uncertain_line_indices": unc_idx,
            }
        )
    return out


def lines_from_ketten_row(row: dict, gt: dict | None = None) -> list[dict]:
    """Build synthetic line dicts from a ketten `read` row (grouping-only eval)."""
    reads = row.get("read") or []
    slots = (gt or {}).get("slots") or []
    if slots:
        base_y = float(slots[0]["slot_y"][0])
        h = float(slots[0]["slot_y"][1] - slots[0]["slot_y"][0])
        pitch = (
            float(slots[1]["slot_y"][0] - slots[0]["slot_y"][0])
            if len(slots) >= 2
            else h + 20.0
        )
        x0 = float(slots[0].get("x_min", 660))
    else:
        base_y, h, pitch, x0 = 100.0, 72.0, 90.0, 660.0

    lines: list[dict] = []
    for i, tex in enumerate(reads):
        lines.append(
            {
                "id": f"{row.get('id', 'K')}_s{i}",
                "latex": tex,
                "y": base_y + i * pitch,
                "h": h,
                "x": x0,
                "uncertain": False,
            }
        )
    return lines