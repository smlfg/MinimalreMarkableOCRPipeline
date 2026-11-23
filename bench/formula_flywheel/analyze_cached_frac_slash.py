"""Chunk C (Pass 2): \\frac{a}{b} vs a/b on cached chain bench reads.

Reads last_real / last_synth_real against GT steps. Does not call live OCR.
Writes bench/formula_flywheel/analysis_frac_slash_20261124.json.

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
OUT_JSON = HERE / "analysis_frac_slash_20261124.json"

LEADING_EQ = re.compile(r"^\s*=\s*")


def extract_brace(s: str, pos: int) -> tuple[str, int] | None:
    if pos >= len(s) or s[pos] != "{":
        return None
    depth = 0
    for j in range(pos, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[pos + 1 : j], j + 1
    return None


def frac_to_slash(s: str) -> str:
    """Collapse nested \\frac{num}{den} to num/den after ocr.latex.normalize."""
    s = normalize(s)
    pattern = re.compile(r"\\frac\{")
    while True:
        m = pattern.search(s)
        if not m:
            break
        idx = m.end() - 1
        g1 = extract_brace(s, idx)
        if g1 is None:
            break
        num, after1 = g1
        while after1 < len(s) and s[after1].isspace():
            after1 += 1
        g2 = extract_brace(s, after1)
        if g2 is None:
            break
        den, after2 = g2
        repl = f"{frac_to_slash(num)}/{frac_to_slash(den)}"
        s = s[: m.start()] + repl + s[after2:]
    return s


def strip_leading_eq(s: str) -> str:
    t = (s or "").strip()
    return LEADING_EQ.sub("", t, count=1).strip()


def frac_slash_only_string_diff(gt: str, rd: str) -> bool:
    """True if strings differ but match after folding \\frac to slash (both sides)."""
    g, r = (gt or "").strip(), (rd or "").strip()
    if g == r:
        return False
    return frac_to_slash(g) == frac_to_slash(r)


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
        gt_body, rd_body = strip_leading_eq(gt), strip_leading_eq(rd)
        sym_body = same(gt_body, rd_body)
        fso = frac_slash_only_string_diff(gt, rd)
        ocr_miss_fso = hit is False and fso
        sympy_artifact = ocr_miss_fso and sym is True
        body_recover = ocr_miss_fso and sym is False and sym_body is True
        out.append(
            {
                "chain_id": chain_row["id"],
                "step_idx": k,
                "gt": gt,
                "read": rd,
                "frac_slash_only_string": fso,
                "normalize_equal": normalize(gt) == normalize(rd),
                "frac_to_slash_equal": frac_to_slash(gt) == frac_to_slash(rd),
                "sympy_same_gt_read": sym,
                "sympy_same_strip_leading_eq_bodies": sym_body,
                "ocr_hit": hit,
                "ocr_miss_frac_slash_only": ocr_miss_fso,
                "ocr_miss_same_true_artifact": sympy_artifact,
                "ocr_miss_eq_parse_frac_slash": body_recover,
            }
        )
    return out


def summarize(pairs: list[dict], source: str) -> dict:
    fso = [p for p in pairs if p["frac_slash_only_string"]]
    miss_fso = [p for p in pairs if p["ocr_miss_frac_slash_only"]]
    artifacts = [p for p in miss_fso if p["ocr_miss_same_true_artifact"]]
    eq_parse = [p for p in miss_fso if p["ocr_miss_eq_parse_frac_slash"]]
    hit_false = [p for p in pairs if p["ocr_hit"] is False]
    return {
        "source": source,
        "step_pairs": len(pairs),
        "frac_slash_only_string_pairs": len(fso),
        "ocr_hit_false": len(hit_false),
        "ocr_miss_frac_slash_only": len(miss_fso),
        "ocr_miss_same_true_artifact": len(artifacts),
        "ocr_miss_eq_parse_frac_slash_only": len(eq_parse),
        "frac_slash_pair_details": [
            {
                k: p[k]
                for k in (
                    "chain_id",
                    "step_idx",
                    "gt",
                    "read",
                    "sympy_same_gt_read",
                    "sympy_same_strip_leading_eq_bodies",
                    "ocr_hit",
                    "ocr_miss_frac_slash_only",
                    "ocr_miss_same_true_artifact",
                    "ocr_miss_eq_parse_frac_slash",
                )
            }
            for p in pairs
            if p["frac_slash_only_string"]
        ],
        "ocr_miss_frac_slash_details": miss_fso,
        "ocr_miss_same_true_artifact_details": artifacts,
        "ocr_miss_eq_parse_details": eq_parse,
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
    probe = {
        r"\frac{20}{6}": "20/6",
        r"=\frac{20}{6}": "=20/6",
    }
    probe_same = {k: same(k, v) for k, v in probe.items()}

    gt_kalib = load_gt(KETTEN / "ketten_gt.jsonl")
    gt_synth = load_gt(SYNTH_GT)

    summaries = [
        analyze_jsonl(KETTEN / "last_real.jsonl", gt_kalib, "kalib_last_real"),
        analyze_jsonl(ROOT / "bench" / "synth" / "last_synth_real.jsonl", gt_synth, "synth_last_real"),
    ]

    all_miss = [p for sm in summaries for p in sm["ocr_miss_frac_slash_details"]]
    artifacts = [p for p in all_miss if p["ocr_miss_same_true_artifact"]]
    eq_parse = [p for p in all_miss if p["ocr_miss_eq_parse_frac_slash"]]

    bare_frac_equal = probe_same[r"\frac{20}{6}"] is True
    verdict = "REVERT"
    product_change = False
    if bare_frac_equal:
        rationale = (
            "ocr.latex.same already equates bare \\frac{a}{b} with a/b (SymPy rationals); "
            "no frac→slash product normalization. Cached synth ocr_hit=False rows with "
            "frac/slash-only ink are almost all '=…' continuation steps where latex2sympy "
            "fails to parse slash-form equalities (same(gt,read) False) but "
            "same(strip leading '=', gt, read) is True — bench/metric parse coupling with "
            "Chunk B, not a missing equivalence rule. ocr_hit uses same(read, gt) so "
            "False is consistent; not a string/ocr_hit bug when same() is also False."
        )
    else:
        verdict = "EXPERIMENT"
        rationale = "bare \\frac vs slash not equal under same() — controlled normalize experiment warranted."
        product_change = True

    payload = {
        "date": "20261124",
        "chunk": "C",
        "verdict": verdict,
        "product_change": product_change,
        "rationale": rationale,
        "primary_metric_probe": {
            "same_frac20_6_vs_20_slash_6": probe_same[r"\frac{20}{6}"],
            "same_eq_frac20_6_vs_eq_20_slash_6": probe_same[r"=\frac{20}{6}"],
            "note": (
                "Bare rational forms equivalent; leading '=' + slash breaks latex2sympy "
                "equality parse so same() False on full continuation strings."
            ),
        },
        "chain_bench": {
            "ocr_hit_computation": "hits.append(same(o['latex'], c['steps'][k])) in bench/chain_bench.py",
            "ocr_hit_uses_sympy_same": True,
            "ocr_hit_not_raw_string": True,
        },
        "summaries": summaries,
        "totals": {
            "frac_slash_only_string_pairs": sum(s["frac_slash_only_string_pairs"] for s in summaries),
            "ocr_miss_frac_slash_only": len(all_miss),
            "ocr_miss_same_true_artifact": len(artifacts),
            "ocr_miss_eq_parse_frac_slash_only": len(eq_parse),
        },
        "discrepancy_explanation": {
            "ocr_hit_false_same_true_count": len(artifacts),
            "meaning": (
                "Should be 0 if ocr_hit and same() share one code path — nonzero would imply "
                "stale cache or alternate metric."
            ),
            "ocr_hit_false_strip_eq_same_true_count": len(eq_parse),
            "meaning_eq_parse": (
                "Math content matches after removing continuation '=' and comparing bodies; "
                "primary metric same() on full strings still False — document as parse artifact, "
                "not ink error; do not weaken frozen eval."
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=== Chunk C: \\frac vs slash on cached reads ===")
    print(f"probe same(\\frac{{20}}{{6}}, 20/6) = {probe_same[r'\frac{20}{6}']}")
    print(f"probe same(=\\frac{{20}}{{6}}, =20/6) = {probe_same['=\\frac{20}{6}']}")
    for sm in summaries:
        print(f"\n[{sm['source']}] step_pairs={sm['step_pairs']}")
        print(f"  frac/slash-only string:     {sm['frac_slash_only_string_pairs']}")
        print(f"  ocr_hit=False:              {sm['ocr_hit_false']}")
        print(f"  ocr_miss frac/slash ONLY:   {sm['ocr_miss_frac_slash_only']}")
        print(f"  ocr_miss same()=True bug:  {sm['ocr_miss_same_true_artifact']}")
        print(f"  ocr_miss eq-parse only:     {sm['ocr_miss_eq_parse_frac_slash_only']}")
        for d in sm["ocr_miss_frac_slash_details"][:6]:
            print(
                f"    {d['chain_id']} step {d['step_idx']}: "
                f"sympy={d['sympy_same_gt_read']} body_sympy={d['sympy_same_strip_leading_eq_bodies']} "
                f"ocr_hit={d['ocr_hit']} gt={d['gt']!r} read={d['read']!r}"
            )
        if len(sm["ocr_miss_frac_slash_details"]) > 6:
            print(f"    ... +{len(sm['ocr_miss_frac_slash_details']) - 6} more")

    print(f"\nVERDICT: {verdict} (product_change={product_change})")
    print(f"  {rationale}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())