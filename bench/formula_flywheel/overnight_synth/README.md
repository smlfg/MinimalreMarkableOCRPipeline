# Overnight synthetic math dataset (seed 20261124)

Reproducible **matplotlib mathtext** renders for pipeline wiring — **not** real handwriting.

## Regenerate

```bash
cd bench/formula_flywheel/overnight_synth
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python gen.py
```

Reads `config.json` (seed, split sizes). Writes `train.jsonl`, `dev.jsonl`, and PNGs under `images/` (gitignored).

## Fields (jsonl)

| Field | Meaning |
|---|---|
| `id` | Unique row id (`train_T001`, …) |
| `split` | `train` or `dev` |
| `template_id` | Structural template; never duplicated across splits |
| `gt_latex` | Ground truth as **written** (incorrect equations stay wrong) |
| `math_correct` | Whether the equation chain is mathematically true |
| `png` | Path to rendered image |

## Offline eval stub

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python eval_stub.py
```

Oracle stubs + fused-digit corruption on power lines; reports `sympy_equal` via `bench/structure_bench.py`.

## Warning

Synthetic mathtext ≠ SchlangebeißtinSchwanz / kalib handwriting. Do not cite these numbers as real OCR accuracy.