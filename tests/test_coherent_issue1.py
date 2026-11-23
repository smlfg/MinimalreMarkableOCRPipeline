"""Issue #1: direct unit tests for coherent() OCR-trust semantics."""
from ocr.coherence import coherent

CONFUSE_REPAIR_TT = r"17.3=52"
CONFUSE_REPAIR_GLM = r"17\cdot 3=52"


def test_repair_glm_corroboration_untrusted():
    latex, repair, trusted = coherent(CONFUSE_REPAIR_TT, CONFUSE_REPAIR_GLM)
    assert repair is not None
    assert trusted is False
    assert latex == CONFUSE_REPAIR_GLM or "cdot" in latex


def test_second_none_wrong_equation_untrusted():
    latex, repair, trusted = coherent(r"7+5=12", None)
    assert latex == r"7+5=12"
    assert repair is None
    assert trusted is False


def test_second_none_student_error_untrusted():
    latex, repair, trusted = coherent(r"7+5=13", None)
    assert latex == r"7+5=13"
    assert repair is None
    assert trusted is False


def test_both_agree_no_repair_trusted():
    eq = r"7+5=13"
    latex, repair, trusted = coherent(eq, eq)
    assert latex == eq
    assert repair is None
    assert trusted is True


def test_power_digit_repair_glm_untrusted():
    fused = r"3^{2}\cdot3^{3}=35"
    power = r"3^{2}\cdot3^{3}=3^{5}"
    latex, repair, trusted = coherent(fused, power)
    assert repair is not None
    assert trusted is False
    assert latex == power