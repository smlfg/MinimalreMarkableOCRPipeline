"""Regression tests for Issue #1: OCR uncertain separate from math_status."""
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from ocr.coherence import closed_truth
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


REQUIRED_KEYS = frozenset({"latex", "uncertain", "repair", "math_status", "alt", "cost_s"})


def test_both_agree_wrong_equation(tiny_png):
    r = recognize(tiny_png, tt_stub(r"7+5=13"), glm_stub(r"7+5=13"))
    assert r["uncertain"] is False
    assert r["math_status"] is False
    assert r["repair"] is None
    assert r["latex"] == "7+5=13"


def test_engines_disagree(tiny_png):
    r = recognize(tiny_png, tt_stub(r"7+5=13"), glm_stub(r"7+5=12"))
    assert r["uncertain"] is True
    assert r["math_status"] is False
    assert r["latex"] == "7+5=13"
    assert r["alt"] == "7+5=12"


def test_repair_always_uncertain_even_when_trusted(tiny_png):
    r = recognize(
        tiny_png,
        tt_stub(r"17.3=52"),
        glm_stub(r"17\cdot 3=52"),
    )
    assert r["repair"] is not None
    assert r["uncertain"] is True
    assert "17.3=52" in r["repair"]


def test_output_fields_present(tiny_png):
    r = recognize(tiny_png, tt_stub("1+1=2"), glm_stub("1+1=2"))
    assert REQUIRED_KEYS <= r.keys()


def test_both_agree_correct_equation(tiny_png):
    r = recognize(tiny_png, tt_stub(r"7+5=12"), glm_stub(r"7+5=12"))
    assert r["uncertain"] is False
    assert r["math_status"] is True
    assert r["repair"] is None


@pytest.mark.parametrize(
    "latex,expected",
    [
        ("7+5=13", False),
        ("7+5=12", True),
    ],
)
def test_closed_truth(latex, expected):
    assert closed_truth(latex) is expected