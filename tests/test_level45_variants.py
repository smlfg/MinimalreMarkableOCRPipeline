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
]

# Known baseline failures — do not assert match until product changes
KNOWN_GAPS = [
    (r"e", r"\mathrm{e}"),
]


@pytest.mark.parametrize("a,b", SHOULD_MATCH)
def test_variant_same_and_agree(a, b):
    assert same(a, b), f"same failed for {a!r} vs {b!r}"
    assert agree(a, b), f"agree failed for {a!r} vs {b!r}"


@pytest.mark.parametrize("a,b", KNOWN_GAPS)
def test_variant_baseline_gap_documented(a, b):
    """Baseline: \\mathrm{e} not yet equivalent to e (see level45 diag builtin_variant)."""
    assert same(a, b) is False
    assert agree(a, b) is False