# Level 4–5 formula diagnostic (seed 20261124)

Reproducible **matplotlib mathtext** (with text fallback for some matrices) for **pipeline / coherence baseline** on integrals, matrices, trigonometry, and special symbols (`i`, `\pi`, `e`).

**Synthetic mathtext ≠ SchlangebeißtinSchwanz / kalib handwriting.** Use this split only to localize Level 4–5 failure modes (Issue #1, variant equivalence, CONFUSE / power-digit risks)—not as real OCR accuracy.

## Regenerate

```bash
cd bench/formula_flywheel/level45
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python gen.py
```

Reads `config.json` (seed, split sizes, buckets). Stratified **~2/3 train, 1/3 dev per bucket**; unique `gt_latex` across splits. PNGs under `images/` (gitignored).

## Fields (jsonl)

| Field | Meaning |
|---|---|
| `id` | `train_L45001`, … |
| `split` | `train` or `dev` |
| `bucket` | `integral`, `matrix`, `trig`, or `special` |
| `gt_latex` | Ground truth as written (incorrect student equations stay wrong) |
| `math_correct` | Whether the chain is mathematically true (`closed_truth` where applicable) |
| `png` | Path to rendered image |
| `variants` | Optional list of LaTeX strings that should agree with `gt_latex` |

## Coherence / Issue #1 baseline (no live OCR)

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/level45/diag.py
```

Writes `bench/results_level45_diag_20261124.json` and `.tsv`.

## TexTeller feasibility

Live TexTeller CPU stack may be unavailable on this VM. This pack does **not** depend on it; wire live engines later against the same `dev.jsonl` for end-to-end struct/char metrics.