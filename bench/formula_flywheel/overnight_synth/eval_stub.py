"""Offline harness: oracle + fused-digit corruption stubs on overnight_synth dev split."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import structure_bench as sb
from ocr.formula import recognize

HERE = Path(__file__).resolve().parent


def _load_dev():
    rows = []
    for line in (HERE / "dev.jsonl").read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _fused_corrupt(latex: str) -> str:
    """Collapse single-digit powers to fused digits (TexTeller-style artefact)."""
    return re.sub(r"(\d)\^\{(\d)\}", r"\1\2", latex)


def _run(rows, label: str, tt_fn, glm_fn) -> None:
    ok = 0
    for r in rows:
        png = HERE / r["png"]
        if not png.exists():
            print(f"skip {r['id']}: missing {png}")
            continue
        pred = recognize(png, tt_fn(r["gt_latex"]), glm_fn(r["gt_latex"]))["latex"]
        sc = sb.score(r["gt_latex"], pred)
        ok += int(bool(sc["sympy_equal"]))
    rate = ok / len(rows) if rows else 0.0
    print(f"{label}: sympy_equal {ok}/{len(rows)} = {rate:.1%}")


def main() -> None:
    rows = _load_dev()
    print(f"dev rows: {len(rows)}")

    def oracle(latex):
        def _e(_):
            return latex, 0.0
        return _e

    _run(rows, "oracle (TT=GLM=gt)", oracle, oracle)

    def tt_fused(gt):
        def _e(_):
            return _fused_corrupt(gt), 0.0
        return _e

    _run(rows, "fused TT + GLM=gt (coherence repair path)", tt_fused, oracle)


if __name__ == "__main__":
    main()