# OCR overnight mission 2026-11-24

Branch: `experiment/ocr-overnight-20261124`

## Baseline (2026-11-23)

From `bench/formula_flywheel/results_2026-11-23.tsv` (best coherence-era rows on Mac MPS, metrik v2):

| Split | commit | strukt | char | p95 s | coverage | prec_certain |
|---|---|---:|---:|---:|---:|---:|
| own_probe (40, eigene Schrift) | a1db534 | 90,0 % | 93,4 % | 0,23 | 85,0 % | 94,1 % |
| dev (326, Schulmathe) | a1db534 | 89,6 % | 97,2 % | 0,32 | 72,7 % | 93,7 % |

**Issue #1 follow-up:** `coherent()` no longer sets `trusted=True` on repair or via `closed_truth` without GLM. `uncertain` / `coverage` / `prec_certain` semantics changed — **live Mac MPS remeasure** required before updating this table.

## Data availability gate

- Kalib PNGs and flywheel `data/images/` are gitignored / absent in this VM.
- SchlangebeißtinSchwanz sibling repo is **not** required for the overnight synth pack.
- **Verdict:** synthetic mathtext dataset only; no claim of real-handwriting accuracy until kalib PNGs are available.

## Issue #1 (Pass 2 — coherent hardening)

`uncertain` is OCR-confidence only (`not trusted` or `repair is not None`); `math_status` = `closed_truth(fixed)`. Any repair ⇒ `trusted=False` (even GLM-corroborated). Without a second opinion, `trusted=False` — `closed_truth` does not drive OCR trust. Student wrong equations with both engines agreeing stay wrong and `uncertain=False`.

## Pass 2 Chunk A — x vs X variable case (measurement)

**Verdict: REVERT** (no `ocr/latex.py` / `ocr/coherence.py` casefold rule).

Cached kalib reads (`bench/formula_flywheel/kalib/ketten/last_real.jsonl`) vs `ketten_gt.jsonl`:

| Metric | kalib (60 OCR steps) | synth (102 OCR steps) |
|---|---:|---:|
| Step pairs with x/X-only string diff (raw) | 3 | 0 |
| x/X-only after `normalize` | 4 | 0 |
| Those pairs with `ocr.latex.same` = True | 4 | 0 |
| Those pairs with `ocr_hit` = True | 4 | 0 |
| `same` fail where case is **only** issue | 0 | 0 |

Affected kalib lines: **K01** (`3X=15`), **K06** (`5X=25` — step 3 `x=125` is intentional student error, never “fix”), **K09** (`(X-1)(X+7)=0`), **K13** (mixed `X`/`x` in one chain). Primary metric already treats x/X as equivalent via SymPy; `ocr_hit` already True.

Reproduce:

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/analyze_cached_case.py
```

Artifact: `bench/formula_flywheel/analysis_case_xX_20261124.json`.

## Pass 2 Chunk B — leading `=` on continuation lines (measurement)

**Verdict: REVERT** (no OCR/coherence prepend-`=` rule).

`chain_bench` sets `ocr_hit` via `same(read, gt_step)` (`ocr.latex.same` → normalize + SymPy), **not** raw string equality. Bare continuation terms without leading `=` parse as expressions; GT steps with `=` parse as equalities → `same` False even when ink is correct.

Cached reads:

| Metric | kalib (60 OCR steps) | synth (102 OCR steps) |
|---|---:|---:|
| `ocr_hit=False` | 3 | 27 |
| Fail **only** missing/extra leading `=` (`sympy_same` True after align) | 3 | 0 |
| `sympy` fail with other cause | 0 | 27 |

Kalib: **K25** only — steps 2–4 read `3\cdot10+3\cdot7`, `30+21`, `41` vs GT `=…`; student **41** (not 51) preserved; validator uses implicit continuation (`validator_lines`).

Reproduce:

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/analyze_cached_leading_eq.py
```

Artifact: `bench/formula_flywheel/analysis_leading_eq_20261124.json`.

## Experiment 1 — fused exponent digits

**Failure:** TexTeller reads fused exponent digits as flat numbers — `=3^{5}` → `=35` (S41/S43) and `=3^{9}` → `=39` (S34) in `bench/synth/last_synth_real.jsonl`.

**Hypothesis:** Candidate `b^{e}` from adjacent digit pairs; accept **only** if `agree(cand, glm)` — never via `closed_truth` alone.

**Result:** **KEPT.** `tests/test_power_digit_repair.py` + Issue #1 regressions pass (12/12). Student-error case `both=...=35` unchanged; GLM-corroborated repair yields power form with `uncertain=True`, `math_status=True`.

