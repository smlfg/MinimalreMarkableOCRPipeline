"""Level 4–5 coherence/Issue #1 baseline without live OCR (injected engines + direct API calls)."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ocr.coherence import _power_digit_cands, closed_truth, coherent, agree  # noqa: E402
from ocr.formula import recognize  # noqa: E402
from ocr.latex import same  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_JSON = ROOT / "bench" / "results_level45_diag_20261124.json"
OUT_TSV = ROOT / "bench" / "results_level45_diag_20261124.tsv"

BUILTIN_VARIANTS: list[tuple[str, str]] = [
    (r"\cos x", r"\cos(x)"),
    (r"\sin^2(x)", r"\sin^{2}(x)"),
    (r"\int x\,dx", r"\int x dx"),
    (r"\int x\,dx", r"\int x \mathrm{d}x"),
    (r"e", r"\mathrm{e}"),
    (r"i", r"\mathrm{i}"),
]

# Simulated TT reads: digit/letter confusion near special/trig tokens (CONFUSE list).
CONFUSE_PROBES: list[tuple[str, str, str]] = [
    # (corrupt_tt, glm_gt, label)
    (r"e^{1\pi}+1=0", r"e^{i\pi}+1=0", "e:1_for_i"),
    (r"e^{i\pl}+1=0", r"e^{i\pi}+1=0", "pi:o_for_0_in_pi"),
    (r"\c0s(\pi)=1", r"\cos(\pi)=1", "cos:0_for_o"),
    (r"\cos(\pi)=1", r"\cos(\pi)=1", "trig_both_agree_wrong"),
    (r"\int_0^1 x\,dx=1", r"\int_0^1 x\,dx=1", "integral_both_agree_wrong"),
    (r"3^{2}\cdot3^{3}=35", r"3^{2}\cdot3^{3}=3^{5}", "power_digit_fused"),
]


def _load_rows() -> list[dict]:
    rows: list[dict] = []
    for split in ("train", "dev"):
        path = HERE / f"{split}.jsonl"
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                r.setdefault("split", split)
                rows.append(r)
    return rows


def _stub(latex: str):
    def _e(_path):
        return latex, 0.0
    return _e


def _glm_img(latex: str):
    def _e(_img):
        return latex, 0.0
    return _e


def _variant_pairs(row: dict) -> list[tuple[str, str]]:
    gt = row["gt_latex"]
    vs = list(row.get("variants") or [])
    pairs = [(gt, v) for v in vs if v != gt]
    return pairs


def _closed_truth_ok(row: dict) -> tuple[bool, str | None]:
    gt = row["gt_latex"]
    mc = row["math_correct"]
    try:
        ct = closed_truth(gt)
    except Exception as exc:
        return False, f"crash:{exc}"
    if mc:
        if ct is True:
            return True, None
        if ct is None:
            return True, None  # non-equation forms (e.g. bare matrix) — no crash expected
        return False, f"expected_true_got_{ct}"
    else:
        if ct is False:
            return True, None
        if ct is None:
            return True, None  # student error not sympy-checkable (matrix, Euler identity)
        return False, f"false_eq_but_ct_{ct}"


def _issue1_ok(row: dict) -> tuple[bool, str | None]:
    gt = row["gt_latex"]
    png = HERE / row["png"]
    if not png.exists():
        return False, "missing_png"
    rec = recognize(png, _stub(gt), _glm_img(gt))
    ok = (
        rec["latex"] == gt
        and rec["uncertain"] is False
        and rec["repair"] is None
    )
    mc = row["math_correct"]
    ct = closed_truth(gt)
    if mc:
        if ct is True and rec["math_status"] is not True:
            ok = False
    else:
        if ct is False and rec["math_status"] is not False:
            ok = False
    if not ok:
        return False, json.dumps(
            {k: rec[k] for k in ("latex", "uncertain", "math_status", "repair")},
            ensure_ascii=False,
        )
    return True, None


def _variant_agree_row(row: dict) -> tuple[int, int, list[str]]:
    fails: list[str] = []
    ok = n = 0
    for a, b in _variant_pairs(row):
        n += 1
        if same(a, b) and agree(a, b):
            ok += 1
        else:
            fails.append(f"same({a!r},{b!r})={same(a,b)} agree={agree(a,b)}")
    return ok, n, fails


def _power_digit_risk(gt: str, glm: str) -> str | None:
    for cand in _power_digit_cands(gt):
        _, repair, _ = coherent(gt, glm)
        if repair and cand in repair:
            if agree(cand, glm) and closed_truth(cand) is True and closed_truth(gt) is False:
                return "power_digit_repair_student_error"
        if repair and gt in (r"e^{i\pi}+1=0",) and cand != gt:
            return "unexpected_power_digit_on_euler"
    return None


def _corrupt_probe(corrupt: str, glm: str) -> tuple[bool, str | None]:
    """True = corrupt (coherent wrongly changed latex when engines should agree on glm)."""
    fixed, repair, trusted = coherent(corrupt, glm)
    if agree(corrupt, glm):
        return (fixed != corrupt, f"changed_agreeing:{corrupt}->{fixed}") if fixed != corrupt else (False, None)
    if agree(corrupt, glm) is False and agree(fixed, glm) and fixed != glm and corrupt != fixed:
        return True, f"corrupt_toward_glm:{corrupt}->{fixed}"
    if repair and not agree(corrupt, glm):
        if fixed != corrupt and not same(fixed, corrupt):
            return True, f"repair:{repair}"
    if trusted and corrupt != glm and agree(corrupt, glm) is False:
        return False, None
    return False, None


def main() -> None:
    rows = _load_rows()
    failure_modes: Counter[str] = Counter()
    by_bucket: dict[str, dict] = defaultdict(
        lambda: {
            "n": 0,
            "issue1_ok": 0,
            "closed_truth_ok": 0,
            "variant_ok": 0,
            "variant_n": 0,
            "corrupt_n": 0,
        }
    )
    detail_rows: list[dict] = []

    for row in rows:
        bucket = row["bucket"]
        by_bucket[bucket]["n"] += 1
        iok, ierr = _issue1_ok(row)
        if iok:
            by_bucket[bucket]["issue1_ok"] += 1
        else:
            failure_modes[f"issue1:{ierr}"] += 1

        ctok, cterr = _closed_truth_ok(row)
        if ctok:
            by_bucket[bucket]["closed_truth_ok"] += 1
        else:
            failure_modes[f"closed_truth:{cterr}"] += 1

        vok, vn, vf = _variant_agree_row(row)
        by_bucket[bucket]["variant_ok"] += vok
        by_bucket[bucket]["variant_n"] += vn
        for f in vf:
            failure_modes[f"variant:{f}"] += 1

        gt = row["gt_latex"]
        pdr = _power_digit_risk(gt, gt)
        if pdr:
            failure_modes[f"power_digit:{pdr}"] += 1
            by_bucket[bucket]["corrupt_n"] += 1

        detail_rows.append(
            {
                "id": row["id"],
                "bucket": bucket,
                "split": row["split"],
                "gt_latex": gt,
                "math_correct": row["math_correct"],
                "issue1_ok": iok,
                "closed_truth_ok": ctok,
                "variant_failures": vf,
            }
        )

    # Built-in variant pairs (global, not per-row)
    for a, b in BUILTIN_VARIANTS:
        if same(a, b) and agree(a, b):
            continue
        failure_modes[f"builtin_variant:same={same(a,b)} agree={agree(a,b)} {a!r} vs {b!r}"] += 1

    corrupt_events = 0
    for corrupt, glm, label in CONFUSE_PROBES:
        bad, msg = _corrupt_probe(corrupt, glm)
        if bad:
            corrupt_events += 1
            failure_modes[f"confuse_corrupt:{label}:{msg}"] += 1

    summary = {}
    tsv_lines = ["bucket\tn\tissue1_ok_rate\tclosed_truth_ok_rate\tvariant_agree_rate\tcorrupt_events"]
    for bucket in sorted(by_bucket.keys()):
        b = by_bucket[bucket]
        n = b["n"]
        summary[bucket] = {
            "n": n,
            "issue1_ok_rate": b["issue1_ok"] / n if n else 0.0,
            "closed_truth_ok_rate": b["closed_truth_ok"] / n if n else 0.0,
            "variant_agree_rate": (b["variant_ok"] / b["variant_n"]) if b["variant_n"] else None,
            "corrupt_rate_probe": b["corrupt_n"] / n if n else 0.0,
        }
        var_rate = summary[bucket]["variant_agree_rate"]
        var_s = "" if var_rate is None else f"{var_rate:.4f}"
        tsv_lines.append(
            f"{bucket}\t{n}\t{summary[bucket]['issue1_ok_rate']:.4f}\t"
            f"{summary[bucket]['closed_truth_ok_rate']:.4f}\t{var_s}\t{b['corrupt_n']}"
        )

    payload = {
        "seed": 20261124,
        "engine": "stub_injected",
        "n_rows": len(rows),
        "by_bucket": summary,
        "confuse_probe_corrupt_count": corrupt_events,
        "failure_modes_ranked": failure_modes.most_common(50),
        "rows": detail_rows,
        "texteller_feasibility": {
            "live_tt": False,
            "note": "CPU VM may lack .venv_tt; this diag does not require TexTeller. Re-run dev.jsonl with live TT+GLM when available.",
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    OUT_TSV.write_text("\n".join(tsv_lines) + "\n")

    print("Level 4–5 baseline by bucket:")
    for bucket in sorted(summary.keys()):
        s = summary[bucket]
        vr = s["variant_agree_rate"]
        vr_txt = "n/a" if vr is None else f"{vr:.1%}"
        print(
            f"  {bucket:8s} n={s['n']:2d}  issue1={s['issue1_ok_rate']:.1%}  "
            f"closed_truth={s['closed_truth_ok_rate']:.1%}  variants={vr_txt}"
        )
    print("\nTop failure modes:")
    for mode, cnt in failure_modes.most_common(15):
        print(f"  {cnt:3d}  {mode}")
    print(f"\nwrote {OUT_JSON.relative_to(ROOT)} and {OUT_TSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()