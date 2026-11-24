# OCR Overnight — 2026-11-24 (Branch `experiment/ocr-overnight-opencode-20261124`)

Autonome Nachtschicht. Ein Faktor pro Experiment, kleine Commits, eingefrorene
Eval-Dateien unangetastet. Ziel: mathematisch treue Handschrift-Erkennung ≥ 99 %
Struktur auf echter Kalibrierung, ohne Schülerfehler still zu korrigieren.

## Hardware & Datenlage (ehrlich)

- **Diese VM:** Linux, 8 vCPU, 15 GB RAM, **keine GPU/MPS**. `venv` = Python 3.13,
  torch 2.15.0+cpu, texteller 1.0.2 (Gewichte gecacht), sympy, latex2sympy2-extended.
- **Kein GLM-OCR / Ollama** auf dieser VM → die Zweitmeinung ist hier nicht messbar;
  die Kohärenz-Schicht wird mit injizierten Engine-Ausgaben getestet (Regressionstests).
- **Kein `data/external/`** (MathWriting/CROHME) und kein `cache.sqlite` im Repo → die
  Splits `train/dev/test` aus `prepare.py` sind hier nicht baubar. Eigenes handschriftliches
  Kalibriermaterial (`own_*`) braucht das Tablet (SSH), das hier nicht verfügbar ist.
- Ersatz: **synthetisch gerenderte** Formeln (matplotlib mathtext, festes Dataset).
  **Das ist NICHT Handschrift und wird nie als solche berichtet** (ADR-008).

## Baseline (aus `bench/formula_flywheel/results_2026-11-23.tsv`, Mac MPS, eingefroren)

| Split | struct | char | p95 | coverage | prec_certain |
|---|---:|---:|---:|---:|---:|
| own_probe (40) | 90,0 % | 93,4 % | 0,23 s | 85,0 % | 94,1 % |
| dev (326) | 89,6 % | 97,2 % | 0,32 s | 72,7 % | 93,7 % |

Issue #1 ändert die Semantik von `coverage`/`prec_certain` (übereinstimmend gelesene
falsche Gleichungen wandern von `uncertain` nach `certain`). Diese Spalten brauchen eine
**Neu-Messung auf Mac MPS** — hier nicht möglich.

## Experiment 1 — Issue #1 (harter Sicherheits-Gate) — BEHALTEN

**Befund:** `recognize()` verband `uncertain` mit `closed_truth(fixed) is False` und
`coherent()` lieferte für eine GLM-korroborierte Reparatur `trusted=True`.

**Änderung (kleinste kompatible Korrektur):**
- `coherent()`: jede Reparatur → `trusted=False`; ohne Zweitmeinung entscheidet
  `closed_truth` nie über `trusted`.
- `recognize()`: `uncertain = not trusted or repair is not None` (reine OCR-Evidenz);
  neues Diagnose-Feld `math_status = closed_truth(fixed)`.

**Regressionstests (injizierte TT/GLM-Ausgaben, keine Modelle):**
- Beide Engines `7+5=13` → `uncertain=False`, `math_status=False` (OCR sicher, Rechnung falsch).
- Engines `7+5=13`/`7+5=12` uneinig → `uncertain=True`, wahre Alternative wird nicht still übernommen.
- Reparatur `2a→za` (GLM-korroboriert) → `uncertain=True`.
- Falsche Schülerlösung wird nicht still umgedichtet.

**Beleg:** `tests/test_issue1_safety.py` (8 Tests), `tests/test_normalize.py` (6 Tests), 14 grün.

## Experiment 2 — Normalisierung von TexTeller-Artefakten — BEHALTEN

**Hypothese:** TexTeller wrappt `\int` als `\mbox{\Large$\int$}`, ganze Integrale als
`\begin{array}{c}…`, Klammern/Funktionsnamen als `\text{(`/`\text{sin(`. Das brach
`sympy_equal` auf Integralen/Trig, obwohl die Erkennung korrekt war.

**Änderung (`ocr/latex.py normalize`, eine Quelle mit der Metrik):**
Fontgrößen-Kommandos + innere `$` entfernen; einspaltige `\begin{array}{c}…\end{array}`
→ Inhalt (nur `{c}`, nie mehrspaltige `{cc}` = Matrix); `\mbox`/`\text`/`\mathrm` → Inhalt
(nach Funktionsnamen-Normalisierung). Semantik-erhaltend, berührt keine Rechenwahrheit.

**Messung (Live TexTeller CPU, synthetisch gerendert, 50 Formeln):**

| Lauf | struct | char |
|---|---:|---:|
| Baseline | 0,900 | 0,945 |
| + normalize | **1,000** | **1,000** |

Fehlerverteilung Baseline: 3× Integral (`\mbox`/`\begin{array}`), 1× Trig (`\text{}`),
1× Special (`\sum`-Spacing). Nach der Änderung 0 Fehler.

