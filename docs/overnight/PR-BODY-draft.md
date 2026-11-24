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
9. Pass 5 — mehrzeilige Ableitungen sind ohne Seitenstruktur nur eine flache Zeilenliste;
   sie lassen sich rein strukturell (Fortsetzungssignale, Nähe, Spalte, Label) zu Ketten
   gruppieren, **ohne** Tutor/Validator und ohne eine Zeile zu verändern (Issue #1).
10. Pass 5 — die echten ketten-Muster brechen an OCR `x`/`X` und an K25 (verschlucktes
    führendes `=`); nackte Terme + Gross/Klein-Fold lösen beide strukturell.

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
| Pass 5: Mehrzeilen-Gruppierung (`ocr/multiline.py`) | ketten within-chain 0,821 → **1,000**; live chain_recall **1,000**, chain_exact_pages **1,000**, merge_fp 0, Schuelerfehler/Anti-Domino 100 % | **KEEP** |

## Kept and rejected changes

**Behalten (Produktcode):** `ocr/formula.py` (uncertain = reine OCR-Evidenz + `math_status`),
`ocr/coherence.py` (Reparatur/second-None trusted=False), `ocr/latex.py` (Artefakt-
Normalisierung, Matrix-Umgebungen `smallmatrix`→`matrix`/`|`-Matrix→`vmatrix`,
`\vspace`/`\mathsf`, `parse` wendet `normalize` an, `equivalent_expr` vergleicht Matrizen),
`ocr/multiline.py` (`group_lines`/`page_structure`: strukturelle Rechenketten, Issue-#1-sicher),
`ocr/pre.py:split_lines_with_boxes` (Boxen; `split_lines` verhaltensgleich),
`ocr/pipeline.py:recognize_page` (additiv; Segmentieren→Erkennen→Gruppieren).
**Verworfen:** jede x/X-Regel im Vergleich, jede führende-`=`-Reparatur ohne Zweitmeinung, jeder
frac-Produkt-Hack, jedes blinde Kollabieren mehrerer Determinanten-Balken (würde `‖M‖` mit
`|M|` verwechseln), `\langle→(` (würde echte Inner-Products korrumpieren), **jegliche
Tutor-/Schrittrichter-Logik** (bewusst nicht in der OCR-Struktur). Nicht angetastet:
`prepare.py`, `models.py`, `structure_bench.py`, Test-Labels, `results_2026-11-23.tsv`,
GT-Dateien.

## Validation evidence

- `venv/bin/python -m pytest -q` → **grün** (36 Tests: Issue-#1-Sicherheit, coherent-Pfade,
  normalize, Matrix-Umgebungen/`parse`-Robustheit, Mehrzeilen-Gruppierung).
- `venv/bin/python bench/structure_bench.py --selftest` → **OK**.
- Level 4–5 (dev 70 / holdout 36, live TexTeller CPU, synthetisch gerendert): dev struct
  **0,714 → 0,943** (matrix 0,000 → 0,875, integral 1,000, parse_err 0,157 → 0,043);
  holdout struct **0,944** (integral/trig/special 1,000, matrix 0,778) → **keine Überanpassung**.
  Anchor `overnight_synth` (50) bleibt **1,000**.
- Pass 5 real ketten-Muster (ohne Modell): within-chain **28/28 = 1,000** (vorher 23/28);
  packed mit Leerzeile **28/28 exakt, 0 verschmolzen**.
- Pass 5 end-to-end (15 Seiten, 43 Zeilen, 19 Ketten, live TexTeller CPU): line_struct 0,889,
  **chain_recall 1,000, chain_exact_pages 1,000**, merge_fp 0, **student_error_preserved 1,000,
  anti_domino True**; p50 0,475 s / p95 0,931 s (Linux CPU ≠ MPS).
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
7. Pass 5 Segmentierung hoher Brüche/Integrale: dünner Bruchstrich fällt unter die Ink-Schwelle
   → Zusatz-Zeile (`seg_mismatch` p04/p07). Betrifft die Segmentierung, nicht die Gruppierung
   (Ketten bleiben exakt) — gehört zur Matrix/Crop-Vorverarbeitung (Pass 6).
8. Pass 5 Grenzfall: gleiche-Variable-Aufgaben ohne sichtbare Lücke/Label werden verschmolzen
   (ohne Validator/Tutor nicht eindeutig auflösbar; bewusst nicht geraten).

## Reproduction commands

```bash
git checkout experiment/ocr-overnight-opencode-20261124
venv/bin/python -m pytest -q                                # Regressionstests
venv/bin/python bench/structure_bench.py --selftest        # Metrik-Selbsttest
venv/bin/python bench/overnight/error_distribution.py       # Cache-Fehlerverteilung (nur lesend)
venv/bin/python bench/overnight/benchmark.py --tag "notiz"  # live TexTeller CPU (synth. gerendert)
venv/bin/python bench/overnight/level45.py dev --tag "notiz"  # Level 4-5, live TexTeller CPU
venv/bin/python bench/overnight/level45.py holdout          # Holdout (einmal am Ende)
venv/bin/python bench/overnight/multiline_ketten.py --tag "notiz"  # Mehrzeilen: echte ketten-Muster
venv/bin/python bench/overnight/multiline_bench.py --tag "notiz"   # Mehrzeilen: live TexTeller
venv/bin/python bench/overnight/latency.py 3                # Latenz, Linux CPU
```
