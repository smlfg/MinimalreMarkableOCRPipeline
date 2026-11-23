# UPSTREAM_SEARCH: Handschriftliche Mathe -> LaTeX (lokal, Apple Silicon)

**Stand:** 23.11.2026 · **Zweck:** Upstream-First-Gate (>=3 Kandidaten) vor jedem Feature-Code · **Art:** nur Recherche, kein Prototyp
**Vermerk:** ohne HAI-Mission, Owner-Freigabe im Chat 23.11.2026 (gilt nur für diese eine Datei).

Konvention: **belegt** = steht in der genannten Primärquelle (Quellen-Nummern in eckigen Klammern, Liste unten). **unbelegt** = keine Primärangabe gefunden; nicht geschätzt. Ich habe nichts installiert und nichts gemessen. Alle Zahlen stammen aus Papern/READMEs und gelten für deren Hardware, nicht für unseren M3 Max.

## 1. Ist-Stand (aus dem Repo bestätigt)

- `ocr/engine.py`: `read_vision(img,cfg)->str` (Subprozess `ocr/vision_ocr`), `read_text` (Tesseract), `read_boxes` (Tesseract makebox). `ocr/pipeline.py:run_detailed` verzweigt per `cfg["engine"]` (`apple_vision` | `tesseract_word` | sonst makebox) und liefert `{raw, final, ms}`.
- Vision liefert heute nur `topCandidates(1).string`; Boxen, Top-N und Confidence werden verworfen (ADR-003). Confidence bei `.accurate` durchgehend 1.00 (ADR-003/005), taugt nicht als Mathe-Detektor.
- Ziel laut ADR-005: Seiten-JSON mit LaTeX- und SymPy-Feldern, Unsicherheit pro Zeile, nichts verwerfen.

## 2. Vergleichstabelle

