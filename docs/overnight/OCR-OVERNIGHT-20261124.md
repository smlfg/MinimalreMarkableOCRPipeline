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

- `\sum_{k=1}^{n}` wird von TexTeller teils als `\sum_{k\,=\ ,1}` gelesen (Spacing + Komma-
  Artefakt im Subskript). Das `,` ist mehrdeutig (Mengentrenner) → noch nicht normalisiert.
- Matrizen (`\begin{pmatrix}`/`\bmatrix`) sind im Benchmark noch nicht abgedeckt (mathtext
  kann sie nicht rendern) und werden als eigener Block später behandelt.
- Issue-#1-Neumessung von `coverage`/`prec_certain` auf Mac MPS steht aus.
- Seitenstruktur (`order`/`steps`/`checks`) ist weiterhin nicht gemessen (ADR-005).

## Reproduktion

```bash
# Regressionstests (keine Modelle nötig)
venv/bin/python -m pytest -q
venv/bin/python bench/structure_bench.py --selftest

# Overnight-Benchmark (live TexTeller CPU, synthetisch gerendert)
venv/bin/python bench/overnight/benchmark.py --tag "notiz"
```
