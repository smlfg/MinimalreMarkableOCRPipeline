# Mathe-OCR Modelltest — Stand 2026-11-24

**Stufe 0 (Rohlauf, OHNE Optimierung).** Greedy-Decoding, keine Vor-/Nachbearbeitung, keine Kohärenzschicht, kein Tuning.
Die Zahlen sind eine **Baseline**, kein Endergebnis. Mission: `M-20261124T194047-0dbdbb55`. Branch: `bench/mathocr-models` (Worktree `../MathOCR-ModelBench`).
Produktionspipeline (`ocr/`) unverändert. Entscheidung über ein Produktionsmodell liegt beim Owner.

## Behalten und in den Benchmark eingetragen
| Modell | Revision | Roh-struct deine Schrift (Formeln / Ketten) | synth_hard | Rettet TexTeller (von 123) |
|---|---|---|---|---|
| phxember/Uni-MuMER-Qwen3-VL-2B | 26d57451 | 75 % / 85 % | 78 % | 62 |
| bhaskar1707/qwen3.5-latex-ocr-finetune (v1) | 4a18f87c | 70 % / 80 % | 89 % | 70 |
| Referenz TexTeller allein | – | 82 % / 92 % | 60 % | – |
Zeilen: `bench/formula_flywheel/results_models.tsv` (gleiche Spalten wie `results.tsv`). Rohausgaben: `raw/<modell>/<split>.jsonl`. Auswertung: `BENCHMARK_RESULTS.csv`, `per_item.jsonl`.
Nicht zu Ende gerechnet (vom Owner gestoppt): bhaskar_v2 (fertig, schwach auf eigener Schrift), clzoro_2b (549/662, vermutlich Adapterproblem), alle übrigen. aditya blockiert (Fremdcode), clzoro_8b nicht gelaufen (17,5 GB).

## Reproduzieren
```bash
cd bench/model_bench                      # im Worktree
../../.venv_mb/bin/python -I mb_fetch.py uni_qwen3vl_2b          # pinned Gewichte (nur *.safetensors)
../../.venv_mb/bin/python -I mb_run.py --model uni_qwen3vl_2b --split own_probe --limit 5 --tag smoke
../../.venv_mb/bin/python -I mb_run.py --model uni_qwen3vl_2b --split own_probe,own_ketten,synth_hard,dev,synth
../../.venv_mb/bin/python -I mb_score.py                         # -> BENCHMARK_RESULTS.csv
```
venv `.venv_mb`: torch 2.15.0, transformers 5.24.1, sympy 1.14.0, latex2sympy2_extended 1.11.0, RapidFuzz 3.14.6 (Scoring identisch zu `.venv_structure`). `test`-Split nie angefasst.

## NEXT STEP — Flywheel auf ~100 %
Ziel laut `bench/formula_flywheel/program.md`: struct und char ≥ 99 %, p95 < 2 s, am Ende zählt nur die eigene Schrift. 100 % ist das Ziel der Schleife, keine Zusage.
Die Rohwerte oben sind die Ausgangslage der Schleife; aktuell darunter: eigene Schrift 70–85 % (Pipeline TexTeller+GLM: 90 %).
Regeln (damit am Ende nicht „wer besser getunt wurde“ gewinnt):
1. **Stufe 1 — gemeinsame Pipeline:** gleiche Vor-/Nachbearbeitung für beide Modelle (Höhe 128 + Rand, Graustufen, Dezimalkomma, Stop-Reste), einmal festgelegt.
2. **Stufe 2 — Modell-Tuning mit gleichem Budget** (gleiche Zahl Versuche je Modell): Bildgröße/`max_pixels`, Prompt, Padding, Beam-Suche. Gesucht nur auf `train`/`dev`, Kontrolle auf `dev`.
3. **Zweite-Meinung-Einbindung:** beide als zusätzliche Stimme neben TexTeller+GLM prüfen (Kennzahl „Rettet TexTeller“). Uni-MuMER stark auf Fremdschrift (dev 18/34), bhaskar_v1 auf Integrale/Summen (45/55) — ergänzen sich.
4. **Stille Korrekturen messen:** falsche Rechenschritte müssen falsch bleiben (11 von 60 Kettenschritten sind absichtlich falsch); jede Stufe wird darauf geprüft.
5. **Endmessung** auf eigener Schrift ohne dort getunt zu haben; `test` bleibt Holdout. Grenzen: 100 Bilder, ein Schreiber, ein Seed.
Optuna-Infrastruktur liegt bereits in `bench/formula_flywheel/optuna_study.py` (andere Mission, Kohärenzschicht).
