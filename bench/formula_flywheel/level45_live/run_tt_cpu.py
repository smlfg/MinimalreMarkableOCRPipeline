"""Live TexTeller CPU eval for Pass 4 (raw + product pipe metrics)."""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ocr.coherence import coherent, tt_postprocess  # noqa: E402
from ocr.formula import TexTeller  # noqa: E402
from ocr.latex import same  # noqa: E402
import bench.structure_bench as sb  # noqa: E402
from bench.formula_flywheel import prepare as fw_prepare  # noqa: E402

HERE = Path(__file__).resolve().parent
BENCH = ROOT / "bench"


def _pipe(raw: str) -> tuple[str, str | None]:
    t = tt_postprocess(raw)
    fixed, repair, _ = coherent(t, t)
    return fixed, repair


def _score_row(gt: str, pred: str) -> dict:
    sc = sb.score(gt, pred)
    return {
        "same": bool(same(gt, pred)),
        "sympy_equal": bool(sc["sympy_equal"]),
        "latex_edit_sim": float(sc["latex_edit_sim"]),
        "cer": 1.0 - float(sc["latex_edit_sim"]),
        "char_acc": fw_prepare.char_acc(gt, pred),
    }


def _load_split(suite_dir: Path, split: str) -> list[dict]:
    path = suite_dir / f"{split}.jsonl"
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(len(s) * p) - 1))
    return s[i]


def run_suite(
    suite_name: str,
    suite_dir: Path,
    split: str,
    out_prefix: str,
    limit: int | None = None,
) -> dict:
    rows = _load_split(suite_dir, split)
    if limit:
        rows = rows[:limit]

    tt_py = ROOT / ".venv_tt" / "bin" / "python"
    if not tt_py.exists():
        raise SystemExit("missing .venv_tt")
    cold = subprocess.run(
        [str(tt_py), "-c", "import torch; print(torch.__version__)"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    tt = TexTeller()
    t0_load = time.perf_counter()

    detail: list[dict] = []
    lats: list[float] = []
    by_bucket: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        png = suite_dir / row["png"]
        raw, dt_s = tt(str(png))
        ms = dt_s * 1000.0
        lats.append(ms)
        pipe, repair = _pipe(raw)
        raw_m = _score_row(row["gt_latex"], raw)
        pipe_m = _score_row(row["gt_latex"], pipe)
        stud_ok = True
        if not row.get("math_correct", True):
            stud_ok = pipe == row["gt_latex"]
        rec = {
            "id": row["id"],
            "bucket": row.get("bucket", "unknown"),
            "split": row.get("split", split),
            "math_correct": row.get("math_correct", True),
            "gt_latex": row["gt_latex"],
            "raw_latex": raw,
            "pipe_latex": pipe,
            "repair": repair,
            "tt_ms": ms,
            "raw_same": raw_m["same"],
            "raw_sympy": raw_m["sympy_equal"],
            "pipe_same": pipe_m["same"],
            "pipe_sympy": pipe_m["sympy_equal"],
            "cer_raw": raw_m["cer"],
            "cer_pipe": pipe_m["cer"],
            "student_error_preserved": stud_ok,
        }
        detail.append(rec)
        by_bucket[rec["bucket"]].append(rec)

    failures = [r for r in detail if not r["pipe_sympy"]]

    def _agg(items: list[dict]) -> dict:
        n = len(items)
        if not n:
            return {"n": 0}
        return {
            "n": n,
            "raw_sympy": sum(x["raw_sympy"] for x in items) / n,
            "pipe_sympy": sum(x["pipe_sympy"] for x in items) / n,
            "pipe_same": sum(x["pipe_same"] for x in items) / n,
            "student_error_preserved": sum(x["student_error_preserved"] for x in items) / n,
            "mean_cer_pipe": sum(x["cer_pipe"] for x in items) / n,
        }

    bucket_summary = {b: _agg(v) for b, v in sorted(by_bucket.items())}
    false_rows = [r for r in detail if not r["math_correct"]]
    stud_rate = (
        sum(r["student_error_preserved"] for r in false_rows) / len(false_rows) if false_rows else 1.0
    )

    summary = {
        "suite": suite_name,
        "split": split,
        "device": "cpu",
        "platform_note": "Linux CPU TexTeller — not comparable to Mac MPS",
        "n": len(detail),
        "cold_load_s": round(time.perf_counter() - t0_load, 3),
        "tt_torch": cold.stdout.strip() if cold.returncode == 0 else None,
        "latency_ms_tt_only": {
            "p50": round(_percentile(lats, 0.5), 1),
            "p95": round(_percentile(lats, 0.95), 1),
            "mean": round(statistics.mean(lats), 1) if lats else 0,
        },
        "raw_sympy": sum(r["raw_sympy"] for r in detail) / max(len(detail), 1),
        "pipe_sympy": sum(r["pipe_sympy"] for r in detail) / max(len(detail), 1),
        "student_error_preserved_rate": stud_rate,
        "by_bucket": bucket_summary,
        "failure_count_pipe": len(failures),
    }

    out_json = BENCH / f"{out_prefix}.json"
    out_tsv = BENCH / f"{out_prefix}.tsv"
    out_jsonl = BENCH / f"{out_prefix}.jsonl"
    fail_json = BENCH / f"{out_prefix}_failures.json"

    payload = {"summary": summary, "rows": detail}
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    out_jsonl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in detail))
    fail_json.write_text(json.dumps(failures, indent=2, ensure_ascii=False) + "\n")

    tsv_lines = [
        "id\tbucket\tmath_correct\tms\traw_sympy\tpipe_sympy\tstudent_ok\tgt\traw\tpipe"
    ]
    for r in detail:
        tsv_lines.append(
            f"{r['id']}\t{r['bucket']}\t{r['math_correct']}\t{r['tt_ms']:.1f}\t"
            f"{r['raw_sympy']}\t{r['pipe_sympy']}\t{r['student_error_preserved']}\t"
            f"{r['gt_latex']}\t{r['raw_latex']}\t{r['pipe_latex']}"
        )
    hdr = [
        f"metric\t{out_prefix}",
        f"suite\t{suite_name}",
        f"split\t{split}",
        f"n\t{summary['n']}",
        f"raw_sympy\t{summary['raw_sympy']:.4f}",
        f"pipe_sympy\t{summary['pipe_sympy']:.4f}",
        f"student_error_preserved\t{summary['student_error_preserved_rate']:.4f}",
        f"tt_p50_ms\t{summary['latency_ms_tt_only']['p50']}",
        f"tt_p95_ms\t{summary['latency_ms_tt_only']['p95']}",
    ]
    for b, agg in bucket_summary.items():
        hdr.append(f"bucket_{b}_pipe_sympy\t{agg['pipe_sympy']:.4f}")
    out_tsv.write_text("\n".join(hdr + [""] + tsv_lines) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"wrote {out_json.relative_to(ROOT)}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="level45_live", choices=("level45_live", "overnight_synth"))
    ap.add_argument("--split", default="dev")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--out-prefix",
        default=None,
        help="basename under bench/ (default pass4_<suite>_<split>)",
    )
    args = ap.parse_args()
    suite_dir = ROOT / "bench" / "formula_flywheel" / args.suite
    if args.suite == "level45_live":
        default_out = (
            "results_pass4_l45_baseline_dev"
            if args.split == "dev"
            else f"results_pass4_l45_baseline_{args.split}"
        )
    else:
        default_out = "results_pass4_overnight_synth_anchor"
    prefix = args.out_prefix or default_out
    run_suite(args.suite, suite_dir, args.split, prefix, args.limit)


if __name__ == "__main__":
    main()