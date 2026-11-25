"""Shared evaluation runner: rescore caches + multiline E2E (Pass 10)."""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.formula_flywheel.level45_live.rescore_pipe import rescore  # noqa: E402

BENCH = ROOT / "bench"
FF = BENCH / "formula_flywheel"

ANCHOR_SYNTH = BENCH / "results_pass4_overnight_synth_anchor.jsonl"
L45_DEV = BENCH / "results_pass6_l45_baseline_dev.jsonl"
L45_HOLDOUT = BENCH / "results_pass4_l45_baseline_holdout.jsonl"

DEFAULT_SUITES = (
    "overnight_synth",
    "level45_dev",
    "level45_holdout",
    "multiline_live",
    "multiline_l45",
    "multiline_multitask_live",
    "kalib_ketten",
)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def _summarize_rescore(name: str, path: Path, *, holdout: bool = False) -> dict:
    full = rescore(path)
    rows = full["rows"]
    n = len(rows)
    pipe_sympy = sum(x["pipe_sympy"] for x in rows) / max(1, n)
    pipe_same = sum(x["pipe_same"] for x in rows) / max(1, n)
    student_rows = [x for x in rows if not x.get("math_correct", True)]
    sep = (
        sum(x["student_error_preserved"] for x in student_rows) / len(student_rows)
        if student_rows
        else 1.0
    )
    lat = [x["tt_ms"] for x in rows if x.get("tt_ms")]
    lat.sort()
    p50 = lat[len(lat) // 2] if lat else None
    p95 = lat[int(len(lat) * 0.95) - 1] if lat else None
    out: dict = {
        "suite": name,
        "n": n,
        "pipe_sympy": pipe_sympy,
        "pipe_same": pipe_same,
        "by_bucket": full["by_bucket"],
        "student_error_preserved": sep,
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "device": "cpu",
        "mode": "rescore_cached_raw",
    }
    if holdout:
        out["holdout"] = True
        out["note"] = "holdout — not for KEEP decisions"
    return out


def _try_tt():
    try:
        from ocr.formula import TexTeller  # noqa: E402

        return TexTeller()
    except Exception:
        return None


def _run_multiline_suite(
    mod_path: str,
    suite_key: str,
    *,
    grouping_only: bool,
    live_tt: bool,
) -> dict:
    mod = importlib.import_module(mod_path)
    tt = None
    use_gt = grouping_only
    if live_tt and not grouping_only:
        tt = _try_tt()
        if tt is None:
            use_gt = True
    block = mod.run_synth(tt=tt, use_gt_latex=use_gt)
    return {
        "suite": suite_key,
        "n_pages": block.get("n_pages"),
        "line_sympy": block.get("line_sympy_rate"),
        "chain_boundary": block.get("chain_boundary_accuracy"),
        "anti_domino_violations": block.get("anti_domino_violations"),
        "student_error_preserved": block.get("student_error_preserved"),
        "latency_ms_p50": block.get("latency_ms_p50"),
        "latency_ms_p95": block.get("latency_ms_p95"),
        "mode": block.get("mode"),
        "device": "cpu" if block.get("mode") == "live_tt" else "n/a",
    }


def _run_kalib() -> dict:
    mod = importlib.import_module("bench.formula_flywheel.multiline_live.run_e2e")
    k = mod.run_kalib_grouping_only()
    return {
        "suite": k["suite"],
        "n_chains": k["n_chains"],
        "chain_boundary": k["chain_boundary_accuracy"],
        "mode": "grouping_only_last_real",
    }


def _run_overnight_live_synth() -> dict | None:
    mod = importlib.import_module("bench.formula_flywheel.level45_live.run_tt_cpu")
    # run_tt_cpu main is heavy; skip unless images present and user asked
    synth_dir = FF / "overnight_synth"
    if not (synth_dir / "pages.jsonl").exists():
        return None
    return None  # live path optional; use --live-synth with run_tt_cpu externally


def run_eval(
    suites: list[str],
    *,
    grouping_only: bool,
    live_tt: bool,
    live_synth: bool,
) -> dict:
    out: dict = {
        "platform": "Linux CPU TexTeller — not comparable to Mac MPS",
        "git_sha": _git_sha(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "datasets": {},
    }
    for name in suites:
        if name == "overnight_synth":
            if live_synth:
                live = _run_overnight_live_synth()
                if live:
                    out["datasets"][name] = live
                    continue
            out["datasets"][name] = _summarize_rescore("overnight_synth", ANCHOR_SYNTH)
        elif name == "level45_dev":
            out["datasets"][name] = _summarize_rescore("level45_live_dev", L45_DEV)
        elif name == "level45_holdout":
            out["datasets"][name] = _summarize_rescore(
                "level45_live_holdout", L45_HOLDOUT, holdout=True
            )
        elif name == "multiline_live":
            out["datasets"][name] = _run_multiline_suite(
                "bench.formula_flywheel.multiline_live.run_e2e",
                "multiline_live",
                grouping_only=grouping_only,
                live_tt=live_tt,
            )
        elif name == "multiline_l45":
            out["datasets"][name] = _run_multiline_suite(
                "bench.formula_flywheel.multiline_l45.run_e2e",
                "multiline_l45",
                grouping_only=grouping_only,
                live_tt=live_tt,
            )
        elif name == "multiline_multitask_live":
            out["datasets"][name] = _run_multiline_suite(
                "bench.formula_flywheel.multiline_multitask_live.run_e2e",
                "multiline_multitask_live",
                grouping_only=grouping_only,
                live_tt=live_tt,
            )
        elif name == "kalib_ketten":
            out["datasets"][name] = _run_kalib()
        else:
            raise SystemExit(f"unknown suite: {name}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--suites",
        default=",".join(DEFAULT_SUITES),
        help=f"comma-separated ({','.join(DEFAULT_SUITES)})",
    )
    ap.add_argument("--out", type=Path, default=BENCH / "results_pass10_shared_eval.json")
    ap.add_argument("--grouping-only", action="store_true", help="multiline: GT latex only")
    ap.add_argument("--live-tt", action="store_true", help="multiline: prefer live TexTeller")
    ap.add_argument("--live-synth", action="store_true", help="overnight_synth: live TT if images exist")
    args = ap.parse_args()
    suites = [s.strip() for s in args.suites.split(",") if s.strip()]
    live_tt = args.live_tt or not args.grouping_only
    payload = run_eval(
        suites,
        grouping_only=args.grouping_only,
        live_tt=live_tt,
        live_synth=args.live_synth,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tsv = args.out.with_suffix(".tsv")
    lines = ["dataset\tmetric\tvalue"]
    for ds, m in sorted(payload["datasets"].items()):
        for k, v in sorted(m.items()):
            if k in ("suite", "note", "holdout", "mode", "device"):
                continue
            if isinstance(v, dict):
                for bk, bv in sorted(v.items()):
                    lines.append(f"{ds}\tby_bucket_{bk}\t{bv}")
            else:
                lines.append(f"{ds}\t{k}\t{v}")
    tsv.write_text("\n".join(lines) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()