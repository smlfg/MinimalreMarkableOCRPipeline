# MinimalreMarkableOCRPipeline

Handschrift vom reMarkable → LaTeX, schnell, lokal und mit ehrlicher Unsicherheit. Ziel: die **eigene Schrift** zu 99 % lesen (Zeichen und Struktur), unter 2 s pro Zeile.

```text
reMarkable (USB) ─ .rm-Striche ─> PNG ─┬─> TexTeller (liest)  ─┐
                                        └─> GLM-OCR (prüft)    ─┴─> Kohärenz-Schicht ─> {latex, uncertain, repair}
```

## Stand 23.11.2026

| Messung | Struktur | Zeichen | Latenz |
|---|---:|---:|---:|
| eigene Schrift, Probeblatt (40 Zeilen) | 90 % (95 % gegen Geschriebenes) | 93,4 % | p95 0,23 s |
| fremde Schulmathe, dev (326) | 89,6 % | 97,2 % | p95 0,32 s |

Struktur = SymPy-Äquivalenz pro Zeile. Seitenstruktur (Zeilen finden, Rechenkette) ist noch nicht gemessen.

## Aufbau

```text
ocr/                       Produkt
├── formula.py             recognize(png) -> latex, uncertain, repair   (Formeln, ADR-006/007)
├── coherence.py           Verwechslungspaare nur tauschen, wenn die Rechnung stimmt; Dezimalkomma
├── latex.py               normalize / parse / same – eine Quelle für Pipeline und Metrik
├── texteller_worker.py    TexTeller-Dauerprozess (läuft in .venv_tt)
├── pre.py engine.py post.py pipeline.py vision_ocr.swift   Fließtext (Apple Vision / Tesseract)
tablet/                    .rm-Seiten per USB holen (fetch, sync_corpus, runonce)
bench/
├── formula_flywheel/      Messschleife nach karpathy/autoresearch (ADR-008), Kalibrierungsblätter in kalib/
├── structure_bench.py     Metrik: sympy_equal, tree_sim, edit_sim
└── claudebench.py         Web-Ansicht: Tablet-Seite + GT + Ergebnis (http://127.0.0.1:8790)
docs/adr/                  Entscheidungen, Index in docs/adr/README.md
archive/text_ocr_bench/    abgelöste Text-OCR-Bench (Arena, VLM-Konsens, altes Flywheel)
```

## Umgebungen

- `.venv_structure` (Python 3.12): sympy, latex2sympy2_extended, apted, rapidfuzz, Pillow, pyarrow – Pipeline und Metrik.
- `.venv_tt` (Python 3.12): `texteller` – nur der TexTeller-Worker.
- Ollama mit `glm-ocr:q8_0`.

## Schnellstart

```bash
# eine Formel lesen (live)
.venv_structure/bin/python -m ocr.formula bild.png

# Web-Ansicht
.venv_structure/bin/python bench/claudebench.py

# eigene Schrift messen: Kalibrierungsblatt vom Tablet holen, TexTeller-Cache füllen, messen
cd bench/formula_flywheel
python3 kalib_eval.py probe
../../.venv_tt/bin/python tt_run.py --files own/probe/png/*.png
../../.venv_structure/bin/python run.py "beschreibung" own_probe
```

Experimente ändern `ocr/formula.py` oder `ocr/coherence.py`, alles andere im Flywheel ist eingefroren (`bench/formula_flywheel/program.md`).
