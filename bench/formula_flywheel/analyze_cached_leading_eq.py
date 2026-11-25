"""Chunk B (Pass 2): leading '=' on ketten continuation lines — cached bench only.

Reads last_real / last_synth_real against GT steps. Does not call live OCR.
Writes bench/formula_flywheel/analysis_leading_eq_20261124.json.

chain_bench ocr_hit = ocr.latex.same(read, gt_step) — SymPy-aware, not raw string equality.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ocr.latex import normalize, same  # noqa: E402

HERE = Path(__file__).resolve().parent
KETTEN = HERE / "kalib" / "ketten"
SYNTH_GT = ROOT / "bench" / "synth" / "ketten_gt.jsonl"
OUT_JSON = HERE / "analysis_leading_eq_20261124.json"

LEADING_EQ = re.compile(r"^\s*=\s*")


def has_leading_eq(s: str) -> bool:
    return bool(LEADING_EQ.match(s or ""))


def strip_leading_eq(s: str) -> str:
    return LEADING_EQ.sub("", (s or "").strip(), count=1).strip()


def prepend_leading_eq(s: str) -> str:
    t = (s or "").strip()
    if has_leading_eq(t):
        return t
    return "=" + t


def align_leading_eq(gt: str, rd: str) -> tuple[str, str]:
    """Best-effort alignment so gt/read share the same leading-'=' convention."""
    g, r = (gt or "").strip(), (rd or "").strip()
    if has_leading_eq(g) and not has_leading_eq(r):
        r = prepend_leading_eq(r)
    elif has_leading_eq(r) and not has_leading_eq(g):
        g = prepend_leading_eq(g)
    return g, r


def leading_eq_only_string_diff(gt: str, rd: str) -> bool:
    """Raw/normalized strings differ only by presence of leading '='."""
    g, r = (gt or "").strip(), (rd or "").strip()
    if g == r:
        return False
    if not (has_leading_eq(g) ^ has_leading_eq(r)):
        return False
    ag, ar = align_leading_eq(g, r)
    return ag == ar or normalize(ag) == normalize(ar)


def load_gt(path: Path) -> dict[str, list[str]]:
    return {c["id"]: c["steps"] for c in map(json.loads, open(path, encoding="utf-8"))}


def step_pairs(chain_row: dict, gt_steps: list[str]) -> list[dict]:
    read = chain_row.get("read") or gt_steps
    hits = chain_row.get("ocr_hit") or []
    out = []
    for k in range(1, len(gt_steps)):
        gt, rd = gt_steps[k], read[k] if k < len(read) else ""
        hit = hits[k - 1] if k - 1 < len(hits) else None
        sym = same(gt, rd)
        rd_prep = prepend_leading_eq(rd) if has_leading_eq(gt) and not has_leading_eq(rd) else rd
        gt_prep = prepend_leading_eq(gt) if has_leading_eq(rd) and not has_leading_eq(gt) else gt
        sym_prep_read = same(gt, rd_prep)
        sym_prep_gt = same(gt_prep, rd)
        ag, ar = align_leading_eq(gt, rd)
        sym_aligned = same(ag, ar)
        leq_only = leading_eq_only_string_diff(gt, rd)
        ocr_miss_leq_only = hit is False and sym is False and sym_aligned is True
        out.append(
            {
                "chain_id": chain_row["id"],
                "step_idx": k,
                "gt": gt,
                "read": rd,
                "has_leading_eq_gt": has_leading_eq(gt),
                "has_leading_eq_read": has_leading_eq(rd),
                "leading_eq_only_string": leq_only,
                "sympy_same_gt_read": sym,
                "sympy_same_gt_prepend_read": sym_prep_read,
                "sympy_same_prepend_gt_read": sym_prep_gt,
                "sympy_same_aligned": sym_aligned,
                "normalize_equal": normalize(gt) == normalize(rd),
                "normalize_equal_aligned": normalize(ag) == normalize(ar),
                "ocr_hit": hit,
                "ocr_miss_leading_eq_only": ocr_miss_leq_only,
            }
        )
    return out


def summarize(pairs: list[dict], source: str) -> dict:
    n = len(pairs)
    leq_pairs = [p for p in pairs if p["leading_eq_only_string"]]
    miss_leq = [p for p in pairs if p["ocr_miss_leading_eq_only"]]
    hit_false = [p for p in pairs if p["ocr_hit"] is False]
    sym_fail = [p for p in pairs if not p["sympy_same_gt_read"]]
    sym_fail_other = [
        p
        for p in sym_fail
        if not p["ocr_miss_leading_eq_only"] and not p["leading_eq_only_string"]
    ]
    return {
        "source": source,
        "step_pairs": n,
        "leading_eq_asymmetric_pairs": len(leq_pairs),
        "ocr_hit_false": len(hit_false),
        "ocr_miss_leading_eq_only": len(miss_leq),
        "sympy_fail_gt_read": len(sym_fail),
        "sympy_fail_not_leading_eq_only": len(sym_fail_other),
        "leading_eq_pair_details": [
            {k: p[k] for k in (
                "chain_id",
                "step_idx",
                "gt",
                "read",
                "sympy_same_gt_read",
                "sympy_same_aligned",
                "ocr_hit",
                "ocr_miss_leading_eq_only",
            )}
            for p in pairs
            if p["leading_eq_only_string"] or p["ocr_miss_leading_eq_only"]
        ],
        "ocr_miss_leading_eq_only_details": miss_leq,
        "sympy_fail_other_cause": sym_fail_other,
    }


def analyze_jsonl(jsonl: Path, gt: dict[str, list[str]], source: str) -> dict:
    rows = [json.loads(l) for l in open(jsonl, encoding="utf-8")]
    pairs = []
    for row in rows:
        steps = gt.get(row["id"])
        if not steps:
            continue
        pairs.extend(step_pairs(row, steps))
    return summarize(pairs, source)


def main() -> int:
    gt_kalib = load_gt(KETTEN / "ketten_gt.jsonl")
    gt_synth = load_gt(SYNTH_GT)

    summaries = [
        analyze_jsonl(KETTEN / "last_real.jsonl", gt_kalib, "kalib_last_real"),
        analyze_jsonl(ROOT / "bench" / "synth" / "last_synth_real.jsonl", gt_synth, "synth_last_real"),
    ]

    oracle_path = KETTEN / "last_oracle.jsonl"
    oracle_rows = [json.loads(l) for l in open(oracle_path, encoding="utf-8")]
    oracle_note = {
        "source": "kalib_last_oracle",
        "chains": len(oracle_rows),
        "note": "No read[]/ocr_hit[] in cache; GT steps used as oracle reads by construction.",
        "ocr_hit_definition": "N/A (oracle mode)",
    }

    all_miss = [p for sm in summaries for p in sm["ocr_miss_leading_eq_only_details"]]
    other_fail = [p for sm in summaries for p in sm["sympy_fail_other_cause"]]

    verdict = "REVERT"
    rationale = (
        "ocr_hit uses ocr.latex.same (SymPy); missing leading '=' makes Equality vs bare expr fail, "
        "but aligned prepending '=' recovers match without changing math content. "
        "Auto-prepending '=' in OCR/coherent without continuation context is unsafe; "
        "tutor/validator already treats naked terms as continuations (chain_bench.validator_lines). "
        "Document as bench metric artifact; no product change."
    )
    product_change = False

    payload = {
        "date": "20261124",
        "chunk": "B",
        "verdict": verdict,
        "product_change": product_change,
        "rationale": rationale,
        "chain_bench": {
            "ocr_hit_computation": "hits.append(same(o['latex'], c['steps'][k])) in bench/chain_bench.py",
            "ocr_hit_uses_sympy_same": True,
            "ocr_hit_not_raw_string": True,
            "validator_continuation": (
                "validator_lines: bare terms after line 1 get implicit '=' continuation (K25 comment)"
            ),
        },
        "notes": {
            "K25": (
                "Steps 1–3: read drops leading '='; step 4 read '41' vs GT '=41' preserves student "
                "Additionsfehler (51 correct); never change 41→51."
            ),
        },
        "oracle": oracle_note,
        "summaries": summaries,
        "totals": {
            "ocr_miss_leading_eq_only": len(all_miss),
            "sympy_fail_not_leading_eq_only": len(other_fail),
            "kalib_K25_steps_affected": sum(
                1
                for p in all_miss
                if p["chain_id"] == "K25"
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=== Chunk B: leading '=' on cached ketten reads ===")
    print(
        f"chain_bench ocr_hit = same(read, gt) — SymPy same(), not raw string"
    )
    for sm in summaries:
        print(f"\n[{sm['source']}] step_pairs={sm['step_pairs']}")
        print(f"  leading '=' asymmetric:     {sm['leading_eq_asymmetric_pairs']}")
        print(f"  ocr_hit=False:              {sm['ocr_hit_false']}")
        print(f"  ocr_miss leading '=' ONLY:  {sm['ocr_miss_leading_eq_only']}")
        print(f"  sympy fail (gt,read):       {sm['sympy_fail_gt_read']}")
        print(f"  sympy fail, other cause:    {sm['sympy_fail_not_leading_eq_only']}")
        for d in sm["leading_eq_pair_details"]:
            print(
                f"    {d['chain_id']} step {d['step_idx']}: "
                f"sympy={d['sympy_same_gt_read']} aligned={d['sympy_same_aligned']} "
                f"ocr_hit={d['ocr_hit']} leq_only_miss={d['ocr_miss_leading_eq_only']} "
                f"gt={d['gt']!r} read={d['read']!r}"
            )

    print(f"\nVERDICT: {verdict} (product_change={product_change})")
    print(f"  {rationale}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())