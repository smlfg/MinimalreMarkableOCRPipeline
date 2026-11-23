# OCR overnight mission 2026-11-24

Branch: `experiment/ocr-overnight-20261124`

## Baseline (2026-11-23)

From `bench/formula_flywheel/results_2026-11-23.tsv` and README:

| Split | Struktur (`sympy_equal`) | Zeichen |
|---|---:|---:|
| own_probe (40 Zeilen, eigene Schrift) | 90 % | 93,4 % |
| dev (326, Schulmathe) | 89,6 % | 97,2 % |

## Data availability gate

- Kalib PNGs and flywheel `data/images/` are gitignored / absent in this VM.
- SchlangebeißtinSchwanz sibling repo is **not** required for the overnight synth pack.
- **Verdict:** synthetic mathtext dataset only; no claim of real-handwriting accuracy until kalib PNGs are available.

## Issue #1 (DONE — 517b7b3)

`uncertain` is OCR-confidence only (`not trusted` or `repair is not None`); `math_status` = `closed_truth(fixed)`. Student wrong equations with both engines agreeing stay wrong and `uncertain=False`.

## Experiment 1 — fused exponent digits

**Failure:** TexTeller reads `3^{2}\cdot3^{3}=35` instead of `=3^{5}` (S41/S43 in `bench/synth/last_synth_real.jsonl`).

**Hypothesis:** Candidate `b^{e}` from adjacent digit pairs; accept **only** if `agree(cand, glm)` — never via `closed_truth` alone.

**Result:** **KEPT.** `tests/test_power_digit_repair.py` + Issue #1 regressions pass (12/12). Student-error case `both=...=35` unchanged; GLM-corroborated repair yields power form with `uncertain=True`, `math_status=True`.

**Implementation:** `ocr/coherence.py` — `_power_digit_cands()` after CONFUSE loop.

## Experiment 2 — overnight synthetic dataset

**Location:** `bench/formula_flywheel/overnight_synth/`

- `config.json` — seed `20261124`, n_train=40, n_dev=20, matplotlib mathtext
- `gen.py` — reproducible formulas + PNGs under `images/` (gitignored)
- `train.jsonl`, `dev.jsonl` — committed
- `eval_stub.py` — oracle 100 % struct on dev; fused-digit TT stub + GLM=gt 100 % struct (repair path)

## Rejected / deferred

| Idea | Reason |
|---|---|
| Fused exponent via `closed_truth` only | Silently “fixes” agreeing student `=35` |
| Replace TexTeller | Out of scope; no weight download in VM |
| UniMERNet download | Large model; defer |
| Upstream issues #2–#4 | Triage → defer per `docs/research/`; no new framework |

## Hardware / environment (this VM)

- Linux CPU only — no MPS, no Ollama/TexTeller live stack in this run.
- CPU stub tests ≠ Mac MPS production latencies.

## Remaining failures

- Real synth chain S41/S43 OCR hit still needs **live** TT+GLM on handwriting PNGs (not reproduced here).
- dev struct ~89.6 % baseline unchanged by coherence-only edit until remeasured on real data.

## Reproduction

```bash
# tests
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python -m pytest tests/ -v

# regenerate synthetic data
cd bench/formula_flywheel/overnight_synth
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python gen.py

# offline eval stub
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python eval_stub.py
```

## Honest limitation

Cannot claim ≥99 % on **real handwriting** without kalib / flywheel PNGs in-repo. Synthetic mathtext proves pipeline wiring only.