"""Experiment 1: fused exponent digits — repair only when GLM corroborates."""
import pytest
from PIL import Image

from ocr.formula import recognize


@pytest.fixture
def tiny_png(tmp_path):
    p = tmp_path / "line.png"
    Image.new("RGB", (4, 4), color=(255, 255, 255)).save(p)
    return p


def tt_stub(latex, cost=0.01):
    def _tt(path):
        return latex, cost
    return _tt


def glm_stub(latex, cost=0.01):
    def _glm(img):
        return latex, cost
    return _glm


FUSED = r"3^{2}\cdot3^{3}=35"
POWER = r"3^{2}\cdot3^{3}=3^{5}"


def test_tt_fused_glm_power_repairs(tiny_png):
    r = recognize(tiny_png, tt_stub(FUSED), glm_stub(POWER))
    assert r["latex"] == POWER
    assert r["repair"] is not None
    assert r["uncertain"] is True
    assert r["math_status"] is True


def test_both_fused_wrong_unchanged(tiny_png):
    r = recognize(tiny_png, tt_stub(FUSED), glm_stub(FUSED))
    assert r["latex"] == FUSED
    assert r["repair"] is None
    assert r["uncertain"] is False
    assert r["math_status"] is False


def test_both_agree_wrong_equation_regression(tiny_png):
    r = recognize(tiny_png, tt_stub(r"7+5=13"), glm_stub(r"7+5=13"))
    assert r["latex"] == "7+5=13"
    assert r["repair"] is None
    assert r["uncertain"] is False
    assert r["math_status"] is False


def test_both_agree_digit_swap_regression(tiny_png):
    r = recognize(tiny_png, tt_stub(r"17+71=88"), glm_stub(r"17+71=88"))
    assert r["latex"] == "17+71=88"
    assert r["repair"] is None
    assert r["uncertain"] is False


def test_no_power_invention_without_glm(tiny_png):
    eq = r"5x=35"
    r = recognize(tiny_png, tt_stub(eq), glm_stub(eq))
    assert r["latex"] == eq
    assert r["repair"] is None