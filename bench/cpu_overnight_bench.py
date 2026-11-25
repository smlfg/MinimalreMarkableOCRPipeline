#!/usr/bin/env python3
"""CPU-VM overnight benchmark: hardware fingerprint + structure selftest + pytest + stub OCR eval.

Engines are injected stubs (engine=stub_injected). Latency is recognize() wall time on CPU;
not comparable to Mac MPS TexTeller p95.
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench"
SYNTH = BENCH / "formula_flywheel" / "overnight_synth"
VENV_PY = ROOT / ".venv_structure" / "bin" / "python"
RESULT_JSON = BENCH / "results_cpu_overnight_20261124.json"
RESULT_TSV = BENCH / "results_cpu_overnight_20261124.tsv"
DOC = ROOT / "docs" / "overnight" / "OCR-OVERNIGHT-20261124.md"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BENCH))

import structure_bench as sb
from bench.formula_flywheel import prepare as fw_prepare
from ocr.formula import recognize


def _read_memtotal_kb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    try:
        r = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            if "Model name" in line:
                return line.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or "unknown"


def collect_hardware() -> dict:
    torch_info: dict
    try:
        import torch

        torch_info = {
            "present": True,
            "version": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
        }
    except ImportError:
        torch_info = {"present": False}

    mem_kb = _read_memtotal_kb()
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "nproc": os.cpu_count(),
        "mem_total_gib": round(mem_kb / (1024**2), 2) if mem_kb else None,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "torch": torch_info,
        "device": "cpu",
        "mps": False,
        "ollama": False,
        "texteller": False,
        "engine_note": "stub_injected for overnight_synth scenarios",
    }


def run_structure_selftest() -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [str(VENV_PY), str(BENCH / "structure_bench.py"), "--selftest"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    wall_s = time.perf_counter() - t0
    return {
        "name": "structure_bench --selftest",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "wall_s": round(wall_s, 4),
        "stdout_tail": proc.stdout.strip()[-500:] if proc.stdout else "",
        "stderr_tail": proc.stderr.strip()[-500:] if proc.stderr else "",
    }


def run_pytest_suite() -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [str(VENV_PY), "-m", "pytest", "tests/", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    wall_s = time.perf_counter() - t0
    return {
        "name": "pytest tests/ (Issue #1 + power-digit)",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "wall_s": round(wall_s, 4),
        "stdout_tail": proc.stdout.strip()[-800:] if proc.stdout else "",
        "stderr_tail": proc.stderr.strip()[-500:] if proc.stderr else "",
    }


def _load_split(split: str) -> list[dict]:
    path = SYNTH / f"{split}.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _fused_corrupt(latex: str) -> str:
    parts = latex.split("=")
    if len(parts) < 2:
        return latex
    rhs = re.sub(r"(\d)\^\{(\d)\}", r"\1\2", parts[-1])
    return "=".join(parts[:-1]) + "=" + rhs


def _stub(latex: str, cost: float = 0.0):
    def _tt(path):
        return latex, cost

    def _glm(img):
        return latex, cost

    return _tt, _glm


def _oracle(gt: str):
    return _stub(gt)


def _equation_closed(gt_latex: str) -> bool:
    parts = [p for p in re.split(r"(?<![<>!\\])=", gt_latex) if p.strip()]
    return len(parts) >= 2


def eval_scenario(split: str, scenario: str) -> dict:
    rows = _load_split(split)
    lat_ms: list[float] = []
    details: list[dict] = []
    struct_hits = 0
    char_sum = 0.0
    cert_ok = 0
    cert_n = 0

    for r in rows:
        png = SYNTH / r["png"]
        gt = r["gt_latex"]
        math_correct = bool(r.get("math_correct", True))
        if scenario == "fused_tt_glm_gt":
            has_rhs_power = "=" in gt and re.search(r"\d\^\{\d\}", gt.split("=")[-1])
            tt_latex = _fused_corrupt(gt) if has_rhs_power else gt
            tt, glm = _stub(tt_latex)[0], _stub(gt)[1]
        elif scenario == "both_student_error":
            # Wrong equations: both engines agree on gt (student error on page); correct rows: oracle.
            tt, glm = _oracle(gt)
        else:
            tt, glm = _oracle(gt)

        t0 = time.perf_counter()
        out = recognize(str(png), tt, glm=glm)
        wall_ms = (time.perf_counter() - t0) * 1000
        lat_ms.append(wall_ms)

        pred = out["latex"]
        sc = sb.score(gt, pred)
        ok = bool(sc["sympy_equal"])
        struct_hits += int(ok)
        ch = fw_prepare.char_acc(gt, pred)
        char_sum += ch
        unc = bool(out.get("uncertain", False))
        if not unc:
            cert_n += 1
            cert_ok += int(ok)

        details.append(
            {
                "id": r["id"],
                "gt_latex": gt,
                "pred_latex": pred,
                "math_correct": math_correct,
                "sympy_equal": ok,
                "char": round(ch, 4),
                "uncertain": unc,
                "math_status": out.get("math_status"),
                "repair": out.get("repair"),
                "latency_ms": round(wall_ms, 3),
            }
        )

    n = len(rows)
    lat_ms.sort()
    wrong_closed = [d for d in details if not d["math_correct"] and _equation_closed(d["gt_latex"])]
    preserved = sum(
        1
        for d in wrong_closed
        if d["pred_latex"] == d["gt_latex"] and d["math_status"] is False
    )

    return {
        "split": split,
        "scenario": scenario,
        "engine": "stub_injected",
        "n": n,
        "struct": round(struct_hits / n, 4) if n else 0.0,
        "char": round(char_sum / n, 4) if n else 0.0,
        "p50_latency_ms": round(lat_ms[n // 2], 3) if n else 0.0,
        "p95_latency_ms": round(lat_ms[max(0, int(n * 0.95) - 1)], 3) if n else 0.0,
        "coverage": round(sum(1 for d in details if not d["uncertain"]) / n, 4) if n else 0.0,
        "prec_certain": round(cert_ok / cert_n, 4) if cert_n else 0.0,
        "student_error_preserved": round(preserved / len(wrong_closed), 4) if wrong_closed else None,
        "student_wrong_closed_n": len(wrong_closed),
        "rows": details,
    }


def append_tsv(hw: dict, suites: list[dict], metrics: list[dict]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    host = "cpu_vm"
    lines = [
        f"zeit\thost\tcpu\tnproc\tmem_gib\tmps\tollama\ttexteller\tsuite\tok\twall_s\tnote",
        (
            f"{ts}\t{host}\t{hw['cpu_model'][:60]}\t{hw['nproc']}\t{hw['mem_total_gib']}\t"
            f"{hw['mps']}\t{hw['ollama']}\t{hw['texteller']}\t"
            f"hardware_fingerprint\t-\t-\tdevice={hw['device']}"
        ),
    ]
    for s in suites:
        lines.append(
            f"{ts}\t{host}\t-\t-\t-\t-\t-\t-\t{s['name']}\t{s['ok']}\t{s['wall_s']}\treturncode={s['returncode']}"
        )
    lines.append(
        "zeit\thost\tsplit\tscenario\tengine\tn\tstruct\tchar\tp50_ms\tp95_ms\tcoverage\tprec_certain\tstudent_error_preserved"
    )
    for m in metrics:
        sep = m.get("student_error_preserved")
        sep_s = "" if sep is None else f"{sep:.4f}"
        lines.append(
            f"{ts}\t{host}\t{m['split']}\t{m['scenario']}\t{m['engine']}\t{m['n']}\t"
            f"{m['struct']:.4f}\t{m['char']:.4f}\t{m['p50_latency_ms']:.3f}\t{m['p95_latency_ms']:.3f}\t"
            f"{m['coverage']:.4f}\t{m['prec_certain']:.4f}\t{sep_s}"
        )
    # Overwrite (not append): each run is a complete, comparable snapshot for this VM.
    RESULT_TSV.write_text("\n".join(lines) + "\n")


def update_doc(hw: dict, suites: list[dict], metrics: list[dict]) -> None:
    if not DOC.exists():
        return
    text = DOC.read_text()
    marker = "## CPU benchmark (2026-11-24"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n"

    pytest_ok = next(s for s in suites if "pytest" in s["name"])
    st_ok = next(s for s in suites if "structure" in s["name"])

    def _row(m: dict) -> str:
        sep = m.get("student_error_preserved")
        sep_s = "—" if sep is None else f"{sep * 100:.1f} %"
        return (
            f"| {m['split']} | {m['scenario']} | {m['n']} | {m['struct'] * 100:.1f} % | "
            f"{m['char'] * 100:.1f} % | {m['p50_latency_ms']:.1f} | {m['p95_latency_ms']:.1f} | "
            f"{m['coverage'] * 100:.1f} % | {m['prec_certain'] * 100:.1f} % | {sep_s} |"
        )

    section = f"""
