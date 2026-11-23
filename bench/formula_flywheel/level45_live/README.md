# Level 4–5 live TexTeller suite (Pass 4)

Scaled fixed-seed synthetics for **live CPU TexTeller** evaluation on integrals, matrices, trig, and special constants.

- **Seed:** `20261124`
- **Splits:** `dev` (72) — tuning/decisions; `holdout` (36) — touch once for final report
- **Buckets:** integral, matrix, trig, special (stratified; each bucket has true and false student equations)
- **No `gt_latex` overlap** across splits

## Generate PNGs + JSONL

```bash
cd bench/formula_flywheel/level45_live
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python gen.py
```

Images under `images/` (gitignored).

## Live TexTeller CPU baseline

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/level45_live/run_tt_cpu.py --split dev
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/level45_live/run_tt_cpu.py --suite overnight_synth --split dev
```

Outputs: `bench/results_pass4_l45_baseline_*.json` (+ `.tsv`). Raw preds cached in JSONL for postprocess re-scores (`rescore_pipe.py`).

## Metrics (per row)

| Metric | Meaning |
|---|---|
| `raw_same` / `raw_sympy` | TexTeller output vs GT (`ocr.latex.same`) |
| `pipe_same` / `pipe_sympy` | After `decimal_comma` → `texttt_artifacts` → `integral_eq_artifact` → `coherent(tt, second=tt)` |
| `student_error_preserved` | `math_correct=False` rows: pipeline latex equals GT (no silent fix) |
| `cer` | `1 - latex_edit_sim` from `structure_bench` normalize path |

**Latency:** TT inference ms only (Linux CPU — not comparable to Mac MPS).

Sibling (frozen Pass 3): `../level45/` (24 dev) — do not modify.