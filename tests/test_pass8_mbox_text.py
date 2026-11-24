"""Pass 8 F2: mbox/text dollar wrappers from live multiline_l45 misses."""
import pytest

from ocr.coherence import tt_postprocess
from ocr.latex import same


@pytest.mark.parametrize(
    "raw,gt",
    [
        (r"\text{($x+y$)}^{3}", r"(x+y)^3"),
        (
            r"\mbox{\small$\frac{1}{2}$}+\mbox{\small$\frac{1}{3}$}",
            r"\frac{1}{2}+\frac{1}{3}",
        ),
        (
            r"= \mbox{\small$\frac{3}{6}$}+\mbox{\small$\frac{2}{6}$}",
            r"=\frac{3}{6}+\frac{2}{6}",
        ),
        (r"\text{($x-2$)($x+2$)}=0", r"(x-2)(x+2)=0"),
    ],
)
def test_mbox_text_unwrap_matches_gt(raw: str, gt: str):
    assert same(gt, tt_postprocess(raw))


def test_student_paren_text_still_wrong():
    """Must not turn a mangled student line into correct GT (Pass 6 guard)."""
    raw = r"\text{($6$}+2\text{)}\cdot 2=4"
    gt = r"(6+2)\cdot 2=4"
    rep = tt_postprocess(raw)
    assert not same(gt, rep)


def test_holdout_integral_rhs_mbox():
    raw = r"\int_{-1}^{1}x^{2}\,dx=\mbox{\small$\frac{2}{3}$}"
    gt = r"\int_{-1}^1 x^2\,dx=\frac{2}{3}"
    assert same(gt, tt_postprocess(raw))