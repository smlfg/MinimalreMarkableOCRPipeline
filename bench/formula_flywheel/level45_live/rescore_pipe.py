"""Re-score cached raw TT preds through updated pipe (no re-inference)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ocr.coherence import coherent, tt_postprocess  # noqa: E402
from ocr.latex import same  # noqa: E402
import bench.structure_bench as sb  # noqa: E402


def _pipe(raw: str) -> tuple[str, str | None]:
    t = tt_postprocess(raw)
    fixed, repair, _ = coherent(t, t)
    return fixed, repair


def rescore(cache_path: Path) -> dict:
    rows = [json.loads(ln) for ln in cache_path.read_text().splitlines() if ln.strip()]
    detail = []
    by_bucket: dict[str, list] = defaultdict(list)
    for r in rows:
        raw = r["raw_latex"]
        pipe, repair = _pipe(raw)
        gt = r["gt_latex"]
        sc = sb.score(gt, pipe)
        rec = {
            **r,
            "pipe_latex": pipe,
            "repair": repair,
            "pipe_sympy": bool(sc["sympy_equal"]),
            "pipe_same": bool(same(gt, pipe)),
            "student_error_preserved": pipe == gt if not r.get("math_correct", True) else True,
        }
        detail.append(rec)
        by_bucket[rec["bucket"]].append(rec)
    n = len(detail)
    return {
        "n": n,
        "pipe_sympy": sum(x["pipe_sympy"] for x in detail) / n,
        "by_bucket": {
            b: sum(x["pipe_sympy"] for x in v) / len(v) for b, v in sorted(by_bucket.items())
        },
        "rows": detail,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_jsonl", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = rescore(args.cache_jsonl)
    if args.out:
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("n", "pipe_sympy", "by_bucket")}, indent=2))


if __name__ == "__main__":
    main()