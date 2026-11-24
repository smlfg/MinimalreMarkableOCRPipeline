"""Pass 8 F1: thin-space artifacts before continuation equals."""
import pytest

from ocr.coherence import tt_lead_eq_space_artifacts, tt_postprocess
from ocr.latex import same
from ocr.multiline import leading_continuation


@pytest.mark.parametrize(
    "raw,expected_lead",
    [
        (r"\,=\!2^{5}", r"=2^{5}"),
        (r"\,=32", r"=32"),
        (r"\!=x", r"=x"),
    ],
)
def test_lead_continuation_after_postprocess(raw: str, expected_lead: str):
    rep = tt_postprocess(raw)
    assert same(expected_lead, rep)
    assert leading_continuation(rep)


def test_lead_eq_identity():
    assert tt_lead_eq_space_artifacts(r"2^{3}\cdot2^{2}") == r"2^{3}\cdot2^{2}"


def test_mid_thin_eq_normalization():
    assert same(r"dx=6", tt_postprocess(r"dx\,{=6}"))