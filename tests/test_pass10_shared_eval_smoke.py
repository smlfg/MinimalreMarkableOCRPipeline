"""Smoke: shared eval rescore path without live TT."""
from pathlib import Path

from bench.formula_flywheel.run_shared_eval import run_eval


def test_shared_eval_rescore_suites():
    payload = run_eval(
        ["overnight_synth", "level45_dev"],
        grouping_only=True,
        live_tt=False,
        live_synth=False,
    )
    assert payload["datasets"]["overnight_synth"]["pipe_sympy"] == 1.0
    assert payload["datasets"]["level45_dev"]["n"] == 72
    assert Path("bench/results_pass6_l45_baseline_dev.jsonl").exists()