**Latenz (Linux CPU, ≠ Mac MPS):** p50 ≈ 0,5–0,9 s, p95 schwankt (0,6–7,4 s; Modell-Load +
VM-Last). Nur als Orientierung, nicht mit MPS vergleichbar.

## Hardware-Benchmark — live TexTeller CPU (Pass 1b)

Sauber gemessen (`bench/overnight/latency.py`): Modell einmal laden (3,7 s), 3× Warm-up,
dann 3 Durchläufe über 50 Formeln = 150 Inferenzen.

| Metrik | Linux CPU (diese VM) | Mac MPS (Baseline, eingefroren) |
|---|---:|---:|
| p50 | **0,65 s** | – (nicht erfasst) |
| p95 | **1,14 s** | **0,32 s** (dev) / **0,23 s** (own_probe) |
| min / max | 0,32 s / 4,47 s | – |
| Durchsatz | 1,36 Formeln/s | – |
| Modell-Load | 3,7 s | – |

**Einordnung:** Linux-CPU-Inferenz ist hier **~2–4× langsamer** als der Mac-MPS-Baseline
(p95 1,14 s vs 0,32 s). p95 liegt damit knapp unter der 2-s-Grenze, aber die CPU-Zahl ist
nicht mit MPS gleichzusetzen und wird nicht als solche berichtet. Der Varianz-Ausreißer
(max 4,47 s) stammt von VM-Last/GC während des ersten Durchlaufs nach dem Laden.

## Upstream-Entscheidungen (#2–#4) — DEFER

Memo-gestützt, keine neuen Messungen nötig:

- **#2 MyScript iink / native Strokes — DEFER.** Kommerziell/Cloud bzw. Lizenzpflicht,
  verletzt „lokal/frei"; kein Holdout-Beleg, der TexTeller ersetzen würde (ADR-006 legt
  TexTeller fest). On-device- vs. Cloud-Lizenz ungeklärt.
- **#3 Google MathWriting — DEFER (Experiment später).** Lizenz **CC BY-NC-SA 4.0** ist vor
  Übernahme/Training zu prüfen; kein Fine-Tuning heute. Split-Leakage (Writer/Notebook-Level)
  wäre erst zu klären.
- **#4 UniMERNet / CDM — DEFER.** Vorrecherche (`UPSTREAM_SEARCH-struktur-benchmark.md`)
  fand CDM-Mensch-Korrelation r=0,34 bei schwerem TeX/ImageMagick/Node-Overhead; Backbone
  ist per ADR-006 fest. Nur Zusatzmetrik, nicht Kern.

## Bekannte Restfehler / offen

