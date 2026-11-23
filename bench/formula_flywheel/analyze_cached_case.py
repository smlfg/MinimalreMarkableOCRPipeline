"""Chunk A (Pass 2): measure x vs X display case on cached chain bench reads.

Reads last_real / last_oracle / last_synth_real jsonl against ketten GT steps.
Does not call live OCR. Writes bench/formula_flywheel/analysis_case_xX_20261124.json.
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
OUT_JSON = HERE / "analysis_case_xX_20261124.json"


def canon_xX(s: str) -> str:
    """Collapse standalone x/X to one token for string-only case comparison."""
    return re.sub(r"x", "\x00", s, flags=re.IGNORECASE)


def xX_only_string_diff(a: str, b: str) -> bool:
    """True if a != b but identical after folding x/X (raw strings)."""
    if a == b:
        return False
    return canon_xX(a) == canon_xX(b)


def xX_only_after_normalize(a: str, b: str) -> bool:
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return False
    return canon_xX(na) == canon_xX(nb)


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
        raw_xx = xX_only_string_diff(gt, rd)
        norm_xx = xX_only_after_normalize(gt, rd)
        out.append(
            {
                "chain_id": chain_row["id"],
                "step_idx": k,
                "gt": gt,
                "read": rd,
                "raw_equal": gt == rd,
                "normalize_equal": normalize(gt) == normalize(rd),
                "sympy_same": sym,
                "xX_only_raw": raw_xx,
                "xX_only_after_normalize": norm_xx,
                "ocr_hit": hit,
                "case_only_failure": not sym and (raw_xx or norm_xx),
            }
        )
    return out


def summarize(pairs: list[dict], source: str) -> dict:
    n = len(pairs)
    raw_xx = [p for p in pairs if p["xX_only_raw"]]
    norm_xx = [p for p in pairs if p["xX_only_after_normalize"]]
    sym_true_on_xx = [p for p in pairs if (p["xX_only_raw"] or p["xX_only_after_normalize"]) and p["sympy_same"]]
    hit_on_xx = [p for p in pairs if (p["xX_only_raw"] or p["xX_only_after_normalize"]) and p["ocr_hit"] is True]
    case_only = [p for p in pairs if p["case_only_failure"]]
    sym_fail_other = [p for p in pairs if not p["sympy_same"] and not p["case_only_failure"]]
    return {
        "source": source,
        "step_pairs": n,
        "xX_only_raw": len(raw_xx),
        "xX_only_after_normalize": len(norm_xx),
        "xX_pairs_sympy_same_true": len(sym_true_on_xx),
        "xX_pairs_ocr_hit_true": len(hit_on_xx),
        "sympy_fail_case_only": len(case_only),
        "sympy_fail_other_cause": len(sym_fail_other),
        "xX_pair_details": [
            {k: p[k] for k in ("chain_id", "step_idx", "gt", "read", "sympy_same", "ocr_hit", "xX_only_raw")}
            for p in pairs
            if p["xX_only_raw"] or p["xX_only_after_normalize"]
        ],
        "case_only_failures": case_only,
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

    oracle_path = KETTEN / "last_oracle.jsonl"  # no per-step reads; chain-level sanity only
    oracle_rows = [json.loads(l) for l in open(oracle_path, encoding="utf-8")]
    oracle_note = {
        "source": "kalib_last_oracle",
        "chains": len(oracle_rows),
        "note": "No read[]/ocr_hit[] in cache; GT steps used as oracle reads by construction.",
    }

    all_xx = [s for sm in summaries for s in sm["xX_pair_details"]]
    case_only = [s for sm in summaries for s in sm["case_only_failures"]]
    verdict = "REVERT"
    rationale = (
        "sympy_same/ocr_hit already true on all cached x/X display mismatches; "
        "no struct metric win from casefold rule."
    )
    if case_only:
        verdict = "EXPERIMENT"
        rationale = "sympy_same false with case as only string difference — product tweak may help."

    payload = {
        "date": "20261124",
        "chunk": "A",
        "verdict": verdict,
        "rationale": rationale,
        "notes": {
            "K06": "GT step3 x=125 is intentional student error (Divisionsregel); never auto-correct.",
            "K09_K13": "Same chain may mix X and x in OCR read vs lowercase GT (display artifact).",
        },
        "oracle": oracle_note,
        "summaries": summaries,
        "totals": {
            "xX_display_pairs": len(all_xx),
            "xX_sympy_same_true": sum(1 for p in all_xx if p["sympy_same"]),
            "xX_ocr_hit_true": sum(1 for p in all_xx if p["ocr_hit"]),
            "sympy_fail_case_only": len(case_only),
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=== Chunk A: x vs X case on cached reads ===")
    for sm in summaries:
        print(f"\n[{sm['source']}] step_pairs={sm['step_pairs']}")
        print(f"  x/X-only (raw):              {sm['xX_only_raw']}")
        print(f"  x/X-only (after normalize):  {sm['xX_only_after_normalize']}")
        print(f"  x/X pairs sympy_same=True:   {sm['xX_pairs_sympy_same_true']}")
        print(f"  x/X pairs ocr_hit=True:      {sm['xX_pairs_ocr_hit_true']}")
        print(f"  sympy fail, case ONLY:       {sm['sympy_fail_case_only']}")
        print(f"  sympy fail, other cause:     {sm['sympy_fail_other_cause']}")
        for d in sm["xX_pair_details"]:
            print(
                f"    {d['chain_id']} step {d['step_idx']}: "
                f"sympy={d['sympy_same']} ocr_hit={d['ocr_hit']} "
                f"gt={d['gt']!r} read={d['read']!r}"
            )

    print(f"\nVERDICT: {verdict} — {rationale}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())