**Implementation:** `ocr/coherence.py` — `_power_digit_cands()` after CONFUSE loop.

## Experiment 2 — overnight synthetic dataset

**Location:** `bench/formula_flywheel/overnight_synth/`

- `config.json` — seed `20261124`, n_train=40, n_dev=20, matplotlib mathtext
- `gen.py` — reproducible formulas + PNGs under `images/` (gitignored); stratified by structure family; unique `gt_latex` across splits
- `train.jsonl`, `dev.jsonl` — committed (train wrong=10, dev wrong=4; both have frac/power/sqrt/cdot/decimal)
- `eval_stub.py` — oracle 100 % struct on dev; fused-digit TT stub + GLM=gt 100 % struct (repair path)

## Stop conditions (why no further OCR loops)

- Real kalib / flywheel PNGs and live TexTeller+Ollama absent on this CPU VM → cannot remeasure primary `sympy_equal` on independent handwriting.
- Coherence on foreign `dev` was already saturated (~89.6 % across prior keeps in `results_2026-11-23.tsv`).
- Further struct gains need live engines + owner ink, not more postprocessing speculation.
- Target ≥99 % on real handwriting remains **unproven** here; synthetic results are wiring/safety evidence only.

## Rejected / deferred

| Idea | Reason |
|---|---|
| Fused exponent via `closed_truth` only | Silently “fixes” agreeing student `=35` |
| Replace TexTeller | Out of scope; no weight download in VM |

### Upstream #2–#4 — **DEFER** (memo-grounded, no new framework this sprint)

| # | Candidate | Decision | Rationale (`docs/research/UPSTREAM_SEARCH-math-ocr.md`) |
|---|---|---|---|
| 2 | **MyScript iink** | DEFER | Commercial SDK; on-device math from strokes needs license negotiation — violates “local/frei” until owner signs off. |
| 3 | **MathWriting** (Google) | DEFER | Dataset **CC BY-NC-SA** — training/eval reuse restricted; no published stroke→LaTeX weights to bolt on; gain vs. TexTeller+GLM unproven on owner ink. |
| 4 | **UniMERNet + CDM** | DEFER | Apache-2.0 model but 441 MB–1.3 GB weights + CDM eval needs texlive/ImageMagick/Node ballast; HWE BLEU strong yet Mac MPS latency **unbelegt**; TexTeller already at ~90 % own_probe without framework swap. |

Action: stay on TexTeller+GLM-OCR coherence stack; revisit when kalib PNGs + MPS bench slot available.

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

## CPU benchmark (2026-11-24, this VM)

**Hardware ≠ Mac MPS.** Live TexTeller/Ollama not used; `engine=stub_injected` on overnight_synth PNGs only.

| Field | Value |
|---|---|
| Platform | Linux-6.12.113+-x86_64-with-glibc2.39 |
| CPU | Intel(R) Xeon(R) Processor |
| cores (`nproc`) | 4 |
| RAM | 15.63 GiB |
| Python | 3.12.3 |
| torch | {'present': False} |
| device | cpu (mps=False, ollama=False, texteller=False) |

Suites: `structure_bench --selftest` → **PASS** (0.6066 s);
`pytest tests/` → **PASS** (0.7253 s).

Latency columns are **recognize() wall time on CPU with stub engines**, not MPS OCR throughput.

| Split | Scenario | n | struct | char | p50 ms | p95 ms | coverage | prec_certain | student_error_preserved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | oracle | 20 | 100.0 % | 100.0 % | 3.7 | 20.3 | 100.0 % | 100.0 % | 100.0 % |
| dev | fused_tt_glm_gt | 20 | 100.0 % | 100.0 % | 1.7 | 2.6 | 95.0 % | 100.0 % | 100.0 % |
| dev | both_student_error | 20 | 100.0 % | 100.0 % | 1.7 | 2.6 | 100.0 % | 100.0 % | 100.0 % |
| train | oracle | 40 | 100.0 % | 100.0 % | 1.9 | 5.0 | 100.0 % | 100.0 % | 100.0 % |
| train | fused_tt_glm_gt | 40 | 100.0 % | 100.0 % | 1.7 | 3.1 | 97.5 % | 100.0 % | 100.0 % |
| train | both_student_error | 40 | 100.0 % | 100.0 % | 1.7 | 3.2 | 100.0 % | 100.0 % | 100.0 % |

Logs: `bench/results_cpu_overnight_20261124.json`, `bench/results_cpu_overnight_20261124.tsv`.

Reproduce:

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/cpu_overnight_bench.py
```
