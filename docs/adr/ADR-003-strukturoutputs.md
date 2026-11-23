# ADR 003: Verfügbare strukturierte Outputs von Apple Vision und Tesseract

**Status:** provisional, 23.11.2026 · **Beantwortet:** offene Frage Q3 aus `ADR-001-ocr-messaufbau-provisional.md`

## Kontext

Die Pipeline liest heute nur **Strings**:

- `ocr/vision_ocr.swift:42` — `topCandidates(1).first?.string`
- `ocr/engine.py` — `tesseract … stdout` ohne Struktur

`ocr/post.py` rekonstruiert Exponenten über **Pixel-Geometrie**
(`is_equals_box`, `post.py:38`) — also indem nachträglich im Bild geschaut
wird, ob an einer Position ein `=`-Zeichen steht. Das ist ein Umweg: die
Engine hätte die Information bereits liefern können.

Dieses ADR dokumentiert, **was tatsächlich verfügbar ist** — empirisch
geprüft, nicht aus der API-Dokumentation abgeleitet.

## Befund 1: Apple Vision liefert mehr, als genutzt wird

Probe (`vision_probe.swift`, auf `8194ca66_f98389a9.png`, `.accurate`):

```
Anzahl Observations: 15
[0] conf=1.00 box=(x0.314 y0.892 w0.293 h0.035)
      cand conf=1.00 : 3+3=3 6
      cand conf=1.00 : 3+3=2 6
      cand conf=1.00 : 3+3=36
[1] conf=1.00 box=(x0.314 y0.764 w0.253 h0.031)
      cand conf=1.00 : 4• 8 = 32
      cand conf=1.00 : 4•8 = 32
      cand conf=1.00 : 4• 8 =32
```

**Verfügbar, aber verworfen:**

| Feld | API | Nutzen | Heute verwendet |
|---|---|---|---|
| `boundingBox` | `VNRecognizedTextObservation.boundingBox` | Position (normalisiert, Vision-Koordinatensystem: **y von unten**) | ✗ |
| `confidence` | `VNRecognizedTextObservation.confidence` | Zeilen-Sicherheit, Gewichtung | ✗ |
| `topCandidates(n)` | `VNRecognizedTextObservation.topCandidates(n)` | **n Alternative-Lesarten pro Zeile** | nur `topCandidates(1)` |
| Lesereihenfolge | `req.results` (Array-Reihenfolge) | Vision sortiert top-down | implizit, nur als Text |

**Der Top-N-Befund ist der wichtigste.** Für die Zeile `4• 8 = 32` liefert
Vision drei Varianten, die sich an **einer** Stelle unterscheiden:

```
'4• 8 = 32'   '4•8 = 32'   '4• 8 =32'
```

Das sind **Formatvarianten derselben Formel** — genau das Problem, das
CDM in `ADR-002-metriken.md` adressiert. Mit Top-3 könnte man
**kandidatengestützt** entscheiden (z. B. die Variante wählen, die
`sympify` parst) statt die erste zu nehmen.

Ebenso `3+3=3 6` / `3+3=2 6` / `3+3=36` — hier unterscheiden sich die
Kandidaten **semantisch** (Ziffernverwechslung 6/2). Auch das ist mit
Top-N prinzipiell lösbar.

**Wichtig:** Alle gezeigten `confidence`-Werte sind **1.00**. Vision's
Confidence ist bei `.accurate` auf ganzen Seiten offenbar nicht
diskriminierend. Als Gewichtung unbrauchbar — als Signal „unsicher"
ebenfalls.

**Nicht verfügbar bei Apple Vision:**

- **Keine Zeichen-/Symbol-Boxen.** Vision liefert *Zeilen*-Observationen
  (`VNRecognizedTextObservation`), nicht einzelne Glyphen.
- **Keine Math-Struktur.** Kein Bruch, kein Exponent, kein unterer Index —
  keine Information darüber, dass `x²` eine Hochstellung ist.
- **Keine Strich-/Stroke-Ebene.** Das ist CROHME-inkompatibel (siehe
  `ADR-002-metriken.md`).
- **Kein Layout-Graph** wie OmniDocBench (28 Block-Level-Kategorien).
  Vision kennt nur „Textzeile".

## Befund 2: Tesseract liefert eine reiche Hierarchie

**TSV-Ausgabe** (Vollseite, `--psm 3`):

```
level  page block par line word  left top width height conf  text
5      1    1    1   1    1     40   40   807   128   19.36   3+3=2
5      1    1    1   1    2     ...                          95.54   6
5      1    2    1   1    1     ...                          46.88   4-8=3Y
5      1    3    1   1    1     ...                          89.74   Waehle
5      1    3    1   1    2     ...                          63.77   passende
```