| # | Kandidat | Lizenz | Handschrift-Mathe | Gemeldete Metrik | Apple Silicon / Laufzeit | Installation | Pflege |
|---|---|---|---|---|---|---|---|
| 1 | **GLM-OCR** (0.9B VLM, Z.ai) | Modell MIT, SDK Apache-2.0 [1] | Docs sagen: Handschrift + Formeln erkennbar [2]; **kein** eigener Handschrift-Formel-Score im Paper (HWE nicht berichtet) [3] | UniMERNet 96.5, OmniDocBench v1.5 94.62, FormulaCDM 93.90 [1][3]; 0.67 Seiten/s (Bild), Hardware **nicht angegeben** [3] | MLX-Guide "optimiert für Apple Silicon" [1]; Ollama-Backend [2]; konkrete Latenz auf M-Chip **unbelegt** | `pip install glmocr` bzw. mlx-vlm / `ollama run glm-ocr` [1][2] | aktiv (News Feb/Mär 2026) [1] |
| 2 | **UniMERNet** (T/S/B) | Apache-2.0 [4] | **Ja**, Testset mit 6.332 handschriftlichen Ausdrücken (HWE) [4] | HWE BLEU/EditDist: T 0.883/0.078, S 0.889/0.075, B 0.895/0.072; Texify 0.341/0.522; pix2tex 0.012/0.920 [5]. CDM-ExpRate in Tab. 5 **nicht berichtet** [5] | Durchsatz nur auf A100, Batch 128: T 7.20, S 6.04, B 5.06 img/s [5]. MPS/CoreML **unbelegt** | Conda py3.10, `pip install -U "unimernet[full]"`, Gewichte 441 MB / 773 MB / 1.3 GB [4] | letzte News Sep 2025, 38 offene Issues [4] |
| 3 | **PaddleOCR-VL** (0.9B) | Apache-2.0 [6] | "handwritten text" erwähnt, Formel-Handschrift **unbelegt** [6] | OmniDocBench v1.6 96.3 % (PaddleOCR-VL-1.6) [6]; UniMERNet 96.1 (v1.5) [3] | macOS-Badge; 6.1x Speedup auf M4 gilt nur für PP-OCRv6 tiny, nicht für das VL-Modell [6]; mlx-vlm führt PaddleOCR-VL als Modell [7] | pip (PaddleOCR) oder mlx-vlm [6][7] | aktiv [6] |
| 4 | **Surya 2.5** (Datalab) | Code Apache-2.0; Gewichte modifizierte AI-Pubs-Open-RAIL-M (frei für Forschung/Privat/Startups <5 Mio.) [8] | Handschrift als "hard docs" gelistet, **kein** Score; LaTeX inline als `<math>` (KaTeX) [8] | olmOCR-bench "OldMath" 78.6 % [8]; M4 Max, 96 DPI: 0.190-0.198 Seiten/s [8] | llama.cpp/Metal oder MLX (experimentell) [8] | `pip install surya-ocr` + `brew install llama.cpp` [8] | sehr aktiv [8] |
| 5 | **Texify** | Code GPL-3.0, Gewichte CC BY-SA 4.0 [9] | README erwähnt keine Handschrift [9]; HWE-Messung siehe #2 (BLEU 0.341) [5] | arXiv/im2latex: BLEU 0.842, Edit 0.065 (Autor: verzerrt) [9] | MPS ja (`TORCH_DEVICE=mps`) [9]; 4.16 img/s auf A100 [5] | `pip install texify` [9] | **archiviert 29.01.2025, deprecated**, Nachfolger Surya [9] |
| 6 | **pix2tex / LaTeX-OCR** | MIT [10] | "kinda done" (Trainings-Notebook) [10]; HWE BLEU 0.012 [5] | BLEU 0.88, norm. Edit 0.10, Token-Acc 0.60 (Druck) [10] | MPS **unbelegt** | `pip install "pix2tex[gui]"` [10] | Release-/Aktivitätsdatum **unbelegt** [10] |
| 7 | **Pix2Text** (MFD+MFR 1.5) | MIT [11] | **unbelegt** (README nennt es nicht) [11] | keine Zahlen in README [11] | Apple Silicon/CoreML/ONNX **unbelegt**; separate Mac-App verlinkt [11] | `pip install pix2text` [11] | v1.1.4 vom 25.07.2025 [11] |
| 8 | **GOT-OCR 2.0** | Code Apache-2.0, Daten CC BY-NC 4.0 [12] | Formeln/Handschrift in README **nicht beschrieben** [12] | keine Scores im README [12] | MPS **unbelegt**; Setup nennt CUDA 11.8 + flash-attn [12] | conda + `pip install -e .` [12] | letzte Notiz 02/2025, 223 offene Issues [12] |
| 9 | **Qwen2.5-VL** (via mlx-vlm/Ollama) | Apache-2.0 (Repo) [13] | Formel/Handschrift im README **nicht genannt** [13] | keine Zahlen im Text [13] | mlx-vlm: MLX, MIT, macOS Apple Silicon [7]; Latenz **unbelegt** | `pip install -U mlx-vlm` [7] | aktiv [7] |
| 10 | **Apple Vision RecognizeDocumentsRequest** (WWDC25) | OS-API | Doku/Session erwähnen weder Mathe noch Handschrift [14][15] | keine | macOS 26+, nativ [14] | kein Install (Swift) | Apple |
| 11 | **Mathpix Process Strokes** | proprietär, API | Strokes (Online) ja; Ausgabe-Format LaTeX **nicht bestätigt** (primär MMD) [16] | unbelegt | Cloud-API; "Private Cloud" auf eigener Infrastruktur existiert [16] | API-Key | kommerziell |
| 12 | **MyScript iink SDK** | kommerziell, Dev-Lizenz nur Entwicklung [17] | Math-Recognizer aus Strokes, Export LaTeX/MathML [17] | unbelegt | On-device-Lizenz vs. Cloud getrennt; macOS-SDK-Konditionen **unbelegt** [17] | Lizenzvertrag nötig | kommerziell |

Nicht eigenständig geprüft: Nougat, TrOCR, DeepSeek-OCR, dots.ocr, olmOCR (nur als Namen in [7]/[3] gesehen; keine Primärprüfung, daher keine Aussage).

## 3. Bewertung gegen unser Ziel

Ziel: Struktur erhalten (Bruch, Exponent, Limes, Wurzel, mehrzeilig), lokal, Apple Silicon, möglichst <1 s/Seite.

