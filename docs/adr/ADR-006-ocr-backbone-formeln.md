# ADR 006: OCR-Backbone für Formeln – TexTeller liest, GLM-OCR prüft

**Status:** angenommen, 23.11.2026 · **Ersetzt für Mathe:** `docs/ADR.md` ADR-002 (Apple Vision als primäre Engine) · **Belege:** `bench/formula_flywheel/results_2026-11-23.tsv`

## Kontext

Apple Vision liest Fließtext gut, aber keine 2D-Mathematik: Brüche, Exponenten und Wurzeln kommen flach heraus (Limes-Bild 28 %; auf 200 Formeln nur 16–44 % Zeichenähnlichkeit). Gesucht war ein lokales Modell Bild → LaTeX unter 2 s pro Formel.

## Messung (Struktur = `sympy_equal`, Metrik v2, siehe ADR-008)

| Modell | dev (326 fremde Formeln) | Latenz p95 | Lizenz |
|---|---:|---:|---|
| **TexTeller** (OleehyO/TexTeller, 298M, MPS) | **89,6 %** | 0,32 s | Apache-2.0 |
| GLM-OCR 0.9B (Ollama `glm-ocr:q8_0`) | 72,7 % | 0,21 s | MIT |
| lfm3-vl, gemma4:26b, qwen3.6 (Ollama) | 61–79 % (Stichprobe) | 0,1–0,5 s | – |
| Apple Vision | ungeeignet für Formeln | – | – |

Eigene Schrift, Kalibrierungsblatt (40 Zeilen): **90 %** Struktur, gegen tatsächlich Geschriebenes 95 %, 1 echter Lesefehler.

## Entscheidung

1. **TexTeller ist die lesende Engine** für Formelzeilen. Eigene venv (`.venv_tt`), weil es ein anderes torch/transformers braucht als der Rest.
2. **GLM-OCR ist Zweitmeinung**, nicht Wähler: Weichen beide (SymPy-ungleich) ab, ist die Zeile `uncertain` (ADR-007).
3. Mehrheitsvotes über VLMs werden **nicht** genutzt: Die Modelle machen korrelierte Fehler (Oracle 86 %, Vote 76–78 %).
4. Apple Vision bleibt für Fließtext; das Routing Text/Formel ist offen.

## Folgen

- Kein Training nötig für den aktuellen Stand; der größte Hebel (+17 Punkte) war die Modellwahl.
- CROHME-Werte von TexTeller sind möglicherweise durch Trainingsdaten-Überlappung geschönt; MathWriting und die eigene Schrift sind die belastbaren Zahlen.
- Nächster Lernhebel: LoRA-Fine-Tuning (TexTeller oder GLM-OCR) auf Fremddaten plus synthetischen Formeln aus den eigenen Glyphen.
