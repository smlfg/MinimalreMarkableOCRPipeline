"""Mehrzeilige Rechenketten (ADR-005 Seitenstruktur, ADR-009 Ketten).

Gruppiert vertikal geordnete Mathe-Zeilen zu Rechenketten *rein strukturell*: vertikale Nähe,
Spalten-Konsistenz und explizite Fortsetzungssignale (führendes ``=``/``\\approx``/…,
offener Operator oder offene Klammer am Zeilenende, gleiche Variablenmenge). Es findet **keine**
mathematische Prüfung und **keine** Korrektur statt (kein Tutor, kein Schrittrichter) — das ist
bewusst Aufgabe der Validator-/Tutor-Stufe.

Issue-#1-Garantien (hart):
- Zeilen werden **nie** verändert. ``latex``, ``uncertain``, ``repair``, ``alt``, ``math_status``
  bleiben unangetastet; Ketten halten nur Referenzen auf die Original-Dicts.
- **Kein Domino-Effekt:** die Unsicherheit einer Zeile färbt nie andere Zeilen um. Ketten tragen
  höchstens informative Felder (``has_uncertain_step``, ``uncertain_line_indices``).
- Schülerfehler bleiben über Zeilen erhalten (Zeile für Zeile unverändert).

Erwartetes Zeilen-Dict: mind. ``bbox=(x0,y0,x1,y1)`` (Bildkoordinaten, y nach unten) und
``latex``. Alle weiteren Felder werden unverändert durchgereicht.
"""
from __future__ import annotations

import re

# Führende Fortsetzungsmarker auf Zeile k+1 (Termumformung / Relation).
_CONT_START_RE = re.compile(
    r"^\s*(?:=|\\approx\b|\\equiv\b|\\Rightarrow\b|\\Leftrightarrow\b|\\implies\b|"
    r"\\iff\b|\\leq?\b|\\geq?\b|\\neq?\b|[<>])"
)
# Offene Operatoren / unvollständige Klammern am Zeilenende von k.
_TRAIL_SPACE_RE = re.compile(r"(?:\\[,;! ]|\\quad\b|\\qquad\b|\s)+$")
_OPEN_END_RE = re.compile(r"(?:\+|-|\\cdot\b|\\times\b|=|\(|\[|\{|\\left[([{])$")
# Aufgaben-/Blockmarker (1. / a) / Aufgabe …): erzwingen einen Kettenwechsel.
_LABEL_RE = re.compile(
    r"^\s*(?:\(?[0-9]{1,2}[.)]\s|\(?[A-Za-z][.)]\s|Aufgabe\b|aufgabe\b|Nr\.?\s)"
)
_ENV_RE = re.compile(r"\\(?:begin|end)\{[^{}]*\}")
_CMD_RE = re.compile(r"\\[A-Za-z]+")
# Relationsmarker: eine Zeile ohne diese ist ein „nackter Term“ (K25-Konvention: Fortsetzung).
_REL_RE = re.compile(
    r"=|\\approx\b|\\equiv\b|\\leq?\b|\\geq?\b|\\neq?\b|\\Rightarrow\b|\\Leftrightarrow\b|"
    r"\\implies\b|\\iff\b|[<>]"
)


def _starts_continuation(latex: str) -> bool:
    return bool(_CONT_START_RE.match(latex or ""))


def _ends_open(latex: str) -> bool:
    s = _TRAIL_SPACE_RE.sub("", latex or "")
    return bool(_OPEN_END_RE.search(s))


def _is_label(latex: str) -> bool:
    return bool(_LABEL_RE.match(latex or ""))


def _is_bare_term(latex: str) -> bool:
    """Zeile ohne Relationszeichen = nackter Term. Nach Schul-Konvention setzt ein nackter Term
    (ab Zeile 2) die Rechnung fort (K25; vgl. bench/chain_bench.validator_lines)."""
    return not _REL_RE.search(latex or "")