- **Struktur/LaTeX:** Nur die Kandidaten 1-9 geben LaTeX; Apple Vision (#10) laut Doku nicht (keine Formelerwähnung, nur Tabellen/Listen/Absätze) [14]. Das löst unser Kernproblem (28 % auf `lim ... cos^2`) also nicht.
- **Handschrift-Beleg:** Der einzige Kandidat mit gemessener Handschrift-Formel-Zahl ist UniMERNet (HWE) [5]. Texify und pix2tex fallen dort deutlich ab (BLEU 0.341 bzw. 0.012) [5]. GLM-OCR hat die beste Gesamtzahl auf dem UniMER-Benchmark (96.5) [3], aber ohne Handschrift-Aufschlüsselung: **unbelegt**, ob sie für HWE gilt.
- **Tempo:** Keine Primärzahl für M3 Max. Die einzige Mac-Zahl ist Surya auf M4 Max: ~0.19 Seiten/s, also rund 5 s/Seite [8]. GLM-OCR meldet 0.67 Seiten/s auf unbekannter Hardware [3]. **<1 s/Seite für ein ganzes Seiten-VLM ist nach Belegen nicht erreichbar.** Realistisch ist nur: VLM auf kleine Zeilen-/Formel-Crops (kurze Ausgabe) und Vision für den Rest. Die Latenz pro Crop ist **unbelegt** und muss mit `bench/` gemessen werden.
- **Lizenz:** GLM-OCR (MIT) und UniMERNet (Apache-2.0) unproblematisch. Texify GPL-3.0 + archiviert, Surya-Gewichte eingeschränkt, GOT-Daten NC: nicht empfohlen.
- **Passt zur Regel "kein eigener Code":** GLM-OCR/UniMERNet/mlx-vlm sind fertige Repos, Andocken ist Glue.

## 4. Hybrid (Frage 2)

- Vision-Zeilen (Boxen!) + Formel-Modell nur für Mathe-Zeilen ist der einzige Weg Richtung <1 s/Seite. Das ist **meine Schlussfolgerung** aus den Tempozahlen, kein belegtes Ergebnis.
- Mathe-Regionen erkennen, ohne eigenen Code zu bauen: (a) Pix2Text hat ein Formel-Detektionsmodell (MFD 1.5) [11]; (b) GLM-OCR bringt PP-DocLayoutV3 als Layout-Stufe mit [1]; (c) Vision-Box + Top-N-Kandidaten (ADR-003) als Trigger: Zeile gilt als Mathe, wenn Top-N-Kandidaten semantisch auseinanderlaufen oder `sympify` scheitert. (c) ist eine Heuristik, **unbelegt**, billig prüfbar. Nicht belegt ist, wie zuverlässig (a)/(b) auf handschriftlichen Zeilen sind.
- Lies-Kosten: `vision_ocr.swift` müsste Boxen und Top-N ausgeben (Config/Swift-Glue, ADR-003 zeigt, dass die API sie liefert).

## 5. Stroke-basierte Erkennung (Frage 3, reMarkable-Vorteil)

- `.rm`-Dateien (v6) sind Strichdaten; `rmscene` (MIT) liest v6 und liefert eine Szenen-Baumstruktur [18]. Welche Punktfelder (x, y, Druck, Zeit) exponiert werden, steht nicht im README: **unbelegt, im Quellcode `src/rmscene` prüfen** [18]. Ob Zeitstempel pro Punkt vorhanden sind, ist für Online-Modelle entscheidend und **unbelegt**.
- Beleg für den Nutzen von Strokes: MathWriting (Google, CC BY 4.0, 230k handschriftliche + 400k synthetische Beispiele, Online-Ink mit LaTeX) [19]. Test-CER: reines Bild-OCR-Modell 7.17, Online-CTC-Transformer 5.49, PaLI 5.95; das Paper führt den Vorsprung auf fehlende Schreibreihenfolge/-geschwindigkeit im Bildmodell zurück [20]. PaLI nutzt Punktfolge plus Raster, ist also kein reines Bild-gegen-Ink-Experiment [20]. Der Vorteil ist real, aber klein (ca. 1.7 CER-Punkte), und gilt für deren Modelle.
- **Lokal nutzbare Stroke->LaTeX-Tools mit Primärbeleg habe ich nicht gefunden.** MathWriting-Gewichte: **unbelegt** (nur Datensatz belegt) [19]. Brauchbare Stroke-Dienste sind kommerziell: Mathpix Strokes (Cloud, evtl. Private Cloud) [16], MyScript (on-device-Lizenz, Konditionen offen) [17]. Beides verletzt "lokal/frei" oder braucht Lizenzklärung.
- Pragmatischer Mittelweg ohne Training: `.rm` -> eigene Strich-Geometrie nutzen, um **Zeilen/Formel-Regionen sauber zu schneiden** und sauber zu rendern (hohe Auflösung, einheitliche Strichstärke). Das Bildmodell bleibt, Preprocessing wird besser. Wirkung: **unbelegt**, messen.

## 6. Optimierungshebel ohne Training (Frage 4)

Alles hier ist Hypothese; keine Primärquelle gemessen. Prüfen auf `bench/`:

1. **Aus Strokes rendern statt Screenshot** (rmscene) [18]: saubere, skalierbare Strichdarstellung, kein JPEG-Rauschen.
2. **Crop pro Zeile/Formel** mit Rand, statt ganzer Seite: Vision-Boxen oder Stroke-Cluster als Schnitt. Kurze Crops halten auch die VLM-Ausgabe kurz (Tempo).
3. **Kontrast/Strichdicke**: das Repo hat `bold`, `ink_crop`, `scale` bereits (`DEFAULT_CFG`); gegen die neuen Engines neu vermessen.
4. **Auflösung**: Surya-Benchmark nutzt 96 DPI [8] (nur ein Datenpunkt dafür, dass niedrige DPI ausreicht; für Handschrift nicht belegt).
5. **Validator-Rückkopplung**: Top-N bzw. mehrere Decodierungen und die Variante nehmen, die `sympify` (ADR-004/005) parst. Kein Training, nur Auswahl.
6. **Batching** der Crops in einem Prozess (Modell einmal laden) analog zu `run_vision_batch`; Ladezeit pro Aufruf wäre sonst dominant (Vermutung).

## 7. Empfehlung

> **Nachtrag 23.11.2026 – gemessen, Empfehlung abgelöst:** Ein zweiter Recherchelauf fand **TexTeller** (github.com/OleehyO/TexTeller, Apache-2.0, 298M; Paper: ExpRate CROHME14 88,0, MathWriting 81,0). Lokal gemessen (MPS, Metrik v2): **89,6 %** Struktur auf 326 fremden Schulmathe-Formeln gegen 72,7 % für GLM-OCR, p95 0,32 s; eigene Schrift 90 % (40 Zeilen). Entscheidung in [ADR-006](../adr/ADR-006-ocr-backbone-formeln.md): TexTeller liest, GLM-OCR ist Zweitmeinung. Der Text unten ist der Stand vor der Messung.

**Hauptweg: Hybrid Vision + GLM-OCR (Formel-Prompt) auf Zeilen-Crops.**
- Begründung: MIT, kleines Modell (0.9B), bester gemeldeter UniMER-Wert (96.5) [3], dokumentierte Formel-Ausgabe als LaTeX (Prompt "Formula Recognition:") [3], Ollama/MLX-Pfade vorhanden [1][2], aktiv gepflegt [1]. Vision bleibt für Textzeilen (87 % laut unserer Messung).
- Risiko, offen benannt: Handschrift-Formel-Genauigkeit und M3-Latenz sind **unbelegt**. Erster Schritt wäre ein Messlauf auf den vorhandenen `bench/`-Seiten (nicht Teil dieses Auftrags).

**Fallback: UniMERNet-S/B (Apache-2.0).**
- Begründung: einziger Kandidat mit belegtem Handschrift-Ergebnis (HWE BLEU 0.889/0.895, Edit 0.075/0.072) [5], nur Formel-Crops, kleiner als Texify-Alternative.
- Risiko: Durchsatzzahlen nur A100 [5], MPS unbelegt, Conda-Setup py3.10 [4].

**Nicht weiter verfolgen:** Texify (archiviert, GPL) [9], pix2tex (HWE BLEU 0.012) [5], GOT-OCR (CUDA-Setup, NC-Daten) [12], Apple RecognizeDocuments (kein Mathe belegt) [14][15]. Mathpix/MyScript nur, wenn "lokal" aufgeweicht wird.

**Realismus zum Ziel <1 s/Seite:** nach den Belegen nur über Hybrid mit wenigen Mathe-Crops erreichbar, nicht per Ganzseiten-VLM [3][8].

## 8. Andocken an `ocr/engine.py` / `pipeline.py`

Neuer Zweig, passend zum bestehenden Muster (`read_vision`, `run_vision_batch`):

- **Funktion:** `read_math(img: PIL.Image, cfg: dict) -> str` in `ocr/engine.py`; Batch-Variante `run_math_batch(paths, cfg) -> list[tuple[str, float]]` analog zu `run_vision_batch`.
- **Eingabe:** Graustufen-PIL-Crop einer **einzelnen Zeile/Formel** (kommt bereits aus `pre.split_lines` + `pre.preprocess`), Zeilenbild als PNG-Pfad, wenn per Subprozess.
- **Aufruf:** CLI bzw. lokaler Server als Subprozess/HTTP (z. B. `glmocr` / `mlx_vlm` / `ollama run glm-ocr` mit Prompt `Formula Recognition:`) [1][3]. Kein Modellcode im Repo, nur Aufruf und Config (Boundary "nur Glue").
- **Ausgabe:** LaTeX-String pro Zeile (+ ms). Der Pipeline-Rückgabetyp bleibt `{raw, final, ms}`; `raw` = Modellausgabe, `final` = LaTeX. Für ADR-005 wird je Zeile `latex` befüllt, `sympy` per Validator abgeleitet, `uncertain` gesetzt, wenn Parsing scheitert.
- **Verzweigung in `pipeline.run_detailed`:** neue `cfg["engine"] = "hybrid_math"`: je Chunk zuerst `read_vision`; Mathe-Trigger (Abschnitt 4c oder Layout-Detektion) -> `read_math`; sonst Vision-Text. Config-Keys analog `vision_*`: `math_backend` (`glmocr` | `unimernet`), `math_model`, `math_prompt`.
- **Ein Stück Swift-Glue nötig:** `vision_ocr.swift` soll Box + Top-N ausgeben (heute nur String), siehe ADR-003.
- **Fallback-Wechsel:** `math_backend=unimernet` ändert nur den Aufruf, Ein-/Ausgabevertrag bleibt gleich (Crop -> LaTeX).
- Optional später: `ocr/strokes.py`-artiger Eingang über `rmscene` [18] für sauberes Rendern/Schneiden; das ist ein eigener Auftrag.

## 9. Quellen (Primärquellen)

1. GLM-OCR Repo (Lizenzen, Install, Benchmarks): https://github.com/zai-org/GLM-OCR
2. Z.ai Doku GLM-OCR (Handschrift, Formeln, Ollama): https://docs.z.ai/guides/vlm/glm-ocr
3. GLM-OCR Technical Report, arXiv 2603.10910 (UniMERNet 96.5 u. a., 0.67 Seiten/s, Prompt): https://arxiv.org/html/2603.10910v2
4. UniMERNet Repo (Apache-2.0, HWE-Set 6.332, Install, Modellgrößen): https://github.com/opendatalab/UniMERNet
5. UniMERNet Paper, arXiv 2404.15254, Tab. 5 (BLEU/EditDist je Subset, FPS A100): https://arxiv.org/html/2404.15254
6. PaddleOCR Repo (Apache-2.0, PaddleOCR-VL, OmniDocBench): https://github.com/PaddlePaddle/PaddleOCR
7. mlx-vlm Repo (MIT, Modelle, Apple Silicon): https://github.com/Blaizzy/mlx-vlm
8. Surya Repo (Lizenz, LaTeX, M4-Max-Benchmark): https://github.com/VikParuchuri/surya
9. Texify Repo (archiviert, Lizenzen, Benchmark): https://github.com/VikParuchuri/texify
10. pix2tex Repo: https://github.com/lukas-blecher/LaTeX-OCR
11. Pix2Text Repo: https://github.com/breezedeus/Pix2Text
12. GOT-OCR 2.0 Repo: https://github.com/Ucas-HaoranWei/GOT-OCR2.0
13. Qwen2.5-VL Repo: https://github.com/QwenLM/Qwen2.5-VL
14. Apple Doku RecognizeDocumentsRequest (macOS 26+): https://developer.apple.com/documentation/vision/recognizedocumentsrequest.md
15. WWDC25 Session 272 "Read documents using the Vision framework": https://developer.apple.com/videos/play/wwdc2025/272/
16. Mathpix API Doku (Process Strokes, Private Cloud): https://docs.mathpix.com/
17. MyScript iink / Lizenzbedingungen v7: https://developer.myscript.com/legal-docs/License-terms-of-use-and-sale-v7.pdf , https://www.myscript.com/blog/iink-sdk-3-0-math
18. rmscene (MIT, v6-Reader): https://github.com/ricklupton/rmscene
19. MathWriting, arXiv 2404.10690 (Abstract): https://arxiv.org/abs/2404.10690
20. MathWriting, Tab. 6 (CER Online vs. OCR): https://arxiv.org/html/2404.10690

Hinweis zur Belegqualität: Ein Teil der Angaben wurde über automatische Seitenzusammenfassungen der genannten URLs gewonnen, nicht durch Lesen der Rohtexte. Vor Entscheidungen mit Kostenfolge die Schlüsselzahlen (Tab. 5 in [5], UniMERNet-Wert in [3], Tab. 6 in [20]) einmal im Original gegenlesen.
