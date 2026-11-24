"""Pass 9 multiline_multitask_live E2E."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ocr.coherence import coherent, tt_postprocess  # noqa: E402
from ocr.latex import same  # noqa: E402
from ocr.pipeline import assemble_page  # noqa: E402

HERE = Path(__file__).resolve().parent
SUITE_NAME = "multiline_multitask_live"


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(len(s) * p) - 1))
    return s[i]


def _chain_match(pred: list[list[str]], gt: list[list[str]]) -> bool:
    return [sorted(c) for c in pred] == [sorted(c) for c in gt]


def run_synth(tt=None, use_gt_latex: bool = False) -> dict:
    pages = [json.loads(ln) for ln in (HERE / "pages.jsonl").read_text().splitlines() if ln.strip()]
    latencies: list[float] = []
    chain_ok = 0
    line_ok = 0
    line_total = 0
    domino_violations = 0
    student_ok = 0
    student_total = 0
    details = []

    for page in pages:
        rec_lines = []
        for spec in page["lines"]:
            if use_gt_latex or tt is None:
                latex = spec["latex_gt"]
                repair = None
                uncertain = False
                ms = 0.0
            else:
                raw, _ms = tt(str(HERE / spec["png"]))
                ms = _ms
                t = tt_postprocess(raw)
                latex, repair, _ = coherent(t, t)
                uncertain = repair is not None
            latencies.append(ms)
            rec = {
                "id": spec["id"],
                "latex": latex,
                "y": spec["y"],
                "h": spec["h"],
                "x": spec["x"],
                "uncertain": uncertain,
                "repair": repair,
            }
            rec_lines.append(rec)
            line_total += 1
            if same(spec["latex_gt"], latex):
                line_ok += 1
            if not spec.get("math_correct", True):
                student_total += 1
                if same(spec["latex_gt"], latex):
                    student_ok += 1

        before = json.dumps(rec_lines)
        assembled = assemble_page(rec_lines)
        assert json.dumps(assembled["lines"]) == before
        chains = assembled["calculations"]
        pred_lists = [ch["line_ids"] for ch in chains]
        gt = page["chains_gt"]
        ok = _chain_match(pred_lists, gt)
        chain_ok += int(ok)
        if any(ch.get("has_uncertain_step") for ch in chains):
            n_unc = sum(1 for ln in rec_lines if ln.get("uncertain"))
            if n_unc == 0:
                domino_violations += 1
        details.append({"page": page["id"], "chain_match": ok, "chains_pred": pred_lists, "chains_gt": gt})

    return {
        "suite": SUITE_NAME,
        "n_pages": len(pages),
        "line_sympy_rate": line_ok / max(1, line_total),
        "chain_boundary_accuracy": chain_ok / max(1, len(pages)),
        "anti_domino_violations": domino_violations,
        "student_error_preserved": student_ok / max(1, student_total) if student_total else 1.0,
        "latency_ms_p50": _percentile(latencies, 0.5),
        "latency_ms_p95": _percentile(latencies, 0.95),
        "mode": "gt_latex" if (use_gt_latex or tt is None) else "live_tt",
        "details": details,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grouping-only", action="store_true", help="use GT latex per line (no TT)")
    ap.add_argument("--out", default=str(ROOT / "bench/results_pass9_multiline_multitask_live.json"))
    args = ap.parse_args()

    tt = None
    if not args.grouping_only:
        try:
            from ocr.formula import TexTeller  # noqa: E402

            tt = TexTeller()
        except Exception as exc:  # pragma: no cover
            print(f"TexTeller unavailable ({exc}); falling back to gt_latex grouping path")
            args.grouping_only = True

    synth = run_synth(tt=tt, use_gt_latex=args.grouping_only)
    payload = {"synth": synth, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tsv = out.with_suffix(".tsv")
    tsv.write_text(
        "metric\tvalue\n"
        f"chain_boundary\t{synth['chain_boundary_accuracy']:.4f}\n"
        f"line_sympy\t{synth['line_sympy_rate']:.4f}\n"
        f"anti_domino\t{synth['anti_domino_violations']}\n"
        f"student_error_preserved\t{synth['student_error_preserved']:.4f}\n"
    )
    print(json.dumps(synth, indent=2))


if __name__ == "__main__":
    main()