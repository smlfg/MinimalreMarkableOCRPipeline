# MinimalreMarkableOCRPipeline

Minimale, vollständig nachvollziehbare OCR-Pipeline und Dual-Track-ML-Flywheel für das reMarkable Paper Pro:

`reMarkable (USB) -> .rm -> .svg -> .png -> 3-Stufen-OCR (Pre-Processing -> Tesseract -> Post-Processing) -> TXT`

## Projektstruktur

```text
MinimalreMarkableOCRPipeline/
├── README.md
├── .gitignore
├── tablet/
│   ├── fetch.py      # Terminal-Steuerung (Top-5-Notizbücher & Seite) -> data/real_val/
│   ├── runonce.sh    # Einzellauf: scp (.rm) -> rmc (.svg) -> rsvg-convert (.png)
│   └── ocr.sh        # Eigenständiger Tesseract-Einzellauf auf eine PNG-Datei
├── ocr/
│   └── pipeline.py   # 3-Stufen-OCR (split_lines -> preprocess -> ocr_boxes -> postprocess) + Metriken
├── bench/
│   ├── synth.py      # Virtual-Pen .rm->.png Curriculum + deterministischer Dataset-Cache
│   └── flywheel.py   # M3-Max-Runner (--mode dual | --mode stress) mit HTML-Logs
└── data/             # Eingefrorene Datasets, real_val/, VLM-Cache & HTML-Reports (gitignored)
```

| Datei | Zeilen | Aufgabe |
|---|---:|---|
| `tablet/fetch.py` | 194 | USB-SSH-Auswahl (Top-5-Notizbücher & Seite), speichert nach `data/real_val/` |
| `tablet/runonce.sh` | 24 | Einzellauf `.rm` → `.svg` → `.png` |
| `tablet/ocr.sh` | 23 | Direkter Tesseract-Aufruf auf eine PNG-Datei |
| `ocr/pipeline.py` | 207 | Einzige Quelle für 3-Stufen-OCR (`V5`-CLI) sowie `norm`, `levenshtein`, `diff_tags` |
| `bench/synth.py` | 90 | Virtual-Pen-Curriculum (`data/synth/`) + `make_case` + `ensure_dataset` |
| `bench/flywheel.py` | 245 | Dual-Track CPU+GPU-Benchmark (`--mode dual`) und Stress-Test (`--mode stress`) |

## Schnellstart

```bash
# 1. Echte Seite vom reMarkable (USB) nach data/real_val/ holen
python3 tablet/fetch.py
./tablet/ocr.sh data/real_val/<datei>.png

# 2. Einzelne PNG direkt mit der besten 3-Stufen-Pipeline (V5) lesen
python3 ocr/pipeline.py data/real_val/lines/01_ocr_p01_line03.png

# 3. Synthetisches 6-Fälle-Curriculum erzeugen
python3 bench/synth.py

# 4. Dual-Track Flywheel (CPU-Synth + GPU-VLM-validierte echte Zeilen)
python3 bench/flywheel.py --mode dual --n 100 --seed 1 --workers 12 --open
python3 bench/flywheel.py --mode dual --n 10000 --seed 1 --workers 12 --open

# 5. Generativer Stress-Test (N Fälle oder endlos bis Ctrl+C)
python3 bench/flywheel.py --mode stress --n 1000 --workers 12 --open
python3 bench/flywheel.py --mode stress --forever --workers 12
```

## Verifizierte Messwerte (2026-11-22, Apple M3 Max, `OMP_THREAD_LIMIT=1`)

- **Dual-Track (`n=10000`, `seed=1`, `12` Worker + 3 echte Zeilen `01_ocr_p01.rm`, VLM-Referenz `glm-ocr:q8_0` = `100%`):**
  - `V0_baseline`: Synth `51.2%` (`79.1s`) | Real `0.0%` (`BASELINE`)
  - `V1a_pre_crop`: Synth `51.4%` (`+0.2 pp`, `69.6s`) | Real `0.0%` (`KEEP`)
  - `V1b_pre_crop_bold`: Synth `60.5%` (`+9.3 pp`, `69.0s`) | Real `20.8%` (`+20.8 pp`, `KEEP`)
  - `V2a_minusfix`: Synth `51.9%` (`+0.7 pp`, `75.3s`) | Real `0.0%` (`KEEP`)
  - `V2b_wl_minusfix`: Synth `50.8%` (`-0.4 pp`, `68.1s`) | Real `6.7%` (`+6.7 pp`, `REAL_WIN` — Whitelist drückt `L4` ohne `geom_sup_rescue`)
  - `V4_crop_bold_minusfix`: Synth `61.0%` (`+9.8 pp`, `69.0s`) | Real `20.8%` (`+20.8 pp`, `KEEP`)
  - **`V5_crop_bold_wl_geom`:** Synth **`61.3%` (`+10.1 pp`, `64.7s`)** | Real **`36.1%` (`+36.1 pp`, `KEEP`)** — Zeile 3 (`20 21 22`) stieg von `0.0%` auf **`83.3%`** (`20a122`).
- **`stress.py` (`n=10000`, Baseline vor Refaktor):** `5130/10000` (`51.3%`, `31.3 cases/s`), Top-Fehler `'z' -> '2'` (`863×`).

## Zukunftsideen (geparkt)

- **Dynamisches Echtzeit-OCR:** Stiftstrom des reMarkable live mitlesen, OCR-Zwischenergebnisse stacken und im Post-Processing zu kohärenten mathematischen Aufgaben zusammenführen.
- **Strukturiertes Ausgabeformat (`YAML` / `LaTeX`):** Saubere maschinenlesbare Darstellung für einen deterministischen Mathe-Prüfer **vor** dem LLM (weil ein LLM selbst keine verlässliche Rechen-Wahrheit liefert).
- **Zielarchitektur:** Capture-, Vorverarbeitungs-, OCR- und Nachverarbeitungs-Kette komplett deterministisch, schnell und lokal auf jedem Laptop (Tesseract oder später messbar ersetzbarer Mini-OCR-Slot); der nicht-deterministische LLM-Tutor (Didaktik, Lernmodi, Mathe-Verständnis) wird erst nachgelagert und nur punktuell gerufen.