**Verfügbare Strukturlevel:** `page_num` → `block_num` → `par_num` →
`line_num` → `word_num`, plus `left/top/width/height` und `conf` pro
Wort. Das entspricht OmniDocBenchs Block/Span-Hierarchie, wenn auch ohne
die Kategorien-Vielfalt.

**`makebox`** liefert Zeichen-Boxen:

```
W 40 45 86 86 0
a 96 54 287 168 0
1 354 40 398 106 0
```

**`hOCR`** liefert `ocr_capabilities`:
`ocr_page ocr_carea ocr_par ocr_line ocrx_word ocrp_dir ocrp_lang ocrp_wconf`
— also inklusive **Schreibrichtung** (`ocrp_dir`) und **Wortkonfidenz**.

**Nicht verfügbar bei Tesseract:** Zeichen-Boxen sind vorhanden
(`makebox`), aber **keine Strich-Ebene** (es ist ein Raster-OCR), keine
Math-Struktur, keine semantischen Kategorien.

## Gegenüberstellung

| Fähigkeit | Apple Vision | Tesseract | heute genutzt |
|---|---|---|---|
| Zeilen-Bounding-Box | ✓ | ✓ (über TSV) | ✗ |
| Wort-Boxen | ✗ (nur Zeilen) | ✓ | ✗ |
| Zeichen-Boxen | ✗ | ✓ (`makebox`) | ✗ |
| Lesereihenfolge | ✓ (Array) | ✓ (line_num) | implizit |
| Block-/Absatz-Hierarchie | ✗ | ✓ | ✗ |
| Konfidenz | ✓ (aber 1.00, unbrauchbar) | ✓ (diskriminierend: 19–95) | ✗ |
| Top-N-Lesarten | ✓ (Top-3 gezeigt) | ✗ | ✗ |
| Math-Struktur (Bruch, hoch) | ✗ | ✗ | ✗ (Pixel-Nachbau) |
| Strich-Ebene (CROHME) | ✗ | ✗ | ✗ |

## Konsequenz

### Was sich ohne neue Datenbank gewinnen lässt

1. **Zeilen-Bounding-Boxen aus Vision** — damit lässt sich die
   Zeilen-**Reihenfolge** und **Position** ohne `split_lines` rekonstruieren
   und **B3 (Read Order Edit Distance)** aus `ADR-002-metriken.md` berechnen.
2. **Top-N-Kandidaten aus Vision** — ermöglicht kandidatengestützte
   Auswahl: die Variante wählen, die `sympify` parst (siehe
   `ADR-004-eingabedatenvertrag.md`). Das ist der direkteste Weg zu
   **C2 (Äquivalenz-Rate)**.
3. **Tesseract-TSV statt stdout** — liefert die Hierarchie
   (Block/Para/Line/Word) **und** diskriminierende Konfidenz, mit der sich
   `structure_fehler` von `ocr_fehler` trennen ließe (der Audit
   `ADR-001-error-audit.md` hat beide noch vermischt).

### Was **nicht** gewonnen werden kann

- **Mathematische Struktur** (Bruch, Exponent, unterer Index) liefert
  **keine** der beiden Engines. Das muss die OCR-Schicht **rekonstruieren**
  — aus Box-Geometrie (Zeile A enthält Box B, B ist höher und kleiner →
  Exponent) oder gar nicht.
- **CROHME-Kompatibilität** ist ohne Stroke-Daten nicht erreichbar.
  Entweder der reMarkable liefert Strokes direkt (`.rm` enthält sie), oder
  CROHME bleibt unerreichbar. Das ist zu prüfen, nicht zu entscheiden.

### Empfehlung (noch keine Entscheidung)

Die drei Punkte oben sind **Ad-hoc-Gewinne**, kein Umbau. Sie sind im
`ADR-004` relevant, weil der Vertrag die Frage stellt, welche
**Information** die OCR-Schicht liefern muss — und ob Top-N und Boxen
dorthin gehören.

**Explizit nicht entschieden:** ob `split_lines` (aktuelle Zeilen-Pre-
Segmentierung) durch Vision-Bounding-Boxen ersetzt werden soll. Das wäre
eine Architekturänderung und ist per Auftrag ausgeschlossen.

## Offen

- Vision-Confidence ist bei `.accurate` durchgehend 1.00 — ist das
  seitenabhängig? Auf Zeilen-Crops (statt Vollseiten) gemessen?
- Tesseract-`makebox` nutzt `0` als Feld für den Zeilenindex — unklar,
  ob die Boxen auch bei mehrzeiligen Crops sinnvoll sind.
- Verhalten von Vision bei `.fast` (erkennt: 17,7 % Real All) — liefert
  es dort brauchbare Boxen, nur schlechtere Texte?
