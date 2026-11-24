# Benchmark-Protokoll: Overnight-Branches gegen `main` (2026-11-24)

## Ergebnis in einem Satz

**Auf deinen Kalibrier- und Synth-Daten bringen beide Branches keinen messbaren Gewinn;
auf den echten Ketten und auf L4 sind sie je eine Nachfrage schlechter.** Auf den Matrizen
(L6), dem Hauptziel der Branches, sind die Vorhersagen Zeichen für Zeichen identisch mit `main`.
Empfehlung: **nicht mergen als Qualitätsgewinn**. Einzelne Teile (Mehrzeilen, Gate) nur mit
eigener Messung prüfen (siehe „Was als Nächstes").

## Frage und Paket

Verbessern `experiment/ocr-overnight-20261124` (A, `fa44a68`) und
`experiment/ocr-overnight-opencode-20261124` (B, `9526123`) die Pipeline gegenüber
`main` (`601e6e3`) auf den Kalibrier- und Synth-Daten?

- Harness `bench/chain_bench.py` (Arbeitsbaum, uncommittet: `--gt/--rows`; `judge/score/f1`
  unverändert), in alle Varianten kopiert. Metrik: ADR-009-F1, Nachfrage zählt strict falsch.
- Engines live, ohne Cache (die Branches ändern Bilder vor der Erkennung): TexTeller-Worker
  (`.venv_tt`, MPS) + `glm-ocr:q8_0` via Ollama. Je Variante ein Worktree (inzwischen entfernt).
- Matrizen/Formeln werden mit dem Bewerter von `main` ausgewertet, nicht mit dem des Branches.
- Skripte und Rohvorhersagen: `bench/evidence_branches_2026-11-24/`.

## Was die Branches wollten (laut ihrer eigenen Doku) und was gemessen wurde

| Ziel der Branches | Eigene Messung (Linux-CPU, matplotlib-Rendering, **nicht Handschrift**) | Hier gemessen (Handschrift-Simulator bzw. echte Schrift) |
|---|---|---|
| Issue 1: nie still Reparatur durchlassen (`trusted=False`) | Sicherheitstests grün | Kostet **eine Nachfrage mehr** (K24 und eine L4-Kette), kein Gewinn bei Fehlalarmen |
| TexTeller-Artefakte normalisieren (`\mbox`, `array`, `\text{sin}`) | Struktur 0,90 → 1,00 auf 50 gerenderten Formeln | L5 (150 Formeln): 0,573 → 0,573 (A) / 0,580 (B). Ein Treffer von 150 |
| Matrizen lesen/normalisieren | 0,00 Baseline; weitere Passes | **L6 (165 Zeilen): 0,109 für alle drei, Vorhersagen identisch** |
| Mehrzeilen-Gruppierung (`ocr/multiline.py`) | Eigene Suiten | **Nicht gemessen** (dein Harness hat keinen Mehrzeilen-Pfad) |

Der Grund, warum eigene und fremde Messung auseinanderliegen: Die Branches wurden an
gerenderten Formeln mit TexTeller-Ausgaben auf Linux-CPU getunt, ohne GLM und ohne
Handschrift. Dein Datensatz ist Handschrift bzw. ein Schriftsimulator mit GLM-Zweitmeinung.

## Messwerte

### Echtes Kalibrierblatt (28 Ketten, 15 mit eingebautem Fehler)

| Variante | F1 strict | acc_err | acc_ok | Nachfragen |
|---|---|---|---|---|
| main | **1,000** | 1,000 | 1,000 | 0 |
| A | 0,960 | 1,000 | 0,923 | 1 (K24) |
| B | 0,960 | 1,000 | 0,923 | 1 (K24) |

K24 (korrekte Kette): TexTeller liest `3·7` als `37`, GLM liest richtig. `main` akzeptiert
die GLM-bestätigte Reparatur als sicher; A und B setzen jede Reparatur auf unsicher →
Nachfrage. Bewusste Design-Entscheidung (Issue 1), kein Zufall.

### Synthetische Ketten (campaign_v3)

| Messung | main | A | B |
|---|---|---|---|
| Stichprobe 20 pro Level L1–L4 (80 Ketten, Seed 2026) | F1 1,000 | 1,000 | 1,000 |
| L4 komplett (150 Ketten, 65 mit Fehler) | F1 0,930, 11 Fehltreffer | 0,924, 12, 1 Nachfrage | 0,924, 12, 1 Nachfrage |

Gemeinsame 11 Fehltreffer auf L4: Malpunkt `·` wird als `.` gelesen (Stufe ③ OCR).
L1–L3 sind zu leicht, um zu trennen.

### Synthetische Formeln

| Messung | main | A | B |
|---|---|---|---|
| L5 (150 schwere Formeln) struct | 0,573 | 0,573 | 0,580 |
| L5 coverage / prec_certain | 0,567 / 0,988 | 0,567 / 0,988 | 0,573 / 0,988 |
| L6 (165 Matrixzeilen) struct | 0,109 | 0,109 | 0,109 |

L5 nach Thema (alle gleich): Bruch 1,00, π 1,00, Algebra 0,92 (B: 0,96), Integral 0,72,
Wurzel 0,47, Summe 0,00 (Σ-Glyph-Problem des Simulators, kein Pipeline-Fehler).
L6: TexTeller liest Matrizen als `\begin{matrix}` mit Klammern und lässt die `&`-Trenner weg
(`44` statt `4&4`). Das ist Strukturverlust vor jeder Nachbearbeitung; keine Variante
rekonstruiert ihn.

### Mehrzeilen-Pfad (`ocr/multiline.py`, nur in den Branches vorhanden)

`main` hat keinen Mehrzeilen-Pfad, es gibt also **keine Baseline**: Die Zahlen zeigen nur, dass
das Feature in den Branches funktioniert, nicht dass es besser als `main` ist. Alle Seiten sind
mit matplotlib gerendert (nicht Handschrift), die Suites haben 12 bzw. 9 Seiten (kein 50er-Batch
vorhanden, daher komplett gelaufen). TexTeller live auf MPS, ohne GLM.

| Suite (Branch) | Seiten | Zeilen-struct | Ketten-Grenzen | Anti-Domino | Schülerfehler erhalten |
|---|---|---|---|---|---|
| `multiline_live` (A) | 12 | 1,000 | 1,000 | 0 Verstöße | 1,000 |
| `multiline_multitask_live` (A) | 9 | 0,969 | 1,000 | 0 Verstöße | 1,000 |
| Kalib-Ketten, Gruppierung auf GT-Zeilen (A) | 28 Ketten | – | 1,000 | – | – |
| `multiline_ketten` (B), Gruppierung auf gelesenen Zeilen | 28 Ketten | – | 28/28 (mit Leerzeile) | – | – |

B: Ohne Trenner (Lücke/Label) verschmelzen alle 28 Ketten zu einer Gruppe, das ist laut
Skript die bekannte Grenze. `multiline_bench.py` (B, Rendern + Live-TexTeller) lief **nicht**:
sie braucht matplotlib und TexTeller im selben Interpreter, das gibt es hier nicht, und ich
habe nichts installiert. Rohausgaben: `A_multiline_*.json`, `B_multiline_ketten.txt`.

Aussage: Das Mehrzeilen-Feature ist der einzige echte Funktionsgewinn der Branches. Gemessen
ist es nur auf sauber gerenderten Seiten, nicht auf deiner Handschrift.

## Bewertung

1. **Keine Verbesserung belegt.** Wo die Varianten sich unterscheiden (K24, eine L4-Kette),
   ist der Branch schlechter, und zwar genau durch die Issue-1-Regel.
2. **Die Branches sind für etwas anderes gebaut:** Sicherheit (nie still reparieren) und
   Mehrzeilen-Erkennung. Das erste ist ein Kompromiss (eine Nachfrage statt einer stillen,
   korroborierten Korrektur), das zweite hat dein Harness nicht abgedeckt.
3. **Matrix-Problem ungelöst**, in allen Varianten.

## Gültigkeit und Grenzen

- Ein Schreiber (echte Ketten), synthetische Schrift sonst, ein Seed. Die 28 Kalibrierketten
  haben `main` getunt; der Vergleich ist dort zugunsten von `main` verzerrt.
- Nicht gemessen: Mehrzeilen-Pfad auf Handschrift (nur gerenderte Seiten), B's
  `multiline_bench.py`, `synth_ketten` (143), Tests der Branches (pytest). Die Rohzeilen der Kettenläufe (28/L4) sind nicht gesichert (Worktrees entfernt);
  nur L6-Vorhersagen liegen im Evidenzordner.
- Voller 840-Ketten-Lauf wurde abgebrochen und durch Stichprobe + L4/L5/L6 ersetzt.

## Was als Nächstes (falls du die Branches weiter prüfen willst)

1. Mehrzeilen-Gruppierung auf **deiner Handschrift** messen (mehrzeiliges Kalibrierblatt
   schreiben). Bisher nur auf gerenderten Seiten belegt.
2. Entscheiden, ob Issue 1 (nie still reparieren) eine Nachfrage pro ~75 Ketten wert ist.
3. Ein neues Kalibrierblatt mit Matrizen und Integralen auf Papier schreiben; die
   Matrix-Lücke ist ein Lesefehler (`&`) und braucht echte Daten.
