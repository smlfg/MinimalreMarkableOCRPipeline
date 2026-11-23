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

## Pass 2 Chunk C — `\frac{a}{b}` vs `a/b` (measurement)

**Verdict: REVERT** (no frac→slash normalization in `ocr/latex.py` / coherence).

Primary probe: `same(r'\frac{20}{6}', '20/6')` is **True** (SymPy rationals). Continuation `same(r'=\frac{20}{6}', '=20/6')` is **False** — `latex2sympy` does not parse slash-form equalities; not a missing frac/slash equivalence rule.

`chain_bench` `ocr_hit` = `same(read, gt_step)` — same code path; **0** cached steps with `ocr_hit=False` and `same()=True` (no stale-metric artifact).

Cached reads:

| Metric | kalib (60 OCR steps) | synth (102 OCR steps) |
|---|---:|---:|
| `frac/slash`-only string diff | 20 | 34 |
| `ocr_hit=False` & frac/slash-only | 0 | 24 |
| Above with `same(gt,read)` True | 0 | 0 |
| Above with `same` on bodies after strip `=` True | 0 | 24 |

Synth continuation steps: GT `=\frac{…}{…}`, read `=a/b` — ink correct; `ocr_hit` False because full-string `same()` fails on `=`-equality parse (Chunk B coupling), not because `\frac` ≠ `/`. Kalib keeps `\frac` in reads → hits stay True. Remaining synth `ocr_hit=False` (3): fused exponents S34/S41/S43 — unrelated.

