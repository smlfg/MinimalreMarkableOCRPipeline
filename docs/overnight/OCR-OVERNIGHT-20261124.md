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

## Pass 4 — Skalierte Level 4–5 Live-Eval + Optimierung (live TexTeller CPU)

### Benchmark & fairer Renderer

`bench/overnight/level45.py` wurde erweitert: festes Seed-Dataset **dev 70 / holdout 36**
(null Überlappung, stratifiziert über Integral/Matrix/Trig/Special, je mit gültigen UND
absichtlich FALSCHEN Schülergleichungen). Der Renderer bekam feste, realistische Parameter
(Fontgröße 30, Zellabstand 25, Matrizen als Zell-Komposition `tail`/`parts`) und zusätzliche
Formen (2×3, 3×3, `bmatrix`, `vmatrix`, falsche Determinanten/Matrixsummen). Synthetisch
gerendert — **nicht Handschrift** (ADR-008). Metriken: struct (`sympy_equal`), char (CER),
`parse_err`, `student_error_preserved` (sep), p50/p95 (Linux CPU ≠ Mac MPS).

### Baseline (vor jeder Produktänderung)

| Split | struct | char | parse_err | sep | n |
|---|---:|---:|---:|---:|---:|
| dev | 0,7143 | 0,9179 | 0,1571 | 0,7500 | 70 |
| **Anchor `overnight_synth` (50)** | **1,000** | **1,000** | – | – | 50 |

Baseline-Fehler (dev): 10/20 Matrix-Zeilen (SymPy-Fehler plus Strukturverlust); Rest Integrale
mit `\vspace`-Artefakt, Trig/Special vereinzelt.

### One-Factor-Iterationen (dev, nach jedem Schritt gemessen)

| # | Faktor (Commit) | struct | matrix | parse_err | sep |
|---|---|---:|---:|---:|---:|
| A | `equivalent_expr` vergleicht Matrizen (Nullmatrix statt Skalar-0) — `7353668` | 0,8143 | 0,438 | 0,1571 | 0,8125 |
| B | `parse` entfernt Whitespace (TexTeller-Zeilenumbrüche in Matrizen) — `c25755e` | 0,8857 | 0,688 | 0,0857 | 0,8125 |
| C–E | `normalize`: `smallmatrix`→`matrix`, `\|`-Matrix→`vmatrix` (Determinante), `\vspace`/`\hspace`, `\mathsf/\texttt/\textsf` — `4c8b58f` | 0,9286 | 0,812 | 0,0857 | 0,8750 |
| F | `parse` wendet **`normalize`** an (statt nur Whitespace) — `4c8b58f` | **0,9429** | **0,875** | **0,0429** | **0,875** |

Per Bucket final (dev): integral **1,000**, matrix **0,875**, trig 0,944, special 0,944.
Anchor bleibt **1,000** (`anchor-after-l45-fixes`). Alle 21 Pytest-Tests + Selftest grün.