- **Fusionierte Exponenten** (synthetisch belegt, `last_synth_real.jsonl`): S34 (`=3^{9}` →
  `=39`), S41 (`=3^{5}` → `=35`, Ketten-F1 verfehlt: Erstfehler zu früh erkannt), S43
  (`=3^{5}` → `=35`, Ketten-F1 verfehlt: Fehlalarm auf korrekter Kette). Laut
  `bench/synth/README.md` ein **Realismusloch des Schrift-Simulators** (Exponent zu flach
  gerendert), kein Pipeline-Fehler. Eine Reparatur-Regel ohne Zweitmeinung wäre ein
  stilles Eingreifen in Schülerzahlen (`35` kann eine echte Zahl sein) — abgelehnt (Issue #1).
- `\sum_{k=1}^{n}` wird von TexTeller teils als `\sum_{k\,=\ ,1}` gelesen (Spacing + Komma-
  Artefakt im Subskript). Das `,` ist mehrdeutig (Mengentrenner) → noch nicht normalisiert.
- Matrizen (`\begin{pmatrix}`/`\bmatrix`) sind im Benchmark noch nicht abgedeckt (mathtext
  kann sie nicht rendern) und werden als eigener Block später behandelt.
- Issue-#1-Neumessung von `coverage`/`prec_certain` auf Mac MPS steht aus.
- Seitenstruktur (`order`/`steps`/`checks`) ist weiterhin nicht gemessen (ADR-005).

## Pass 2 — Fehlerverteilung über getrackte Cache-Ausgaben (Messung vor Code)

`bench/overnight/error_distribution.py` (nur lesend) kategorisiert alle `ocr_hit=false`-
Zeilen in `kalib/ketten/last_real.jsonl` und `bench/synth/last_synth_real.jsonl`.
Ergebnis: **alle drei Kandidaten sind String-Match-Artefakte — kein Produktcode geändert.**

### Chunk A — `x` vs `X` (K01/K06/K09/K13): ZURÜCKGEWIESEN (kein Fehler)

`same('3X=15', '3x=15')` = **True** — latex2sympy faltet `X`→`x`, alle X-Zeilen haben
`ocr_hit=true`. Eine x/X-Normalisierung wäre toter Code mit dem Risiko, legitime
Großbuchstaben (eigenständige Variablen) zu korrumpieren. Kein Messgewinn → nicht behalten.

### Chunk B — führendes `=` auf Fortsetzungszeilen (K25): ZURÜCKGEWIESEN (Artefakt)

- `parse('=…')` = `None` (latex2sympy kann führendes `=` nicht) → `same()` kann nicht auf
  SymPy-Äquivalenz ausweichen. K25 liest `3 \cdot 10+3 \cdot 7`, `30+21`, `41` ohne das
  GT-führende `=`; **Inhalt identisch, Schülerfehler `41` erhalten**.
- Ketten-F1 real: **28/28** — `chain_bench.validator_lines` behandelt Fortsetzungszeilen
  (nackter Term = implizite Fortsetzung, K25-Konvention). Der strikte Zeilen-Diagnosewert
  `ocr_hit` fällt nur wegen des unparsebaren `=`.
- Eine Kohärenz-Regel, die `=` korroboriert erhält/hinzufügt, ist hier **nicht messbar**
  (kein GLM/Ollama auf dieser VM) und ohne Primaer-Metrikgewinn → dokumentiert, kein Code.

### Chunk C — `\frac{a}{b}` vs `a/b`: ZURÜCKGEWIESEN (bereits gleich)

`same(r'\frac{20}{6}', r'20/6')` = **True**. Die 24 synthetischen `ocr_hit=false`-Zeilen
(S03–S31) sind **keine** sympy_equal-Fehler, sondern dasselbe führende-`=`-Artefakt
(GT `=\frac{20}{6}` vs read `=20/6`, beide unparsebar). Kein Produkt-Hack (Vorgabe
„already equal → nur dokumentieren" erfüllt).

### Pass-2-Härtung (Chunk 0): BEHALTEN

- `coherent()`-Sicherheitskanten (Reparatur nie `trusted`, `second is None` nie
  `closed_truth`-getrieben) waren aus Pass 1 bereits umgesetzt; direkte Unit-Tests
  `test_coherent_repair_is_never_trusted` / `test_coherent_second_none_not_truth_driven`
  decken beide Pfade.
- `test_engines_disagree_uncertain_even_if_alt_true` assertiert jetzt zusätzlich
  `math_status=False` (Rechenwahrheit getrennt von `uncertain`).
- ADR-005-Nachtrag definiert `uncertain` als reine OCR-Evidenz, `math_status` trägt
  `closed_truth` — Widerspruch zu ADR-007 aufgelöst.

## Pass 3 — Level 4–5 Diagnostik (Baseline gemessen, live TexTeller CPU)

`bench/overnight/level45.py` rendert ein festes Level-4–5-Dataset (Integrale, Matrizen,
Trig, spezielle Symbole `i`/`\pi`/`e`, je mit absichtlich FALSCHEN Schülergleichungen;
dev 46 / holdout 16, null Überlappung) — Matrizen über eigene Zell-Komposition (mathtext
kann `\begin{pmatrix}` nicht). Baseline (Linux CPU, synthetisch gerendert, NICHT Handschrift):

| Bucket | dev struct (sympy_equal) | n |
|---|---:|---:|
| integral | 0,917 | 12 |
| matrix | **0,000** | 10 |
| trig | 1,000 | 12 |
| special | 1,000 | 12 |
| **gesamt** | **0,761** (char 0,877) | 46 |

p50 0,79 s / p95 1,51 s (Linux CPU ≠ Mac MPS).

**Fehlerverteilung:** 10/11 Fehler sind Matrizen; 1 Integral (`\vspace{0.2cm}`-Artefakt).
TexTeller liest Matrizen als `\begin{array}{cc}`/`\begin{array}{c}`/`\begin{smallmatrix}`
statt `\begin{pmatrix}`/`\bmatrix`/`\vmatrix`, und **lässt oft die `&`-Spaltentrenner weg**
(`1\ 2` statt `1&2`). latex2sympy parst `array`/`smallmatrix` gar nicht → sympy_equal=0 für
alle 10 Matrix-Zeilen. Nächster Schritt (getrennte Experimente): `\vspace`-Normalisierung
und Matrix-Umgebungs-Normalisierung nur für Fälle mit erhaltenem `&`; das `&`-Droppen ist
Strukturverlust und ohne Stütze nicht rekonstruierbar.

## Reproduktion

```bash
# Regressionstests (keine Modelle nötig)
venv/bin/python -m pytest -q
venv/bin/python bench/structure_bench.py --selftest

# Fehlerverteilung über getrackte Cache-Ausgaben (nur lesend)
venv/bin/python bench/overnight/error_distribution.py

# Overnight-Benchmark (live TexTeller CPU, synthetisch gerendert)
venv/bin/python bench/overnight/benchmark.py --tag "notiz"

# Latenz-Benchmark (Linux CPU, sauber protokolliert)
venv/bin/python bench/overnight/latency.py 3

# Level 4-5 Diagnostik (live TexTeller CPU, synthetisch gerendert)
venv/bin/python bench/overnight/level45.py dev --tag "notiz"
```
