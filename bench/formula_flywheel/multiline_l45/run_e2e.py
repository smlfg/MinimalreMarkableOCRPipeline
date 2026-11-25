"""Pass 5 multiline E2E: per-line TT (optional) + grouping vs GT chains."""
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
from ocr.multiline import group_calculations, lines_from_ketten_row  # noqa: E402
from ocr.pipeline import assemble_page  # noqa: E402
import bench.structure_bench as sb  # noqa: E402

HERE = Path(__file__).resolve().parent
SUITE_NAME = "multiline_l45"
KETTEN_GT = ROOT / "bench/formula_flywheel/kalib/ketten/ketten_gt.jsonl"
LAST_REAL = ROOT / "bench/formula_flywheel/kalib/ketten/last_real.jsonl"


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = max(0, min(len(s) - 1, int(len(s) * p) - 1))
    return s[i]


def _chain_match(pred: list[list[str]], gt: list[list[str]]) -> bool:
    return [sorted(c) for c in pred] == [sorted(c) for c in gt]


def _pred_chains(line_ids: list[str], chains: list[dict]) -> list[list[str]]:
    id_set = {lid: i for i, lid in enumerate(line_ids)}
    out: list[list[str]] = []
    for ch in chains:
        out.append([line_ids[id_set[lid]] for lid in ch["line_ids"] if lid in id_set])
    return out


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
            t0 = time.perf_counter()
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
        line_ids = [l["id"] for l in rec_lines]
        pred = [[c["line_ids"] for c in chains]]
        # flatten for comparison — list of line_id lists
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


def run_kalib_grouping_only() -> dict:
    gt_map = {r["id"]: r for r in map(json.loads, KETTEN_GT.read_text().splitlines())}
    ok = 0
    total = 0
    for row in map(json.loads, LAST_REAL.read_text().splitlines()):
        total += 1
        lines = lines_from_ketten_row(row, gt_map[row["id"]])
        chains = group_calculations(lines)
        n = len(row["read"])
        if len(chains) == 1 and len(chains[0]["line_ids"]) == n:
            ok += 1
    return {"suite": "kalib_ketten_grouping", "n_chains": total, "chain_boundary_accuracy": ok / max(1, total)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grouping-only", action="store_true", help="use GT latex per line (no TT)")
    ap.add_argument("--out", default=str(ROOT / "bench/results_pass7_multiline_l45.json"))
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
    kalib = run_kalib_grouping_only()
    payload = {"synth": synth, "kalib_grouping": kalib, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tsv = out.with_suffix(".tsv")
    tsv.write_text(
        "metric\tvalue\n"
        f"chain_boundary_synth\t{synth['chain_boundary_accuracy']:.4f}\n"
        f"line_sympy_synth\t{synth['line_sympy_rate']:.4f}\n"
        f"kalib_grouping\t{kalib['chain_boundary_accuracy']:.4f}\n"
        f"anti_domino\t{synth['anti_domino_violations']}\n"
    )
    print(json.dumps({k: payload[k] for k in ("synth", "kalib_grouping")}, indent=2))


if __name__ == "__main__":
    main()