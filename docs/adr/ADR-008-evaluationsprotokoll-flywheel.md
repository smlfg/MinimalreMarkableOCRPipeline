# ADR 008: Evaluationsprotokoll und Flywheel (nach karpathy/autoresearch)

**Status:** angenommen, 23.11.2026 · **Bezug:** ADR-002 (Metriken) · **Code:** `bench/formula_flywheel/`, `bench/structure_bench.py`

## Kontext

Vorgänger sind an ungemessenen Baselines, fehlender GT und Optimieren ohne Gate gescheitert. Öffentliche Datensätze haben verrauschte GT (MathWriting: Bild `0.605`, GT `0.005`; Bild `α`, GT `a`) – dort ist 99 % nicht messbar. Ziel ist die **eigene Schrift**; gelernt werden darf aus fremden Daten, damit die Pipeline nicht 1:1 auf eine Person overfittet.

## Entscheidung

**Struktur (aus autoresearch, MIT):**
- `prepare.py` und `models.py` sind eingefroren (Splits, Metriken, Modellaufrufe mit Cache inkl. echter Sekunden).
- Veränderbar ist nur der Produktcode `ocr/formula.py` und `ocr/coherence.py`; `bench/formula_flywheel/pipeline.py` ist ein Adapter mit gecachten Engines. Jedes Experiment: Hypothese → Commit → `run.py` → Zeile in `results.tsv` → behalten oder zurückdrehen. Regeln in `program.md`.

**Splits (Hash der GT, fest):** `train` 1823 (Lernen erlaubt), `dev` 326 (Entscheidungen), `test` 485 (Holdout, nur Meilensteine), `synth` (Generator aus SchlangebeißtinSchwanz, saubere GT), `own_*` (Kalibrierungsblätter = Ziel-Messung).

**Metriken:** Struktur = `sympy_equal` (Bruch/Exponent/Index richtig verschachtelt), Zeichen = 1 − CER auf normalisiertem LaTeX, Latenz p95, selektive Präzision + Abdeckung.

**Metrik v2 (`normalize`)** zählt gleich gerenderte Schreibweisen als gleich: `\ge`/`\geq`, `x^2`/`x^{2}`, `\gt`/`>`, `\limits`, `f^{'}`/`f'`, `ln`/`\ln`, `^{o}`/`^{\circ}`. Nach jeder Metrikänderung werden alle Vergleichsläufe neu bewertet.

**GT-Regeln:**
- GT wird in fremden Datensätzen nie korrigiert, auch bei offensichtlichem Fehler.
- **Eigene Schrift: GT = was tatsächlich geschrieben wurde.** Abschreib-Abweichungen von der Vorlage werden markiert und vom Owner bestätigt, nicht als Lesefehler gezählt.

**Kalibrierungsblätter** (`data/kalib/`): Vorlage mit bekannter GT, Owner schreibt ab. Slots kommen aus dem Vorlagen-Layout (keine Zeilensegmentierung nötig); `kalib_eval.py` holt Striche per SSH, rendert je Slot ein PNG, misst. Blätter: Probeblatt (40 Zeilen, Verwechsler + Schulmathe), Uni-Blatt (30 Rechenschritte aus Klausur SS26, mit Quellenangabe), Ketten-Blatt `own_ketten` (28 Rechenketten mit eingebauten Fehlern, End-to-End-Metrik, siehe ADR-009).

## Stand 23.11.

| Split | Struktur | Zeichen | p95 |
|---|---:|---:|---:|
| own_probe (40) | 90 % (95 % gegen Geschriebenes) | 93,4 % | 0,23 s |
| dev (326) | 89,6 % | 97,2 % | 0,32 s |
| synth (100) | 91 % | 98,7 % | – |

## Folgen

- Seitenstruktur (Zeilen finden, Reihenfolge, Kette) ist **nicht** gemessen; dafür braucht es freie Seiten mit GT.
- `train` ist noch ungenutzt; erster Lernschritt: Verwechslungsprior aus `own_*`, dann LoRA auf train + synthetisch-eigene Glyphen.