Reproduce:

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/analyze_cached_frac_slash.py
```

Artifact: `bench/formula_flywheel/analysis_frac_slash_20261124.json`.

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

## Pass 3 — Level 4–5 + TexTeller CPU (2026-11-24)

Suite: `bench/formula_flywheel/level45/` (stratified dev sample, 12 formulas × 4 buckets).

### TexTeller CPU feasibility

**SUCCESS** after pinning `torch==2.10.*+cpu` and `torchvision==0.25.*+cpu` in `.venv_tt` (prior CPU runs lacked torchvision; worker failed to load).

| Metric | Linux CPU (this VM) | Notes |
|---|---:|---|
| Worker load (cold) | ~2.8 s | one-time per bench session |
| TT p50 / p95 (n=12) | ~610 ms / ~1178 ms | per PNG recognize TT leg only |
| Mac MPS reference | unmeasured | not comparable to this Linux CPU slot |

Live JSONL: `bench/results_level45_texteller_cpu_20261124.jsonl`  
Summary TSV: `bench/results_level45_texteller_cpu_20261124.tsv`

### Level 45 baseline (raw TT reads, pre-repair)

| bucket | n | `same(gt,pred)` raw | student false preserved |
|---|---:|---:|---|
| integral | 3 | 2/3 | n/a |
| matrix | 3 | **0/3** | n/a (`\backslash\texttt{begin}{pmatrix}` artifact) |
| trig | 3 | 3/3 | `cos(π)=1` false eq ok |
| special | 3 | 3/3 | `e^{iπ}=1` false eq ok |

Stub diag (injected engines, no TT): `bench/results_level45_diag_20261124.json` — Issue #1 100 % on false-student rows; variant gap documented: `e` vs `\mathrm{e}` (`same=False`).

### Experiment M1 — texttt/backslash env repair

**Verdict: KEPT.** `ocr/coherence.py` — `texttt_artifacts()`; wired in `ocr/formula.py` before `coherent()`; also in `variants(second)`.

Post-repair `same()` on recorded TT matrix preds: **2/3**

| id | raw same | repaired same |
|---|---|---|
| dev_L45_017 (student-false pmatrix) | False | **False** (fused `\texttt{162}` — no `&` invention) |
| dev_L45_018 (det) | False | **True** |
| dev_L45_019 (vmatrix) | False | **True** |

Tests: `tests/test_texttt_artifacts.py` + 40/40 pytest green.

### Experiment M2 — `\mathrm{e}` ↔ `e`

**Verdict: KEPT.** `ocr/latex.py` `normalize()` — `re.sub(r'\\mathrm\{e\}', 'e', s)`.

`same('e','\mathrm{e}')` → True; `e^{1}=e` vs `\mathrm{e}^{1}=\mathrm{e}` → True; Issue #1 false equations unchanged.

### Experiment M3 — integral `\,{=` artifact

**Verdict: KEPT.** `ocr/coherence.py` — `integral_eq_artifact()`; `\int_{0}^{2}\!3\,dx\,{=6}` → `same` True vs GT `\int_0^2 3\,dx=6`.

Integral bucket post-repair: **3/3** `same()` on recorded preds.

### Remaining (Pass 3)

- Fused matrix digits (`\texttt{162}`) — partial env repair only; needs real column OCR or model fix, not silent `&` grafting.
- `closed_truth(e^{i\pi}+1=0)` stays `None` (symbols) — not an OCR equivalence bug.
- No claim of real-handwriting accuracy or Mac MPS latency from this VM.

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

## Pass 4 — scaled Level 4–5 live TexTeller CPU (2026-11-24)

**Suite:** `bench/formula_flywheel/level45_live/` — 108 lines (72 dev + 36 holdout), seed `20261124`, synthetic matplotlib mathtext (not handwriting). Regression anchor: `overnight_synth` dev (20).

**Evaluation:** live TT in `.venv_tt` (torch 2.10+cpu); pipe = `tt_postprocess` + `coherent(tt, second=tt)` (no GLM invention). Cached raw preds: `bench/results_pass4_l45_baseline_dev.jsonl`.

### Baseline (pre–Pass 4 product changes, dev n=72)

| bucket | n | raw_sympy | pipe_sympy |
|---|---:|---:|---:|
| integral | 18 | 0.611 | 0.667 |
| matrix | 18 | **0.000** | 0.111 |
| trig | 18 | 0.778 | 0.778 |
| special | 18 | 0.778 | 0.944 |
| **all** | 72 | 0.542 | **0.625** |

**TT latency (Linux CPU only):** p50 **700** ms / p95 **1900** ms (dev batch; cold worker load ~64 s). Mac MPS not measured.

Artifacts: `bench/results_pass4_l45_baseline_dev.json`, `bench/results_pass4_overnight_synth_anchor.json`.

### Experiments (one-factor; re-score from cache)

| iter | factor | keep | pipe_sympy dev | matrix dev | overnight dev | pytest |
|---:|---|:---:|---:|---:|---:|:---:|
| 0 | baseline | — | 0.625 | 0.111 | 0.950 | 43/43 |
| 1 | `tt_render_artifacts` (`\mbox{\Large$\int$}` → `\int`, `\tfrac`) | **KEEP** | 0.694 | 0.111 | 0.950 | 43/43 |
| 2 | `texttt_artifacts` row breaks (`\backslash \backslash`, `\}\{=`, `@`→`&`) | **KEEP** | 0.750 | 0.333 | 0.950 | 43/43 |
| 3 | `\text{sin|cos|…}` → `\sin` etc. (`tt_render_artifacts`) | **KEEP** | **0.764** | 0.944 | 0.950 | 44/44 |
| 4 | single-cell `\begin{array}` unwrap | **KEEP** | **0.778** | 0.333 | 0.950 | 45/45 |

Iter log: `bench/results_pass4_l45_iters.tsv`.

**Deferred / REVERT:** `G`→`&` matrix fusion, `\bigl{(}` / `\text{(}` paren fixes, larger gen pad (needs full TT re-infer), `Re/Im` mbox — insufficient evidence or Issue #1 risk.

### After Pass 4 (final pipe, dev re-score)

| bucket | pipe_sympy |
|---|---:|
| integral | **1.000** |
| matrix | 0.333 |
| trig | 0.833 |
| special | 0.944 |
| **all** | **0.778** (56/72) |

### Holdout (n=36, final pipe re-score — not used for keep/revert)

| bucket | pipe_sympy |
|---|---:|
| integral | 0.889 |
| matrix | 0.556 |
| trig | 1.000 |
| special | 1.000 |
| **all** | **0.861** |

### Commits (Pass 4)

1. `feat(bench): scaled Level4-5 live TT suite (dev+holdout)`
2. `chore(bench): Pass4 live TT CPU baseline on Level4-5 + overnight_synth`
3. `fix(ocr): tt_render mbox integral + matrix row break artifacts (Pass4)`
4. `fix(ocr): map TT text{sin,cos,...} to backslash macros (Pass4 E3)`
5. `fix(ocr): unwrap single-cell TT array wrapper (Pass4 E4)`

### Remaining failures (dev, pipe_sympy — 16 rows)

- **Matrix (12):** fused digits (`162`, `10060…`), `G` vs `&`, garbled env names (`peatrlx`, `bmatrixx`), `\operatorname` mbox spam — no safe postprocess without inventing `&`.
- **Trig (3):** `\bigl{(}` / `\text{(}` / `\left\langle` mangling beyond `\text{sin}` fix (e.g. L45L_067, L45L_073, L45L_080).
- **Special (1):** `Re(z)+Im(z)` mbox italic artifact (L45L_085).

Reproduce:

```bash
cd bench/formula_flywheel/level45_live && PYTHONPATH=/workspace /workspace/.venv_structure/bin/python gen.py
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/level45_live/run_tt_cpu.py --split dev
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/level45_live/rescore_pipe.py bench/results_pass4_l45_baseline_dev.jsonl
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python -m pytest tests/ -q
```

## Pass 5 — Multi-line calculation grouping (2026-11-24)

**Product:** `ocr/multiline.group_calculations()` — chains are `{id, line_ids, has_uncertain_step, uncertain_line_indices}` only; **never mutates** line fields or sets `line.uncertain` (anti-Domino).

**Pipeline:** `ocr/pipeline.assemble_page()` / `finalize_page()` add `page["calculations"]` when math lines exist.

**Suite:** `bench/formula_flywheel/multiline_live/` (12 seeded pages, line crops + GT chains).

| Metric | Result |
|---|---:|
| Synth chain boundary (grouping + GT OCR) | **100%** (12/12) |
| kalib `last_real.jsonl` grouping-only | **100%** (28/28) |
| Anti-Domino violations | **0** |
| Student-error preservation (k25-style page) | **100%** |
| pytest (incl. `test_multiline.py`) | **57/57** |

Artifacts: `bench/results_pass5_multiline_live.{json,tsv}`

Reproduce:

```bash
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/multiline_live/gen.py
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python bench/formula_flywheel/multiline_live/run_e2e.py --grouping-only
PYTHONPATH=/workspace /workspace/.venv_structure/bin/python -m pytest tests/test_multiline.py -q
```

### Commits (Pass 5)

1. `feat(ocr): multi-line calculation grouping (Pass5)`
2. `test(ocr): multiline anti-Domino and student-error preservation`
3. `feat(bench): multiline_live E2E suite`
4. `docs: Pass5 multiline results`
