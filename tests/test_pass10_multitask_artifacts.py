"""Pass 10 F1–F3: multiline_multitask_live TT artifact unwraps."""
import pytest

from ocr.coherence import tt_postprocess
from ocr.latex import same


@pytest.mark.parametrize(
    "raw,gt",
    [
        (r"b\text{) }2b-1=7", r"b)\ 2b-1=7"),
        (r"1\text{)} \text{ }c+d=5", r"1)\ c+d=5"),
    ],
)
def test_f1_text_marker_and_empty_text(raw: str, gt: str):
    assert same(gt, tt_postprocess(raw))


def test_f2_raisebox_mbox_small_dollar():
    raw = r"\mbox{\raisebox{-1.72pt}{\small$\frac{2}{4}$}}"
    gt = r"\frac{2}{4}"
    assert same(gt, tt_postprocess(raw))


def test_f3_array_single_cell_trailing_backslash():
    raw = (
        r"\begin{array}"
        "\n{c}"
        r"\frac{1}{4}+\frac{1}{4}\,+\\"
        "\n\\end{array}"
    )
    gt = r"\frac{1}{4}+\frac{1}{4}+"
    assert same(gt, tt_postprocess(raw))