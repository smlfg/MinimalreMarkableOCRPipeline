"""Pass 5: multi-line calculation grouping."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ocr.multiline import (
    group_calculations,
    leading_continuation,
    lines_from_ketten_row,
    transform_annotation_line,
)
from ocr.pipeline import assemble_page

ROOT = Path(__file__).resolve().parents[1]
KETTEN_GT = ROOT / "bench/formula_flywheel/kalib/ketten/ketten_gt.jsonl"
LAST_REAL = ROOT / "bench/formula_flywheel/kalib/ketten/last_real.jsonl"


def _lines(specs: list[tuple[str, float]]) -> list[dict]:
    """(latex, y) tuples with uniform height."""
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


def test_cube_expansion_chain():
    lines = _lines(
        [
            (r"(x+y)^3", 100),
            (r"=x^3+3x^2y+3xy^2+y^3", 190),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [2]


def test_cube_chain_without_bbox_y():
    lines = [
        {"id": "l1", "latex": r"(x+y)^3", "uncertain": False},
        {"id": "l2", "latex": r"=(x+y)(x+y)^2", "uncertain": False},
        {"id": "l3", "latex": r"=x^3+y^3", "uncertain": False},
    ]
    chains = group_calculations(lines)
    assert len(chains) == 1
    assert len(chains[0]["line_ids"]) == 3


def test_trailing_plus_and_equals_links():
    lines = _lines(
        [
            (r"\frac{1}{2}+\frac{1}{3}+", 100),
            (r"\frac{2}{6}", 190),
            (r"=\frac{5}{6}", 280),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [3]


def test_k25_student_41_no_domino_uncertain():
    lines = _lines(
        [
            (r"17\cdot3", 210),
            (r"3\cdot10+3\cdot7", 316),
            (r"30+21", 422),
            (r"41", 528),
        ]
    )
    before = copy.deepcopy(lines)
    chains = group_calculations(lines)
    assert lines == before
    assert _chain_lengths(chains) == [4]
    assert chains[0]["has_uncertain_step"] is False
    assert chains[0]["uncertain_line_indices"] == []


def test_anti_domino_uncertain_stays_local():
    lines = _lines(
        [
            (r"3x+5=20", 100),
            (r"=3x=15", 190),
            (r"x=5", 280),
        ]
    )
    lines[1]["uncertain"] = True
    chains = group_calculations(lines)
    assert lines[0]["uncertain"] is False
    assert lines[2]["uncertain"] is False
    assert chains[0]["has_uncertain_step"] is True
    assert chains[0]["uncertain_line_indices"] == [1]


def test_two_exercises_on_same_page_separate():
    gap = 130
    lines = _lines(
        [
            (r"3x+5=20", 100),
            (r"=3x=15", 190),
            (r"x=5", 280),
            (r"4x-7=2x+3", 100 + 280 + gap),
            (r"=2x=-4", 100 + 280 + gap + 90),
            (r"x=-2", 100 + 280 + gap + 180),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [3, 3]


def test_label_breaker_splits():
    lines = _lines(
        [
            (r"x=1", 100),
            (r"Aufgabe 2", 280),
            (r"y=2", 370),
        ]
    )
    chains = group_calculations(lines)
    assert len(chains) >= 2


def test_assemble_page_adds_calculations():
    lines = _lines([(r"a+b", 10), (r"=c", 100)])
    page = assemble_page(lines, page_id="test")
    assert "calculations" in page
    assert len(page["calculations"]) == 1


@pytest.mark.parametrize(
    "kid,expected_len",
    [
        ("K01", 3),
        ("K20", 3),
        ("K25", 4),
        ("K08", 4),
    ],
)
def test_kalib_ketten_grouping_lengths(kid: str, expected_len: int):
    gt = {r["id"]: r for r in map(json.loads, KETTEN_GT.read_text().splitlines())}[kid]
    real = {r["id"]: r for r in map(json.loads, LAST_REAL.read_text().splitlines())}[kid]
    lines = lines_from_ketten_row(real, gt)
    chains = group_calculations(lines)
    assert len(chains) == 1
    assert len(chains[0]["line_ids"]) == expected_len


@pytest.mark.parametrize(
    "lead",
    [
        r"\Rightarrow 5",
        r"\implies x=1",
        r"\iff a=b",
        r"=> 42",
        r"<=> 0",
        r"\approx 3.14",
        r"\equiv 1",
        r"\sim N(0,1)",
    ],
)
def test_lead_continuation_operators(lead: str):
    assert leading_continuation(lead)


def test_integral_eval_chain_with_annotations():
    lines = _lines(
        [
            (r"\int_0^1 x\,dx", 100),
            (r"| :\quad x^2", 190),
            (r"=\frac{1}{2}", 280),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [3]


def test_transform_annotation_mid_chain():
    lines = _lines(
        [
            (r"5x+10=25", 100),
            (r"| - 3x", 190),
            (r"=15", 280),
            (r"x=3", 370),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [4]


def test_trailing_pipe_does_not_break_next_equals():
    lines = _lines(
        [
            (r"x+2=7 | : 2", 100),
            (r"=x+2=5", 190),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [2]


def test_mid_transform_annotation_line():
    assert transform_annotation_line(r"| + 5")
    assert transform_annotation_line(r"\mid - 3x")
    lines = _lines(
        [
            (r"a=b", 100),
            (r"\mid + 5", 190),
            (r"=c", 280),
        ]
    )
    chains = group_calculations(lines)
    assert _chain_lengths(chains) == [3]


def test_all_kalib_chains_single_group_per_row():
    gt_map = {r["id"]: r for r in map(json.loads, KETTEN_GT.read_text().splitlines())}
    misses = []
    for row in map(json.loads, LAST_REAL.read_text().splitlines()):
        kid = row["id"]
        lines = lines_from_ketten_row(row, gt_map[kid])
        chains = group_calculations(lines)
        n = len(row["read"])
        if len(chains) != 1 or len(chains[0]["line_ids"]) != n:
            misses.append(kid)
    assert misses == [], f"grouping failed for {misses}"