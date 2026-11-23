# Formel-OCR-Flywheel (abgeleitet von karpathy/autoresearch, MIT)

Ziel: Handschrift → LaTeX. Struktur (sympy_equal) ≥ 99 %, Zeichen (1−CER) ≥ 99 %, p95 < 2 s pro Formel.
Am Ende zählt nur die eigene Schrift des Owners (Gold-Set aus reMarkable-Seiten, kommt später als Split `own`).

## Dateien
- `prepare.py`: EINGEFROREN. Splits, Bewertung, Metriken. Nie ändern.
- `models.py`: EINGEFROREN. Modellaufrufe und Cache (latex + echte Sekunden).
- `pipeline.py`: dünner Adapter auf `ocr/formula.py` mit gecachten Engines. MUTIERBAR sind `ocr/formula.py` und `ocr/coherence.py` (Produktcode).
- `results.tsv`: jede Zeile ein Experiment (keep, discard oder crash in der Beschreibung).

## Splits (Hash der GT, fest)
- `train`: Lernmaterial (Regeln, Selektor, Kalibrierung, Fine-Tuning). Darf beliebig benutzt werden.
- `dev`: Entscheidungsgrundlage der Schleife. Kein Lernen auf dev.
- `test`: Holdout. Nur an Meilensteinen messen, nie für Entscheidungen.

## Schleife
1. Hypothese aufschreiben (eine Zeile).
2. `pipeline.py` ändern, committen.
3. `python run.py "<hypothese>"` → dev-Metriken.
4. Besser in struct (bei gleicher oder besserer Latenz unter 2 s): behalten. Sonst `git reset --hard HEAD~1`.
5. Alle ~5 Keeps einmal `run.py "<meilenstein>" test`. Wenn dev und test auseinanderlaufen, ist das Overfitting → zurückdrehen.

## Regeln gegen Selbstbetrug
- Keine Regel, die eine einzelne dev-Formel auswendig lernt. Regeln und Gewichte nur aus `train` ableiten.
- GT wird nie korrigiert. Verdacht auf GT-Fehler wird notiert, zählt aber als falsch.
- Einfachheit: Ein kleiner Gewinn mit viel Code wird nicht behalten.
- Unsicher markieren ist erlaubt (`uncertain`) und wird separat als Abdeckung und Präzision berichtet.
