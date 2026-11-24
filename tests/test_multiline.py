"""Mehrzeilen-Gruppierung (occ/multiline.py): Rechenketten rein strukturell, ohne Tutor.
Deckt Pass-5-Vorgaben ab: Fortsetzungs-=, offene Operatoren, Schuelerfehler erhalten,
Anti-Domino, getrennte Aufgaben/Spalten, unveraenderte Eingabe."""
import copy

from ocr.multiline import group_lines, page_structure

H, GAP = 50, 20


def _line(latex, y0, x0=40, w=320, h=H, **kw):
    return {"latex": latex, "bbox": (x0, y0, x0 + w, y0 + h), **kw}


def _stack(latexes, *, y0=0, gap=GAP, x0=40, h=H, **kw):
    return [_line(t, y0 + i * (h + gap), x0=x0, h=h, **kw) for i, t in enumerate(latexes)]


def test_power_chain_groups_into_one():
    lines = _stack([r"(x+y)^{3}", r"=(x+y)(x+y)^{2}", r"=x^{3}+3x^{2}y+3xy^{2}+y^{3}"])
    chains = group_lines(lines)
    assert len(chains) == 1
    assert chains[0]["line_indices"] == [0, 1, 2]


def test_trailing_operator_continues():
    plus = group_lines(_stack([r"x+y+", r"z"]))
    assert len(plus) == 1 and plus[0]["line_indices"] == [0, 1]
    eq = group_lines(_stack([r"x=", r"5"]))
    assert len(eq) == 1 and eq[0]["line_indices"] == [0, 1]


def test_student_mistake_stays_grouped_and_preserved():
    # K25-Arithmetik mit falschem Endschritt 41 statt 51.
    lines = _stack([r"17\cdot3", r"=3\cdot10+3\cdot7", r"=30+21", r"=41"],
                   uncertain=False, math_status=None)
    lines[3]["math_status"] = False
    chains = group_lines(lines)
    assert len(chains) == 1
    assert chains[0]["line_indices"] == [0, 1, 2, 3]
    assert chains[0]["lines"][3]["latex"] == r"=41"          # Schuelerfehler unangetastet
    assert chains[0]["lines"][3]["uncertain"] is False       # OCR-sicher
    assert chains[0]["lines"][3]["math_status"] is False     # Rechenwahrheit getrennt


def test_anti_domino_uncertain_does_not_spread():
    lines = _stack([r"(x+y)^{3}", r"=(x+y)(x+y)^{2}", r"=x^{3}+3x^{2}y+3xy^{2}+y^{3}"],
                   uncertain=False)
    lines[1]["uncertain"] = True
    chains = group_lines(lines)
    assert len(chains) == 1
    c = chains[0]
    assert c["has_uncertain_step"] is True
    assert c["uncertain_line_indices"] == [1]
    assert c["lines"][0]["uncertain"] is False
    assert c["lines"][2]["uncertain"] is False


def test_two_independent_equations_stay_separate():
    chains = group_lines(_stack([r"2x=6", r"3y=12"]))
    assert len(chains) == 2


def test_columns_do_not_merge():
    lines = [_line(r"x=1", 0, x0=40), _line(r"x=2", 0, x0=700)]
    assert len(group_lines(lines)) == 2


def test_exercise_label_breaks_chain():
    chains = group_lines(_stack([r"2x=6", r"3) 2x=9"]))
    assert len(chains) == 2


def test_large_vertical_gap_breaks_chain():
    lines = [_line(r"x=1", 0), _line(r"x=2", 0 + H + 5 * H)]  # gleiche Variable, grosser Abstand
    assert len(group_lines(lines)) == 2


def test_input_lines_not_mutated():
    lines = _stack([r"2x+4=8", r"2x=4", r"x=2"], uncertain=False)
    snapshot = copy.deepcopy(lines)
    group_lines(lines)
    assert lines == snapshot


def test_k25_pattern_groups_like_layout():
    # Fortsetzung auf k+1, wobei Zeile 1 ein nackter Term ist (kein fuehrendes '=').
    lines = _stack([r"17\cdot3", r"=3\cdot10+3\cdot7", r"=30+21", r"=41"])
    assert len(group_lines(lines)) == 1


def test_k25_dropped_equals_bare_terms_group():
    # So liest OCR K25 real (kalib/ketten/last_real.jsonl): fuehrendes '=' wurde verschluckt.
    lines = _stack([r"17\cdot3", r"3 \cdot 10+3 \cdot 7", r"30+21", r"41"])
    assert len(group_lines(lines)) == 1


def test_x_case_artifact_does_not_split_chain():
    # OCR liest x/X gemischt (Pass 2, Chunk A): fuer die Gruppierung dieselbe Variable.
    lines = _stack([r"3x+5=20", r"3X=15", r"x=5"])
    assert len(group_lines(lines)) == 1


def test_bare_term_after_equation_continues():
    lines = _stack([r"(x+y)", r"(x+y)^{2}"])
    assert len(group_lines(lines)) == 1


def test_page_structure_shape_and_reference_identity():
    lines = _stack([r"2x=6", r"x=3"])
    page = page_structure(lines)
    assert page["lines"] == lines
    assert len(page["chains"]) == 1
    assert page["chains"][0]["lines"][0] is lines[0]   # Referenz, keine Kopie


def test_split_lines_backward_compatible_with_boxes():
    from PIL import Image, ImageDraw
    from ocr.pre import split_lines, split_lines_with_boxes
    img = Image.new("L", (200, 200), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 120, 45], fill=0)
    d.rectangle([20, 100, 120, 125], fill=0)
    plain = split_lines(img)
    boxed = [im for im, _ in split_lines_with_boxes(img)]
    assert len(plain) == len(boxed) == 2
    for a, b in zip(plain, boxed):
        assert list(a.getdata()) == list(b.getdata())