**Wichtig (Issue #1):** Der Sprung bei B/F ist kein stilles Korrigieren — `parse` normalisiert
nur die *Darstellung* (Umgebung/Whitespace/Artefakt), nie die Rechenwahrheit. Falsche
Schülergleichungen werden weiterhin als falsch gelesen (sep 0,875 = 7/8 falsche Gleichungen
bleiben falsch erhalten).

### Holdout (einmal am Ende, unangetastet bis dahin)

| Split | struct | char | parse_err | sep | p50 | n |
|---|---:|---:|---:|---:|---:|---:|
| holdout | **0,9444** | 0,9235 | 0,0000 | 0,8750 | 0,876 s | 36 |

Per Bucket: integral **1,000**, trig **1,000**, special **1,000**, matrix 0,778 (7/9).
dev 0,943 vs holdout 0,944 → **keine Überanpassung**; beide Splits stimmen überein.

### Verbleibende Fehlermodi (ehrlich, nicht behoben)

- **Determinanten-Balken (matrix):** dev `l45_dev_22/31`, holdout `l45_holdout_12/13`. TexTeller
  liest die `\left|…\right|`-Determinante als **verstümmelte Mehrfach-Balken**
  (`\left|\!\left|\!…\right|\!\right|`, teils 3 Balken) und verwürfelt die Zellzahl. Ursache ist
  teils die Balken-Glyphe des eigenen Renderers (defekt, nicht „Tuning"), teils eine echte
  OCR-Verwechslung. Ein blindes Kollabieren mehrerer `|` → vmatrix würde die **Norm `‖M‖`**
  (Frobenius) mit der Determinante verwechseln → bewusst NICHT normalisiert.
- **Winkelklammern (trig):** `l45_dev_51` `\sin\langle\pi\rangle` statt `\sin(\pi)` — echte
  OCR-Verwechslung; globales `\langle→(` würde echte Inner-Products/Erwartungswerte korrumpieren.
- **`i`/`j` (special):** `l45_dev_56` `j^{2}=1` statt `i^{2}=1` — echte OCR-Verwechslung, ohne
  Kontext nicht sicher auflösbar (dürfte nicht geraten werden).

Alle offenen Fehler sind entweder echte OCR-Verwechslungen oder ein Renderer-Defekt — kein
Produktlogik-Fehler. Sie werden dokumentiert, nicht durch Raten „weggerechnet".

## Pass 5 — Mehrzeilige Rechenketten (Seitenstruktur, live TexTeller CPU)

### Modul & Signale

Neu `ocr/multiline.py` (`group_lines`/`page_structure`) gruppiert vertikal geordnete Zeilen
**rein strukturell** zu Rechenketten — kein Tutor, keine Schrittrichter, keine Mathe-Prüfung:

- **Fortsetzung** (Zeilen gehören zusammen): führendes `=`/`\approx`/`\equiv`/`\Rightarrow`/
  `\Leftrightarrow`/`\implies`/`\iff`/`<`/`>`/`\leq`/`\geq`/`\neq`; offener Operator
  (`+`,`-`,`\cdot`,`\times`,`=`) oder unvollständige Klammer am Zeilenende; **nackter Term**
  (ohne Relationszeichen) — Schul-Konvention wie `validator_lines` (K25); gleiche
  Variablenmenge (Gross/Klein gefaltet wegen OCR `x`/`X`).
- **Trenner** (neue Kette): grosse vertikale Lücke (> 2× Zeilenhöhe, gemessen an Ink-Höhe;
  Innenabstand der gerenderten Zeilen ~46 px vs. ~156 px zwischen Aufgaben), Aufgabenlabel
  (`1.`, `a)`, `Aufgabe`), oder andere/leere Variablenmenge ohne Fortsetzungssignal.
- Eingang: Zeilen mit `bbox=(x0,y0,x1,y1)` + `latex` (+ beliebige Felder). Zusatz-API
  `ocr/pre.py:split_lines_with_boxes` (Boxen in Seitenkoordinaten; `split_lines` delegiert
  verhaltensgleich) und `ocr/pipeline.py:recognize_page` (segmentieren → erkennen → gruppieren).

**Issue-#1-Garantien (hart, getestet):** Zeilen werden nie verändert (`latex`/`uncertain`/
`repair`/`math_status`/`alt` bleiben); **kein Domino** (Ketten tragen nur informative
`has_uncertain_step`/`uncertain_line_indices`); Schülerfehler bleiben zeilenweise erhalten.
15 Regressionstests in `tests/test_multiline.py`, 36 Pytest gesamt grün, Selftest OK.

### Echte ketten-Muster (strukturell, ohne Modell)

`bench/overnight/multiline_ketten.py` rekonstruiert die echten `kalib/ketten/last_real.jsonl`-
Lesarten einspaltig (Muster-Messung, keine Live-OCR):

| Variante | before (nur explizite Signale) | after (+ nackter Term, x/X-Fold) |
|---|---:|---:|
| within-chain recall (Ketten ≥2 Zeilen) | 23/28 = 0,821 | **28/28 = 1,000** |
| packed mit Leerzeile zwischen Aufgaben | – | **28/28 exakt, 0 verschmolzen** |

Die anfänglichen 5 Fehler waren genau die im Auftrag genannten: `x`/`X` (K01/K06/K09/K13) und
K25 mit **verschlucktem führendem `=`** (`17·3`, `3·10+3·7`, `30+21`, `41` ohne `=`) — beide
jetzt strukturell gelöst. **Grenze (ehrlich):** ohne jeden Trenner (keine Lücke, kein Label)
verschmelzen benachbarte Aufgaben gleicher Variable (1 Gruppe) — echte Seiten haben Lücke/Label.

### End-to-End live TexTeller CPU (15 Seiten, 43 Zeilen, 19 Ketten)

`bench/overnight/multiline_bench.py` rendert feste mehrzeilige Seiten (Ableitungen, Brüche,
Quadrate, Trig, Integral, `e^{iπ}`, absichtlich falsche Schritte, Mehr-Aufgaben-Seiten),
segmentiert mit `split_lines_with_boxes`, liest jede Zeile live und gruppiert:

| Metrik | Wert |
|---|---:|
| line_struct (`same` GT↔read) | 0,889 (40/45) |
| **chain_recall** | **1,000** (19/19) |
| **chain_exact_pages** | **1,000** (15/15) |
| false-merge chains | 0 |
| **student_error_preserved** | **1,000** (3/3 falsche Zeilen treu falsch) |
| **anti_domino** | **True** (100 %) |
| p50 / p95 (Linux CPU ≠ Mac MPS) | 0,475 s / 0,931 s |

**Restfehler (ehrlich):** `seg_mismatch` p04/p07 — der einfache Ink-Band-Segmentierer trennt
bei hohen Brüchen/Integralen den dünnen Bruchstrich nicht (liegt unter der Ink-Schwelle) und
erzeugt eine Zusatz-Zeile. Das ist **Segmentierung**, nicht Gruppierung (Gruppierung bleibt
korrekt, Ketten exakt) — gehört zur Matrix/Crop-Vorverarbeitung (Pass 6). Zweiter Randfall:
gleiche-Variable-Aufgaben ohne sichtbare Lücke/Label werden verschmolzen (ohne Validator nicht
auflösbar; bewusst kein Tutor).

## Pass 6 — Matrix-Crop-Vorverarbeitung + restliche Nicht-Matrix-Fehler

### Ausgangslage (real gemessen, nicht die alte 12/16-Annahme)

Die Pass-4-Grundlage hat die Matrix-Crops bereits weitgehend geheilt (Matrix **14/16 = 0,875**,
nicht 0,333). Vor Pass 6 verblieben genau **4 dev-Fehler**:

| ID | Bucket | Ursache (Inspektion) |
|---|---|---|
| `l45_dev_22`, `l45_dev_31` | matrix (vbar) | TexTeller halluziniert mehrere `\|`-Balken um die Determinante; der **Zellinhalt** (`1&2\\3&4`) wird korrekt gelesen |
| `l45_dev_51` | trig | `(` wird als `\langle` gelesen (`\sin\langle\pi\rangle`) — echte OCR-Verwechslung |
| `l45_dev_56` | special | `i`→`j` in `i^{2}=1` — Zeichendetail geht bei sehr kleinem Crop verloren |

Crop-Inspektion: **keine** Kanten-Clipping (Margins z. B. 136/17/27/17 px), keine zu niedrige
Auflösung (500–660 px breit). Die vbar-Fehler sind Modell-Halluzination, kein Crop-Defekt.

### Ein-Faktor-Experimente (live TexTeller CPU, gleiche Bilder, nur Transform variiert)

| Faktor | Ergebnis auf den 4 Fehlern | Regressionscheck | Entscheidung |
|---|---|---|---|
| **P1 Rand-Padding** (32/64 px weiß) | **flach** — identische Reads auf allen 4 | keine | **REJECT** (kein Effekt) |
| **P2 globales Upscale** (2× / Höhe 160) | `i`/`j` wird korrekt (`l45_dev_56`) | **bricht `l45_dev_21`** (funktionierende vbar-Determinante → Balken-Halluzination) | **REJECT** global (regressiv auf matrix) |
| **P2 gated Min-Höhe** (nur Crops < 96 px hochskalieren, große unangetastet) | `l45_dev_56` → `i^{2}=1`; vbar/trig unverändert | **0 Regressionen** auf dev; stabil bei min_h ∈ {96,128,160} | **KEEP** |
| **P3 Kontrast** (autocontrast) | **flach** | keine | **REJECT** (kein Effekt) |
| **F1 `\langle`→`(`** | würde `l45_dev_51` „reparieren" | würde echte Inner-Products `\langle u,v\rangle` korrumpieren = stiller Eingriff | **REJECT** (nicht geraten) |

Die vbar-Determinanten bleiben ungelöst: weder Padding noch Skalierung noch Kontrast ändern den
multi-Balken-Halluzinations-Read → echte Modell-/Renderer-Grenze, dokumentiert (kein Hack).

### Gehaltene Änderung (generalisiert, produktiv)

`ocr/pre.py:ensure_min_height(img, min_height=96)` — skaliert **nur zu kurze** Crops auf
Mindesthöhe (Seitenverhältnis erhalten, LANCZOS), bereits große Bilder bleiben unverändert.
Verdrahtet in `ocr/formula.py:recognize` (TexTeller-Input; GLM unverändert) sowie in den
Benchmarks (`level45`, `benchmark`, `multiline_bench`), damit die Messung exakt den Produktpfad
abbildet. Reine Bild-Vorverarbeitung: keine Zeile/Mathematik wird verändert (Issue #1 unberührt).

### Ergebnisse (dev / holdout / Anker)

| Metrik | Pass 5 (vorher) | Pass 6 (nachher) |
|---|---:|---:|
| dev struct (70) | 0,943 | **0,957** |
| dev integral / matrix / trig / special | 18/18 / 14/16 / 17/18 / 17/18 | 18/18 / 14/16 / 17/18 / **18/18** |
| dev student_error_preserved | 14/16 = 0,875 | **15/16 = 0,938** (dev_56 jetzt treu gelesen) |
| Holdout struct (36) | 0,944 | **0,944** (keine Divergenz/Überanpassung) |
| Holdout matrix | 7/9 | 7/9 (2 vbar, unverändert) |
| Anker `overnight_synth` (50) | 1,000 | **1,000** |
| Multiline E2E chain_recall / exact | 1,000 / 1,000 | **1,000 / 1,000** (Studentenfehler 1,000, Anti-Domino True) |
| Pytest | 36 | **40** (inkl. 4 neue `ensure_min_height`-Tests) |
| Latenz dev / holdout / multiline p50 | – | 0,697 s / 0,573 s / 0,568 s |

Ehrlich: der Gewinn ist **+1 dev-Item** (kleiner Crop `i^{2}`); Holdout unverändert (der i/j-Fall
tritt dort nicht auf), Anker und Mehrzeilen unberührt. Die Änderung ist sicher (nur zu kurze
Crops, keine Regression), aber bewusst kein „großer" Sprung — die 2 vbar-Determinanten und
`\langle` bleiben echte Modellgrenzen.

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

# Pass 5: Mehrzeilen-Ketten
venv/bin/python -m pytest tests/test_multiline.py -q                 # Gruppierungs-Regressionen
venv/bin/python bench/overnight/multiline_ketten.py --tag "notiz"    # echte ketten-Muster (ohne Modell)
venv/bin/python bench/overnight/multiline_bench.py --tag "notiz"     # live TexTeller, mehrzeilige Seiten
```
