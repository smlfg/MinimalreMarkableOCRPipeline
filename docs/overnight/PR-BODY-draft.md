# Draft PR body — experiment/ocr-overnight-opencode-20261124

> Hinweis: `gh pr edit` ist auf dieser Branch-Runde vom Guardrail-Shim blockiert
> („no PRs/issues/merges"). Der PR-Body liegt daher als Datei im Repo; die 7 Pflicht-
> Abschnitte sind vollständig. PR #6 (andere Branch) bleibt unberührt und Draft.

## Baseline

Eingefrorene Mac-MPS-Baseline aus `bench/formula_flywheel/results_2026-11-23.tsv`:

| Split | struct | char | p95 | coverage | prec_certain |
|---|---:|---:|---:|---:|---:|
| own_probe (40, eigene Schrift) | 90,0 % | 93,4 % | 0,23 s | 85,0 % | 94,1 % |
| dev (326, fremde Schulmathe) | 89,6 % | 97,2 % | 0,32 s | 72,7 % | 93,7 % |

Issue #1 ändert die Semantik von `coverage`/`prec_certain` (übereinstimmend gelesene
falsche Schülergleichungen wandern von `uncertain` nach `certain`) → **Neumessung auf
Mac MPS erforderlich**, auf dieser Linux-CPU-VM nicht möglich.

Hardware-Benchmark dieser VM (live TexTeller CPU): p50 0,65 s / p95 1,14 s /
1,36 Formeln/s, Modell-Load 3,7 s — ~2–4× langsamer als MPS (p95 0,32 s), ausdrücklich
**Linux CPU ≠ Mac MPS**.

## Hypotheses

1. Issue #1 (harter Gate): `uncertain` mischt OCR-Evidenz mit Rechenwahrheit
   (`closed_truth(fixed) is False`), und `coherent()` kann Reparaturen als `trusted=True`
   ausgeben → Schülerfehler werden als OCR-Fehler heruntergestuft oder still geglättet.
2. TexTeller-Artefakte (`\mbox{…}`, `\text{…}`, `\begin{array}{c}`, Fontgrößen, innere `$`)
   brechen `sympy_equal` auf Integralen/Trig, obwohl die Erkennung korrekt ist.
3. Pass 2, Chunk A: `X` vs `x` verursacht Messfehler. → **Widerlegt** (latex2sympy faltet X→x).
4. Pass 2, Chunk B: führendes `=` auf Fortsetzungszeilen verursacht Primärmetrik-Fehler. →
   **Widerlegt** (Ketten-F1 real 28/28; nur Diagnosewert `ocr_hit` bricht am unparsebaren `=`).
5. Pass 2, Chunk C: `\frac{a}{b}` vs `a/b` ist ein sympy_equal-Fehler. → **Widerlegt**
   (`same` bereits gleich; die Cache-Zeilen sind führende-`=`-Artefakte).
6. Pass 3/4 — alle Matrix-Fehler (struct 0,000) stammen aus dem Vergleich, nicht der
   Erkennung: `simplify(Matrix−Matrix)==0` ist immer falsch (Nullmatrix ≠ Skalar 0).
7. Pass 4 — TexTeller bricht Matrix-Umgebungen über Zeilen um und nutzt `smallmatrix`/
   `\left(…\right)`, die latex2sympy nicht parst; `parse` muss voll normalisieren.
8. Pass 4 — `\left|…\right|` um eine Matrix ist die **Determinante**, nicht `Abs(Matrix)`.

## Experiment results

