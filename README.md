# MinimalreMarkableOCRPipeline

Minimale, vollständig nachvollziehbare OCR-Pipeline und Dual-Track-ML-Flywheel für das reMarkable Paper Pro:

`reMarkable (USB) -> .rm -> .svg -> .png -> Pre (ocr/pre.py) -> Engine (ocr/engine.py) -> Post (ocr/post.py) -> TXT`

## Projektstruktur

```text
MinimalreMarkableOCRPipeline/
├── README.md
├── .gitignore
├── tablet/
│   ├── fetch.py          # Einzelauswahl (Top-5-Notizbücher & Seite) -> data/real_val/
│   ├── sync_corpus.py    # Zieht alle aktiven .rm-Seiten (>=5 KB) per USB-tar -> data/real_corpus/
│   ├── runonce.sh        # Einzellauf: scp (.rm) -> rmc (.svg) -> rsvg-convert (.png)
│   └── ocr.sh            # Eigenständiger Tesseract-Einzellauf auf eine PNG-Datei
├── ocr/                  # Schlankes Produkt-Core (407 Zeilen gesamt)
│   ├── pre.py            # Stufe 1: nur Bild -> Bild (split_lines, ink_crop, bold, scale)
│   ├── engine.py         # Stufe 2: Bild -> Roh-Output (Tesseract & Apple Vision Swift CLI)
│   ├── vision_ocr.swift  # Native macOS Apple-Vision-Binary (Single + --batch JSON)
│   ├── post.py           # Stufe 3: Roh-Output -> Endtext + Metriken (norm, accuracy)
│   └── pipeline.py       # Dünner Orchestrator (raw + final getrennt) & Einzelbild-CLI
├── bench/                # Offline/Live Benchmark-Harness (sauber getrennt, nicht im Produkt-Core)
│   ├── ollama.py         # Reiner HTTP Keep-Alive Transport für lokales Ollama
│   ├── vlm_consensus.py  # Two-Pass Dual-VLM-Konsens-GT (glm-ocr -> qwen2.5vl)
│   ├── ocr_runners.py    # Fast-OCR (<1s) Varianten & Batch-Worker-Runner
│   ├── arena_ui.py       # HTML/SVG Pareto- & Sample-Renderer (max. 60 lazy Zeilen)
│   ├── live_arena.py     # Dünner Live-Arena Orchestrator (SSE Browser-UI + --once HTML)
│   ├── wave2_worker.py   # Isolierter RapidOCR ONNX-Worker (.venv_wave2)
│   ├── synth.py          # Virtual-Pen .rm->.png Curriculum + deterministischer Cache
│   └── flywheel.py       # M3-Max-Runner (--mode dual | --mode stress)
├── docs/
│   ├── BENCHMARKS.md     # Verdichtete Messwerte über alle Läufe (n=247 Real + Synth)
│   └── ADR.md            # Kompakte Architecture Decision Records (ADR-001..004)
└── data/                 # .rm-Korpus, tessdata_best, Konsens-GT, Benchmarks & HTML (gitignored)
```

| Datei | Zeilen | Aufgabe |
|---|---:|---|
| `tablet/fetch.py` | 194 | USB-SSH-Auswahl (Top-5-Notizbücher & Seite) nach `data/real_val/` |
| `tablet/sync_corpus.py` | 91 | Bulk-Sync aller nicht-leeren Notizbuch-`.rm`-Seiten über USB-`tar` |
| `tablet/runonce.sh` | 24 | Einzellauf `.rm` → `.svg` → `.png` |
| `tablet/ocr.sh` | 23 | Direkter Tesseract-Aufruf auf eine PNG-Datei |
| `ocr/pre.py` | 58 | Stufe 1 (`Image -> Image`): `split_lines`, `ink_crop`, `bold`, `scale` |
| `ocr/engine.py` | 105 | Stufe 2 (`Image -> Raw`): Tesseract (`tessdata_best`/flags) & Apple Vision |
| `ocr/vision_ocr.swift` | 64 | Natives macOS Apple Vision Binary (`--level`, `--correct`, `--min-height`, `--batch`) |
| `ocr/post.py` | 97 | Stufe 3 (`Boxes -> Text`): Post-Processing & Metriken (`norm`, `levenshtein`, `accuracy`, `diff_tags`) |
| `ocr/pipeline.py` | 83 | Orchestrator (`run_detailed` liefert `raw` + `final`) & Einzelbild-CLI |
| `bench/ollama.py` | 47 | Reiner Keep-Alive Ollama HTTP-Client (`OllamaClient`) |
| `bench/vlm_consensus.py` | 176 | Two-Pass Dual-VLM Konsens-Builder (`glm-ocr:q8_0` → `qwen2.5vl:7b`) nach `data/consensus/` |
| `bench/ocr_runners.py` | 167 | Fast-OCR-Varianten (`VARIANTS`) & Prozess-/Worker-Evaluation |
| `bench/arena_ui.py` | 71 | HTML/SVG Pareto- & Sample-Renderer für die Arena (`loading="lazy"`, 60 Samples) |
| `bench/live_arena.py` | 145 | Dünner Orchestrator: `<1000 ms` Browser-Arena (`http://127.0.0.1:8787`) & `--once` |
| `bench/wave2_worker.py` | 55 | Isolierter ONNX-Worker für `.venv_wave2` (`rapidocr`, `rapid_latex`) |
| `bench/synth.py` | 90 | Virtual-Pen-Curriculum (`data/synth/`), `make_case`, `ensure_dataset` |
| `bench/flywheel.py` | 298 | Dual-Track (`--mode dual`) & Stress-Test (`--mode stress`) |

