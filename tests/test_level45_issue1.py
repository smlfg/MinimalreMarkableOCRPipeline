"""Issue #1 on Level 4–5 buckets: both engines agree on gt; student errors must not be OCR-trusted away."""
import json
from pathlib import Path

import pytest
from PIL import Image

from ocr.coherence import closed_truth
from ocr.formula import recognize

LEVEL45 = Path(__file__).resolve().parents[1] / "bench" / "formula_flywheel" / "level45"


@pytest.fixture
def tiny_png(tmp_path):
    p = tmp_path / "line.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(p)
    return p


def _stub(latex):
    def _tt(_):
        return latex, 0.0
    return _tt


def _glm(latex):
    def _g(_):
        return latex, 0.0
    return _g


CASES = [
    (r"\cos(\pi)=1", "trig", False),
    (r"\int_0^1 x\,dx=1", "integral", False),
    (r"e^{i\pi}=1", "special", False),
    (
        r"\begin{pmatrix}1&2\\3&4\end{pmatrix}=\begin{pmatrix}1&2\\3&5\end{pmatrix}",
        "matrix",
        False,
    ),
]


@pytest.mark.parametrize("latex,bucket,math_correct", CASES)
def test_issue1_false_student_preserved(tiny_png, latex, bucket, math_correct):
    r = recognize(tiny_png, _stub(latex), _glm(latex))
    assert r["uncertain"] is False
    assert r["repair"] is None
    assert r["latex"] == latex
    ct = closed_truth(latex)
    if ct is False:
        assert r["math_status"] is False
    assert math_correct is False


def test_issue1_correct_trig_closed(tiny_png):
    latex = r"\cos(\pi)=-1"
    r = recognize(tiny_png, _stub(latex), _glm(latex))
    assert r["uncertain"] is False
    assert r["math_status"] is True


@pytest.mark.skipif(not (LEVEL45 / "dev.jsonl").exists(), reason="run level45/gen.py first")
def test_issue1_dev_jsonl_sample():
    """Spot-check a few committed dev rows with real tiny png if present."""
    rows = [json.loads(l) for l in (LEVEL45 / "dev.jsonl").read_text().splitlines() if l.strip()]
    wrong = [r for r in rows if not r["math_correct"] and closed_truth(r["gt_latex"]) is False]
    assert wrong, "expected some sympy-checkable false dev equations"
    r0 = wrong[0]
    png = LEVEL45 / r0["png"]
    if not png.exists():
        pytest.skip("PNGs not generated")
    rec = recognize(png, _stub(r0["gt_latex"]), _glm(r0["gt_latex"]))
    assert rec["uncertain"] is False
    assert rec["math_status"] is False
    assert rec["latex"] == r0["gt_latex"]