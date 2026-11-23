# Kompakte ADRs der Text-OCR-Ära (K-001…K-004, früher docs/ADR.md)


## K-001: Strikte 3-Stufen-Trennung im OCR-Core
- **Kontext:** Pre-Processing, OCR-Engine und Post-Processing vermischten Gewinne und Fehler; Effekte einzelner Änderungen waren nicht mehr isolierbar.
- **Entscheidung:** Strikte Dreiteilung in `ocr/pre.py` (`Image -> Image`), `ocr/engine.py` (`Image -> Raw`) und `ocr/post.py` (`Raw -> Text + Metrik`), gebündelt in `ocr/pipeline.py` (`raw` + `final`).
- **Folgen:** Jede Stufe ist einzeln austausch- und messbar; Produkt-Core bleibt bei `407` Zeilen.

## K-002: Natives Apple Vision Swift-CLI (`--batch`) als primäre `<1s`-Engine
- **Kontext:** Auf `n=247` echten Konsens-Zeilen erreichen Tesseract (`53.5%` @ `173 ms`) und RapidOCR (`58.3%` @ `146 ms`) unterhalb von 1 s keine Tutor-taugliche Qualität.
- **Entscheidung:** Natives macOS Binary `ocr/vision_ocr.swift` (`64` Zeilen, ANE-gestütztes `VNRecognizeTextRequest` mit `--batch` JSON-Lines) als Standard-Engine; Tesseract bleibt portabler Fallback.
- **Folgen:** **`87.4 %` Real All (`89.1 %` Math, `86.3 %` Holdout)** bei **`41 ms/Zeile`** ohne Python-ML-Abhängigkeiten im Produkt.

## K-003: Unverändertes `accurate`-Bild statt globalem `bold`/`scale`-Pre-Processing
- **Kontext:** Auf `n=23` schien `ink_crop+bold+scale=3` (`89.9%`) besser als reines Apple Vision (`86.4%`); auf `n=247` fiel `bold+scale=3` jedoch um `-7.1 pp` auf `82.8%` (`Dev` `79.0%` vs. `87.1%`).
- **Entscheidung:** `vision_batch_acc` (ohne `bold`/`scale`) bleibt Standard-Baseline; Eingriffe wie Skalierung/Dilation oder `-`-Rettung werden künftig nur gezielt im Post-Processing oder mathematik-spezifisch nach Holdout-Prüfung ergänzt.
- **Folgen:** Stabilste Generalisierung über alle `36` Notizbücher; verhindert Überanpassung an Kleinstichproben.

## K-004: Harte Modultrennung in `bench/` (`Ollama` / `VLM` / `OCR` / `UI`) & `.venv_wave2/`
- **Kontext:** Monolithische Skripte führten zu dupliziertem Ollama-HTTP-Code, Modell-Swap-Staus beim parallelen Starten und schwer wartbarer UI/Runner-Vermischung.
- **Entscheidung:** Trennung in `bench/ollama.py` (HTTP Keep-Alive Transport), `bench/vlm_consensus.py` (Two-Pass VLM GT), `bench/ocr_runners.py` (Fast-OCR-Varianten), `bench/arena_ui.py` (HTML/SSE View) und `bench/live_arena.py` (dünner Orchestrator); ONNX-Testpakete bleiben in `.venv_wave2/`.
- **Folgen:** Wiederverwendbarer Ollama-Transport (`vlm_consensus` + `flywheel`), kein Modell-Swap-Chaos, und die Benchmark-Infrastruktur berührt den Produkt-Core (`ocr/`) nicht.