def _vars(latex: str) -> frozenset[str]:
    """Grobe Variablenmenge einer Zeile (rein strukturell, keine Auswertung): Umgebungs- und
    Kommandonamen entfernen, dann verbleibende ASCII-Buchstaben sammeln. Gross/Klein wird
    gefaltet, weil OCR ``x``/``X`` verwechselt (Pass 2, Chunk A) — fuer die Gruppierung zaehlt
    „gleiche Variable“, nicht die exakte Schreibweise. Reicht, um ``x`` von ``y`` zu trennen."""
    s = _ENV_RE.sub("", latex or "")
    s = _CMD_RE.sub("", s)
    return frozenset(ch.lower() for ch in s if ch.isalpha() and ch.isascii())


def _median(values: list[float]) -> float:
    v = sorted(values)
    n = len(v)
    if n == 0:
        return 0.0
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def _continues(prev: dict, cur: dict, med_h: float, gap_factor: float, indent_tol: float) -> bool:
    px0, py0, px1, py1 = prev["bbox"]
    cx0, cy0, cx1, cy1 = cur["bbox"]
    gap = cy0 - py1
    # Großer vertikaler Abstand ist ein expliziter Block-Trenner (neue Aufgabe).
    if gap > gap_factor * med_h:
        return False
    if gap < -0.5 * med_h:            # überlappend / nicht sauber geordnet
        return False
    # Spalten-Konsistenz: x-Bereiche müssen sich (mit Toleranz) überlappen, sonst zwei Spalten.
    if cx1 < px0 - indent_tol or cx0 > px1 + indent_tol:
        return False
    c_latex, p_latex = cur.get("latex", ""), prev.get("latex", "")
    if _is_label(c_latex):            # expliziter Aufgabenmarker beginnt neue Kette
        return False
    # Starke, explizite Fortsetzungssignale.
    if _starts_continuation(c_latex):
        return True
    if _ends_open(p_latex):
        return True
    # Nackter Term auf k+1 setzt die Rechnung fort (Schul-Konvention, K25 ohne fuehrendes '=').
    if _is_bare_term(c_latex):
        return True
    # Schwaches, strukturelles Signal: gleiche (nicht-leere) Variablenmenge = gleiche Aufgabe.
    pv, cv = _vars(p_latex), _vars(c_latex)
    if pv and pv == cv:
        return True
    return False


def group_lines(lines: list[dict], *, gap_factor: float = 2.0,
                indent_tol: float | None = None) -> list[dict]:
    """Gruppiert Zeilen zu Ketten. Rückgabe: Liste von Ketten-Dicts (Reihenfolge = Lesereihenfolge).

    Jede Kette: ``{"id", "line_indices", "lines", "has_uncertain_step",
    "uncertain_line_indices"}``. ``line_indices``/``lines`` beziehen sich auf die Eingabeliste;
    die Original-Dicts werden **nicht** kopiert oder verändert.
    """
    n = len(lines)
    if n == 0:
        return []
    heights = [max(1.0, float(l["bbox"][3] - l["bbox"][1])) for l in lines if l.get("bbox")]
    med_h = _median(heights) or 1.0
    tol = med_h if indent_tol is None else indent_tol
    # Lesereihenfolge: oben nach unten, dann links nach rechts; Originalindizes merken.
    order = sorted(range(n), key=lambda i: (float(lines[i]["bbox"][1]), float(lines[i]["bbox"][0])))
    chains: list[list[int]] = []
    for idx in order:
        if not chains:
            chains.append([idx])
            continue
        prev_idx = chains[-1][-1]
        prev, cur = lines[prev_idx], lines[idx]
        if prev.get("bbox") and cur.get("bbox") and _continues(prev, cur, med_h, gap_factor, tol):
            chains[-1].append(idx)
        else:
            chains.append([idx])
    out = []
    for ci, idxs in enumerate(chains):
        members = [lines[i] for i in idxs]
        unc = [k for k, l in enumerate(members) if l.get("uncertain")]
        out.append({
            "id": f"chain_{ci}",
            "line_indices": idxs,
            "lines": members,
            "has_uncertain_step": bool(unc),
            "uncertain_line_indices": unc,
        })
    return out


def page_structure(lines: list[dict], **kwargs) -> dict:
    """Seitenobjekt (ADR-005, additiv): Original-Zeilen unverändert + daraus abgeleitete Ketten."""
    return {"lines": list(lines), "chains": group_lines(lines, **kwargs)}