| Experiment | Ergebnis | Decision |
|---|---|---|
| Issue #1: uncertain/math_status-Trennung | 8 injizierte Regressionstests grün | **KEEP** |
| coherent(): Reparatur nie trusted, second=None nie closed_truth | Unit-Tests grün | **KEEP** (war Pass 1, Pass 2 verifiziert + math_status-Assert ergänzt) |
| normalize(): TexTeller-Artefakte kollabieren | Overnight-Benchmark struct 0,900 → **1,000**, char 0,945 → **1,000** (50 Formeln, live TexTeller CPU, synthetisch gerendert) | **KEEP** |
| Chunk A: x/X-Normalisierung | 0 Messfehler (Parser faltet X→x); Risiko legitime Großbuchstaben | **REVERT/REJECT** — nur dokumentiert |
| Chunk B: führende-`=`-Kohärenzregel | Ketten-F1 real 28/28 unverändert; GLM hier nicht messbar; `=`-Erfinden ohne Stütze = stiller Eingriff | **REVERT/REJECT** — Artefakt dokumentiert |
| Chunk C: frac-vs-Slash-Hack | `same('\frac{20}{6}','20/6')`=True; 24 Cache-Zeilen sind `=`-Artefakte | **REJECT** per Vorgabe („already equal → nur dokumentieren") |
| Pass 4 A: `equivalent_expr` vergleicht Matrizen (Nullmatrix) | dev struct 0,714 → 0,814, matrix 0,000 → 0,438 | **KEEP** |
| Pass 4 B: `parse` entfernt Whitespace | dev struct → 0,886, matrix → 0,688, parse_err 0,157 → 0,086 | **KEEP** |
| Pass 4 C–E: `normalize` smallmatrix/vmatrix/`\vspace`/`\mathsf` | dev struct → 0,929, matrix → 0,812 | **KEEP** |
| Pass 4 F: `parse` wendet `normalize` an | dev struct **0,943**, matrix **0,875**, parse_err **0,043**; holdout **0,944** | **KEEP** |

## Kept and rejected changes

**Behalten (Produktcode):** `ocr/formula.py` (uncertain = reine OCR-Evidenz + `math_status`),
`ocr/coherence.py` (Reparatur/second-None trusted=False), `ocr/latex.py` (Artefakt-
Normalisierung, Matrix-Umgebungen `smallmatrix`→`matrix`/`|`-Matrix→`vmatrix`,
`\vspace`/`\mathsf`, `parse` wendet `normalize` an, `equivalent_expr` vergleicht Matrizen).
**Verworfen:** jede x/X-Regel, jede führende-`=`-Reparatur ohne Zweitmeinung, jeder frac-
Produkt-Hack, jedes blinde Kollabieren mehrerer Determinanten-Balken (würde `‖M‖` mit
`|M|` verwechseln), `\langle→(` (würde echte Inner-Products korrumpieren). Nicht angetastet:
`prepare.py`, `models.py`, `structure_bench.py`, Test-Labels, `results_2026-11-23.tsv`,
GT-Dateien.

## Validation evidence

- `venv/bin/python -m pytest -q` → **grün** (21 Tests: Issue-#1-Sicherheit, coherent-Pfade,
  normalize, Matrix-Umgebungen/`parse`-Robustheit).
- `venv/bin/python bench/structure_bench.py --selftest` → **OK**.
- Level 4–5 (dev 70 / holdout 36, live TexTeller CPU, synthetisch gerendert): dev struct
  **0,714 → 0,943** (matrix 0,000 → 0,875, integral 1,000, parse_err 0,157 → 0,043);
  holdout struct **0,944** (integral/trig/special 1,000, matrix 0,778) → **keine Überanpassung**.
  Anchor `overnight_synth` (50) bleibt **1,000**.
- `venv/bin/python bench/overnight/error_distribution.py` → Cache-Analyse:
  real 28/28 Ketten-F1, einzige ocr_hit=false-Kette K25 = reines führende-`=`-Artefakt
  (Schülerfehler `41` erhalten); synth 44/47, 24× frac-`=`-Artefakt, 3× fusionierter
  Exponent (S34/S41/S43, Simulator-Realismusloch laut bench/synth/README.md).
- Ehrlichkeit zum Benchmark: Der Overnight-Benchmark ist **live TexTeller CPU auf
  synthetisch gerenderten** Formeln (matplotlib mathtext, festes Dataset) — er prüft
  Wiring, Sicherheit, Normalisierung und Latenz, **nicht** echte Handschrift-Genauigkeit.
  Handschrift-Zahlen (90 % own_probe / 89,6 % dev) bleiben die eingefrorene MPS-Baseline.

## Remaining known failures

1. Fusionierte Exponenten `3^{5}`→`35` (S41/S43 kosten synthetische Ketten-F1; laut
   synth-README ein Simulator-Loch, Generator-Fix benötigt dynamic_writer, hier nicht
   verfügbar). Eine Pipeline-Reparatur ohne Zweitmeinung wäre stiller Eingriff → abgelehnt.
2. `\sum_{k\,=\ ,1}`-Spacing/Komma-Artefakt im Subskript (mehrdeutig, nicht normalisiert).
3. Determinanten-Balken (Level 4–5 matrix): dev `l45_dev_22/31`, holdout `l45_holdout_12/13` —
   TexTeller liest `\left|…\right|` teils als verstümmelte Mehrfach-Balken (teils Renderer-
   Glyphe, teils echte OCR-Verwechslung); blindes Kollabieren wäre `‖M‖`-vs-`|M|`-Verwechslung.
4. Winkelklammern `\langle\pi\rangle` statt `(\pi)` und `i`/`j`-Verwechslung (echte OCR-
   Fehler, ohne Kontext nicht sicher auflösbar → nicht geraten).
5. `coverage`/`prec_certain`-Neumessung nach Issue #1 auf Mac MPS ausstehend.
6. S39 (`ask` durch OCR-Unsicherheit) — Ketten-F1-Synth-Verfehlung ohne Zeilen-Mismatch.

## Reproduction commands

```bash
git checkout experiment/ocr-overnight-opencode-20261124
venv/bin/python -m pytest -q                                # Regressionstests
venv/bin/python bench/structure_bench.py --selftest        # Metrik-Selbsttest
venv/bin/python bench/overnight/error_distribution.py       # Cache-Fehlerverteilung (nur lesend)
venv/bin/python bench/overnight/benchmark.py --tag "notiz"  # live TexTeller CPU (synth. gerendert)
venv/bin/python bench/overnight/level45.py dev --tag "notiz"  # Level 4-5, live TexTeller CPU
venv/bin/python bench/overnight/level45.py holdout          # Holdout (einmal am Ende)
venv/bin/python bench/overnight/latency.py 3                # Latenz, Linux CPU
```