## Schnellstart

```bash
# 0. Apple Vision CLI einmalig kompilieren (macOS, keine externen Abhaengigkeiten)
swiftc -O ocr/vision_ocr.swift -o ocr/vision_ocr

# 1. Echte .rm-Seiten vom reMarkable (USB) nach data/real_corpus/ synchronisieren
python3 tablet/sync_corpus.py

# 2. Dual-VLM-Konsens-GT auf den echten Seiten bauen (Two-Pass mit Cache)
python3 -u bench/vlm_consensus.py --candidates 1000 --max-per-nb 40 --workers 12

# 3. Einzelnes Bild mit getrennter RAW- und POST-Ausgabe testen
python3 ocr/pipeline.py data/real_val/lines/01_ocr_p01_line03.png

# 4. Fast-OCR Live-Arena (<1000 ms Guardrail) im Browser oder einmalig ausführen
python3 bench/live_arena.py                          # Live SSE UI auf http://127.0.0.1:8787
python3 -u bench/live_arena.py --once --synth-n 100  # Speichert data/arena/arena_latest.html + .tsv
```

Detaillierte Benchmarks und Architekturentscheidungen liegen kompakt in [docs/BENCHMARKS.md](docs/BENCHMARKS.md) und [docs/ADR.md](docs/ADR.md).

## Verifizierte Messwerte (2026-11-23, Apple M3 Max, `< 1000 ms/Zeile` Gate)

### Fast-OCR Arena auf skaliertem Datensatz (`247` Konsens-Zeilen aus `36` Notizbüchern: `57 Math` / `129 Dev` / `61 Holdout` + `100` Synth)

Erstellt aus `752` extrahierten Kandidaten über `265` echte `.rm`-Seiten mittels Two-Pass Dual-VLM (`glm-ocr:q8_0` → `qwen2.5vl:7b`, `>= 90 %` Übereinstimmung), geprüft auf den `9` schnellen (`< 200 ms`) OCR-Kandidaten:

| Variante | Engine | Real Math | Real Dev | Real Holdout | **Real All** | Synth Exact | ms/Zeile | `<1s` Gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **`vision_batch_acc`** (`raw`, `--batch`) | AppleVision | 89.1% | **87.1%** | **86.3%** | **87.4%** | 47.0% | 41 ms | OK |
| `vision_batch_bold` (`ink_crop+bold`) | AppleVision | 85.8% | 83.6% | 84.0% | 84.2% | **55.0%** | **40 ms** | OK |
| `vision_batch_s2` (`ink_crop+bold+scale=2`) | AppleVision | 88.2% | 80.0% | 86.0% | 83.4% | 54.0% | 52 ms | OK |
| `vision_batch_s3` (`ink_crop+bold+scale=3+min_height=0`) | AppleVision | **89.6%** | 79.0% | 84.6% | 82.8% | **55.0%** | 72 ms | OK |
| `vision_batch_s2_nc` (`scale=2`, `correct=0`) | AppleVision | 86.5% | 80.2% | 83.8% | 82.5% | 52.0% | 50 ms | OK |
| `rapidocr_raw` (PP-OCRv4 ONNX, `raw`) | RapidOCR | 56.5% | 59.0% | 58.4% | 58.3% | **65.0%** | 146 ms | OK |
| `rapidocr_bold` (PP-OCRv4 ONNX, `crop+bold`) | RapidOCR | 58.2% | 55.9% | 58.1% | 57.0% | 45.0% | 147 ms | OK |
| `tess_best_bold` (`tessdata_best`, `crop+bold+deu+eng+p7`) | Tesseract | 58.5% | 51.9% | 52.4% | 53.5% | 54.0% | 173 ms | OK |
| `tess_fast_bold` (`tessdata_fast`, `crop+bold+deu+eng+p7`) | Tesseract | 49.3% | 52.7% | 52.4% | 51.8% | 52.0% | 126 ms | OK |

