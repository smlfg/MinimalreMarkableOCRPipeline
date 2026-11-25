"""Level 4–5 LaTeX variant equivalence baseline (same/agree); documents known gaps."""
import pytest

from ocr.coherence import agree
from ocr.latex import same

# Pairs that should match per Level 4–5 conventions
SHOULD_MATCH = [
    (r"\cos x", r"\cos(x)"),
    (r"\sin^2(x)", r"\sin^{2}(x)"),
    (r"\int x\,dx", r"\int x dx"),
    (r"\int x\,dx", r"\int x \mathrm{d}x"),
    (r"i", r"\mathrm{i}"),
    (r"i^2=-1", r"\mathrm{i}^2=-1"),
    (r"\sin^2(x)+\cos^2(x)=1", r"\sin^{2}(x)+\cos^{2}(x)=1"),
    (r"e", r"\mathrm{e}"),
    (r"e^{1}=e", r"\mathrm{e}^{1}=\mathrm{e}"),
]

KNOWN_GAPS: list[tuple[str, str]] = []


@pytest.mark.parametrize("a,b", SHOULD_MATCH)
def test_variant_same_and_agree(a, b):
    assert same(a, b), f"same failed for {a!r} vs {b!r}"
    assert agree(a, b), f"agree failed for {a!r} vs {b!r}"

