# Benchmarks — Fast `<1000 ms` Local OCR Evaluation

**Hardware / Setup:** Apple M3 Max, `OMP_THREAD_LIMIT=1`, festes `< 1000 ms/Zeile`-Gate (`data/arena/arena_results.tsv`).

## Datensatz (`data/consensus/manifest.tsv`)

- **Quelle:** `265` echte `.rm`-Seiten aus `45` aktiven reMarkable-Notizbüchern → `752` extrahierte Zeilen.
- **Labeling (Two-Pass Dual-VLM):** Pass 1 `glm-ocr:q8_0` (`752` Zeilen) → Vorfilterung (`640`) → Pass 2 `qwen2.5vl:7b`, behalten bei `>= 90 %` Übereinstimmung.
- **Ergebnis:** **`247` Konsens-Zeilen** aus `36` Notizbüchern (`403` verworfen) + `100` synthetische Gleichungen (`seed=1`):
  - `real_math`: **57** | `real_text_dev`: **129** | `real_text_holdout`: **61** (Notizbuch-disjunkt)

## 1. Fast-OCR Hauptlauf (`n=247` Real + `n=100` Synth)

| Variante | Engine | Math | Dev | Holdout | **Real All** | Synth Exact | ms/Zeile | Gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **`vision_batch_acc`** (`raw`, `--batch`) | AppleVision | 89.1% | **87.1%** | **86.3%** | **87.4%** | 47.0% | 40.7 ms | OK |
| `vision_batch_bold` (`ink_crop+bold`) | AppleVision | 85.8% | 83.6% | 84.0% | 84.2% | **55.0%** | **39.6 ms** | OK |
| `vision_batch_s2` (`ink_crop+bold+scale=2`) | AppleVision | 88.2% | 80.0% | 86.0% | 83.4% | 54.0% | 51.6 ms | OK |
| `vision_batch_s3` (`ink_crop+bold+scale=3+min_h=0`) | AppleVision | **89.6%** | 79.0% | 84.6% | 82.8% | **55.0%** | 71.9 ms | OK |
| `vision_batch_s2_nc` (`scale=2`, `correct=0`) | AppleVision | 86.5% | 80.2% | 83.8% | 82.5% | 52.0% | 50.1 ms | OK |
| `rapidocr_raw` (PP-OCRv4 ONNX, `raw`) | RapidOCR | 56.5% | 59.0% | 58.4% | 58.3% | **65.0%** | 145.7 ms | OK |
| `rapidocr_bold` (PP-OCRv4 ONNX, `crop+bold`) | RapidOCR | 58.2% | 55.9% | 58.1% | 57.0% | 45.0% | 147.1 ms | OK |
| `tess_best_bold` (`tessdata_best`, `crop+bold+p7`) | Tesseract | 58.5% | 51.9% | 52.4% | 53.5% | 54.0% | 172.8 ms | OK |
| `tess_fast_bold` (`tessdata_fast`, `crop+bold+p7`) | Tesseract | 49.3% | 52.7% | 52.4% | 51.8% | 52.0% | 126.0 ms | OK |

## 2. Ausgeschiedene Kandidaten & Small-N Overfitting (`n=23` Vorlauf)

| Befund | `n=23` Real | `n=247` Real | Synth | Latenz | Entscheidung |
|---|---:|---:|---:|---:|---|
| `vision_batch_s3` vs `vision_batch_acc` | 89.9% vs 86.4% | **82.8% vs 87.4%** | 55% vs 47% | 72 vs 41 ms | Raw-Default schlägt globales `bold+s3` |
| `lfm3_vl_raw` (Ollama `lfm3-vl:latest`) | 29.5% (`16.7%` Hold) | — | **72.0%** | 393 ms | Zu schwach auf echter Handschrift |
| `vision_batch_fast` (`--level fast`) | 17.7% | — | 41.0% | 8 ms | Unbrauchbar auf Handschrift |
| `rapid_latex_raw` / `rapid_latex_crop` | 0.4% / 0.0% | — | 0–1% | 510 / 1519 ms | Nur LaTeX-Druck; `crop` = `TOO_SLOW` |

## 3. Vorläufer Tesseract-Ceiling (`40` Notizbücher, `glm-ocr:q8_0`-Referenz)

- `B1_bold_deu_p7` (`tessdata_fast`): `42.9%` Real (`42.0%` Dev, `44.3%` Holdout, `51.5%` Synth).
- `load_system_dawg=0` und `language_model_penalty_non_dict_word=0.05` blieben unter `--oem 1` (LSTM-only) wirkungslos (`42.9%`).
- `T3_min_linesize=1.5` (`43.7%` Dev / `39.8%` Holdout) und `E3_psm_13` (`32.6%`) überfitteten und wurden per Holdout-Gate verworfen.