- **Schlüsselerkenntnis durch Dataset-Skalierung (`23` → `247` Zeilen):**
  - Auf `n=23` schien `vision_batch_s3` (`ink_crop+bold+scale=3`: `89.9%`) besser als `vision_batch_acc` (`raw`: `86.4%`). Auf `247` Zeilen drehte sich das Bild klar um: **Unverändertes Apple Vision (`vision_batch_acc`: `87.4%` Real All, `86.3%` Holdout, `41 ms`)** generalisiert am besten, während pauschales `bold` + `scale=3` auf normaler Handschrift (`Dev` `87.1% → 79.0%`) überkorrigiert und nur auf Mathe minimal zulegt (`89.6%` vs `89.1%`).
  - Auch im Mittelfeld klärte `n=247` die Rangfolge: `rapidocr_raw` (`58.3%`, `146 ms`) schlägt sowohl `rapidocr_bold` (`57.0%`) als auch `tess_best_bold` (`53.5%`, `173 ms`).
  - **Produkt-Fazit (Keep It Simple):** Natives `ocr/vision_ocr` (`64` Zeilen Swift, `--level accurate --batch`, `41 ms/Zeile`) ohne künstliche `bold`-Eindickung auf normalem Text — erst für gezielte HPO/Post-Processing (z. B. isolierte Ziffern oder `-`-Rettung bei Mathe) nachschärfen.

### Vorläufer Multi-OCR Arena Welle 2 (`23` Zeilen — inkl. langsamerer/verworfenener Modelle)

| Variante | Engine | Real Math | Real Dev | Real Holdout | **Real All** | Synth Exact | ms/Zeile | `<1s` Gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `vision_batch_s3` (`ink_crop+bold+scale=3+min_height=0`) | AppleVision | 94.8% | 88.8% | 83.8% | 89.9% | 55.0% | 66 ms | OK |
| `vision_batch_acc` (`raw`, `--batch`) | AppleVision | 86.4% | 91.1% | 80.1% | 86.4% | 47.0% | 42 ms | OK |
| `lfm3_vl_raw` (Ollama `lfm3-vl:latest`, warm GPU) | VLM | 42.0% | 25.0% | 16.7% | 29.5% | **72.0%** | 393 ms | OK |
| `vision_batch_fast` (`--level fast`, `crop+bold`) | AppleVision | 28.6% | 14.0% | 6.2% | 17.7% | 41.0% | 8 ms | OK |
| `rapid_latex_raw` (`rapid-latex-ocr` ONNX) | RapidLaTeX | 1.0% | 0.0% | 0.0% | 0.4% | 0.0% | 510 ms | OK |
| `rapid_latex_crop` (`rapid-latex-ocr`, `crop+bold`) | RapidLaTeX | 0.0% | 0.0% | 0.0% | 0.0% | 1.0% | 1519 ms | TOO_SLOW |

### Älterer Tesseract-Decken-Sweep (Vorläufer auf 40 Notizbüchern, `glm-ocr:q8_0`-Referenz)

- `B1_bold_deu_p7` (`tessdata_fast`, `ink_crop + bold + deu+eng + psm 7`): Synth `51.5%` | Dev `42.0%` | Holdout `44.3%` | Real `42.9%` (`ANCHOR`).
- `T3_min_linesize` (`1.5`, Holdout `-4.5 pp`) & `E3_psm_13` (Real `-10.3 pp`): klassisches **Overfitting**, per Holdout-Split aussortiert.

## Zukunftsideen (geparkt)

- **Dynamisches Echtzeit-OCR:** Stiftstrom des reMarkable live mitlesen, OCR-Zwischenergebnisse stacken und im Post-Processing zu kohärenten mathematischen Aufgaben zusammenführen.
- **Strukturiertes Ausgabeformat (`YAML` / `LaTeX`):** Saubere maschinenlesbare Darstellung für einen deterministischen Mathe-Prüfer **vor** dem LLM (weil ein LLM selbst keine verlässliche Rechen-Wahrheit liefert).
- **Zielarchitektur:** Capture-, Vorverarbeitungs-, OCR- und Nachverarbeitungs-Kette komplett deterministisch, schnell und lokal auf jedem Laptop (Tesseract oder später messbar ersetzbarer Mini-OCR-Slot); der nicht-deterministische LLM-Tutor (Didaktik, Lernmodi, Mathe-Verständnis) wird erst nachgelagert und nur punktuell gerufen.