## CPU benchmark (2026-11-24, this VM)

**Hardware ≠ Mac MPS.** Live TexTeller/Ollama not used; `engine=stub_injected` on overnight_synth PNGs only.

| Field | Value |
|---|---|
| Platform | {hw['platform']} |
| CPU | {hw['cpu_model']} |
| cores (`nproc`) | {hw['nproc']} |
| RAM | {hw['mem_total_gib']} GiB |
| Python | {hw['python']} |
| torch | {hw['torch']} |
| device | {hw['device']} (mps={hw['mps']}, ollama={hw['ollama']}, texteller={hw['texteller']}) |

Suites: `structure_bench --selftest` → **{'PASS' if st_ok['ok'] else 'FAIL'}** ({st_ok['wall_s']} s);
`pytest tests/` → **{'PASS' if pytest_ok['ok'] else 'FAIL'}** ({pytest_ok['wall_s']} s).

Latency columns are **recognize() wall time on CPU with stub engines**, not MPS OCR throughput.

| Split | Scenario | n | struct | char | p50 ms | p95 ms | coverage | prec_certain | student_error_preserved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
"""
    section += "\n".join(_row(m) for m in metrics)
    section += f"""

Logs: `{RESULT_JSON.relative_to(ROOT)}`, `{RESULT_TSV.relative_to(ROOT)}`.

