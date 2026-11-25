"""Pass 9 F2: multiline chain boundaries and task markers."""
from __future__ import annotations

import copy

import pytest

from ocr.multiline import group_calculations, label_breaker, trailing_open


def _lines(specs: list[tuple[str, float]]) -> list[dict]:
    out = []
    for i, (tex, y) in enumerate(specs):
        out.append(
            {
                "id": f"l{i + 1}",
                "latex": tex,
                "y": y,
                "h": 72,
                "x": 660,
                "uncertain": False,
            }
        )
    return out


def _chain_lengths(chains: list[dict]) -> list[int]:
    return [len(c["line_ids"]) for c in chains]


def test_tight_gap_independent_equations_split():
    """Over-merge fix: two small calcs on one page stay two chains."""
    lines = _lines(
        [
            (r"x+1=2", 100),
            (r"x=1", 190),
            (r"y+2=5", 280),
            (r"y=3", 370),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [2, 2]


@pytest.mark.parametrize(
    "marker",
    [r"a) x=1", r"b) y=2", r"1) z=3", r"2. w=4"],
)
def test_numeric_and_letter_task_markers_split(marker: str):
    assert label_breaker(marker)
    lines = _lines([(r"x=0", 100), (marker, 280), (r"y=1", 370)])
    chains = group_calculations(lines)
    assert len(chains) >= 2


def test_large_gap_two_chains():
    gap = 130
    lines = _lines(
        [
            (r"3x+5=20", 100),
            (r"x=5", 190),
            (r"4x-7=9", 100 + 190 + gap),
            (r"x=4", 100 + 190 + gap + 90),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [2, 2]


@pytest.mark.parametrize(
    "trail,cont",
    [
        (r"2+3=", r"5"),
        (r"a+b+", r"c"),
        (r"x\cdot", r"y"),
        (r"3-1=", r"2"),
    ],
)
def test_trailing_op_wrap_same_chain(trail: str, cont: str):
    assert trailing_open(trail)
    lines = _lines([(trail, 100), (cont, 190)])
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [2]


def test_anti_domino_uncertain_step_local():
    lines = _lines(
        [
            (r"(6+2)\cdot2=4", 100),
            (r"=16", 190),
        ]
    )
    lines[0]["uncertain"] = True
    before = copy.deepcopy(lines)
    chains = group_calculations(lines)
    assert lines == before
    assert lines[1]["uncertain"] is False
    assert chains[0]["has_uncertain_step"] is True
    assert chains[0]["uncertain_line_indices"] == [0]