Reproduce:

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/cpu_overnight_bench.py
```
"""
    DOC.write_text(text.rstrip() + "\n" + section)


def main() -> int:
    hw = collect_hardware()
    print("=== hardware ===")
    print(json.dumps(hw, indent=2))

    suites = [run_structure_selftest(), run_pytest_suite()]
    for s in suites:
        print(f"{s['name']}: {'OK' if s['ok'] else 'FAIL'} ({s['wall_s']}s)")

    scenarios = ["oracle", "fused_tt_glm_gt", "both_student_error"]
    metrics: list[dict] = []
    slim_metrics: list[dict] = []
    for split in ("dev", "train"):
        for scenario in scenarios:
            print(f"eval {split} / {scenario} ...")
            m = eval_scenario(split, scenario)
            slim = {k: v for k, v in m.items() if k != "rows"}
            slim_metrics.append(slim)
            metrics.append(m)
            print(json.dumps(slim, indent=2))

    payload = {
        "hardware": hw,
        "suites": suites,
        "overnight_synth": slim_metrics,
        "overnight_synth_row_detail": {
            f"{m['split']}_{m['scenario']}": m["rows"] for m in metrics
        },
    }
    RESULT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    append_tsv(hw, suites, slim_metrics)
    update_doc(hw, suites, slim_metrics)

    print(f"\nWrote {RESULT_JSON}")
    print(f"Appended {RESULT_TSV}")
    return 0 if all(s["ok"] for s in suites) else 1


if __name__ == "__main__":
    raise SystemExit(main())