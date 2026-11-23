# ADR 001: OCR-Messaufbau und offene Forschungsfragen (PROVISIONAL)

**Status:** provisional, 23.11.2026 · **Betrifft:** `bench/`, `ocr/`, Konsens-Datensatz

> **Warum provisional:** Dieses ADR dokumentiert Messungen, aus denen **noch keine
> Entscheidung** abgeleitet wird. Es trifft bewusst **keine** Aussage darüber, ob
> Full-Page-Modus grundsätzlich überlegen ist oder ob die Referenzdaten fehlerhaft
> sind. Beides ist offen (siehe „Offene Fragen"). Es existiert, weil die
> nachfolgenden Arbeiten einen belastbaren Ausgangspunkt brauchen.

## Kontext

Die Pipeline liest Handschrift vom reMarkable mit Apple Vision. Bisher wurde
ausschließlich **zeilenweise** gemessen: Seiten werden gerendert, in Zeilen
geschnitten, jede Zeile einzeln durch die OCR-Engine geschickt und gegen eine
Referenz aus zwei VLM-Konsens (glm-ocr:q8_0 + qwen2.5vl:7b) bewertet.

Diese Messreihe hat eine Struktur, die man benennen muss, bevor man ihr
vertraut: **Die Referenz und das Messinstrument teilen einen Technologie-Typ.**
Sowohl die VLM-Referenz als auch Apple Vision sind Vision-Modelle. Es ist
deshalb a priori unklar, ob beobachtete Übereinstimmungen Eigenschaft der
jeweiligen Engine sind oder Eigenschaft des gemeinsamen Fehlermusters.

## Messungen (Stand 23.11.2026)

### Reproduzierbarkeits-Basis

| Element | Wert |
|---|---|
| Git HEAD | `3d881b3df27006d06d6e23279fe0a4258a134caa` |
| Dirty State | 17 geänderte/untracked Dateien (nicht committet) |
| Plattform | macOS 27.2.1, Apple M3 Max, Python 3.14.6 |
| `ocr/vision_ocr` (sha256, gekürzt) | `8888aade77f197fc` |
| `data/consensus/manifest.tsv` (sha256, gekürzt) | `6f21a17904acfadd` |
| `data/arena/arena_results.tsv` (sha256, gekürzt) | `265df2068504fac3` |
| Gerenderte Vollseiten | 210 PNG |
| Zeilen-Crops | 752 PNG |
| Konsens-Manifest | 247 Zeilen + Header |

### M1 — Varianten-Benchmark auf Zeilen (247 Konsens-Zeilen)

Quelle: `data/arena/arena_results.tsv`, 9 Varianten, Gate < 1000 ms/Zeile.

| Variante | Engine | Real Math | Real Dev | Real Holdout | Real All | Synth | ms |
|---|---|---:|---:|---:|---:|---:|---:|
| `vision_batch_acc` | AppleVision (raw, batch) | 89.1 % | 87.1 % | 86.3 % | **87.4 %** | 47.0 % | 41 |
| `vision_batch_bold` | AppleVision (crop+bold) | 85.8 % | 83.6 % | 84.0 % | 84.2 % | 55.0 % | 40 |
| `vision_batch_s2` | AppleVision (crop+bold+scale2) | 88.2 % | 80.0 % | 86.0 % | 83.4 % | 54.0 % | 52 |
| `vision_batch_s3` | AppleVision (crop+bold+scale3) | **89.6 %** | 79.0 % | 84.6 % | 82.8 % | 55.0 % | 72 |
| `vision_batch_s2_nc` | AppleVision (scale2, correct=0) | 86.5 % | 80.2 % | 83.8 % | 82.5 % | 52.0 % | 50 |
| `rapidocr_raw` | RapidOCR | 56.5 % | 59.0 % | 58.4 % | 58.3 % | **65.0 %** | 146 |
| `rapidocr_bold` | RapidOCR (crop+bold) | 58.2 % | 55.9 % | 58.1 % | 57.0 % | 45.0 % | 147 |
| `tess_best_bold` | Tesseract (tessdata_best) | 58.5 % | 51.9 % | 52.4 % | 53.5 % | 54.0 % | 173 |
| `tess_fast_bold` | Tesseract (tessdata_fast) | 49.3 % | 52.7 % | 52.4 % | 51.8 % | 52.0 % | 126 |

**Beobachtung aus dem Vergleich 23 → 247 Zeilen:** Auf 23 Zeilen lag
`vision_batch_s3` (89.9 % Real All) vor `vision_batch_acc` (86.4 %). Auf 247
Zeilen kehrt sich das um (`vision_batch_acc` 87.4 % vs. `s3` 82.8 %). Das
Ranking ist bei n=23 nicht stabil.

### M2 — Konsens-Filter: wie 752 Kandidaten zu 247 Zeilen wurden

Rekonstruktion aus `data/real_corpus/consensus_cache.json` (752 eindeutige
Seiten-Hashes, 1402 Cache-Einträge = 2 Modelle × Zeilen).

| Filter | Ergebnis | Anzahl |
|---|---|---:|
| Agreement ≥ 90 % **und** Länge 3–100 **und** kein ` ``` ` | behalten | **247** |
| Agreement < 90 % | verworfen | 393 |
| A ungültig (Länge / ` ``` `) → nie an Modell B übergeben | vorverworfen | 112 |
| **Summe** | | **752** |

Agreement-Verteilung der 640 Zeilen, die beide Modelle durchlaufen haben:

| Agreement | Anzahl |
|---|---:|
| 100 % | 167 |
| 90–99 % | 80 |
| 50–89 % | 285 |
| < 50 % | 108 |

Die 285 Zeilen im Band 50–89 % sind **nicht** abgelehnt worden, weil die
Modelle sich uneinig waren, sondern weil `post.accuracy()` zeichenbasiert
arbeitet: bei langen Fließtextzeilen reichen 1–2 abweichende Zeichen für
< 90 %. Beispielpaare:

```
50 %  A='housement verhalten'      B='Nonsometen verhulta'
46 %  A='Abgabe for PM 03'         B='Abgabe 15.03 PM'
79 %  A='nsn Selfhosted easier'     B='n8n selfhosted easy'
```

Die 112 vorverworfenen Zeilen sind Extraktions-Artefakte (`''`, `'2'`,
`'```markdown ```'`), keine Bewertung.

### M3 — Full-Page vs. Line-Mode (Apple Vision, 40 Seiten)

Methode: dieselben 40 Seiten, zwei Modi, identische Vision-Konfiguration
(`--level accurate --lang de-DE,en-US --correct 1`).
Full-Mode = **ein** Vision-Call pro gerenderter Seite, Ausgabe wird über
Zeilengrenzen hinweg erzeugt. Line-Mode = ein Vision-Call **pro Zeilen-Crop**.

Metrik: **Zeilen-Recall** = Anteil der Konsens-Ground-Truth-Zeilen, die
(normalisiert) als zusammenhängende Zeichenfolge im Engine-Output enthalten
sind.

| Metrik | Full-Page | Line-Mode |
|---|---:|---:|
| Zeilen-Recall, alle 40 Seiten | 55.0 % | 50.2 % |
| Zeilen-Recall, 35 Math-Seiten | 58.9 % | 52.4 % |
| Seiten, Full besser | 10 | — |
| Seiten, Lines besser | 7 | — |
| Seiten, gleich | 23 | — |

Beispiel-Auszug (`8194ca66_f98389a9`), Ground Truth `'4·8=32'`:

```
FULL:  '3+3=3 6\n4• 8 = 32\nWaehle passende dtured & = ?\nRegel: a mal b = a mal (c\nplus d) wenn c plus d gleich\n...'
LINE:  '4• 8 = 32'
```

**Einschränkung dieser Messung:** Der zeichenweise Vergleich einer ganzen
Seite gegen eine einzelne GT-Zeile (erster Messversuch) ergab 0–21 % und war
methodisch falsch — die Metrik war ungeeignet. Der Recall-Wert oben ist die
korrigierte Form. Beide Messungen sind **keine** Aussage über die
Absolutgüte einer Engine.

### M4 — Fehlerbild, stratifizierter manueller Audit (30 Beispiele)

Siehe `docs/adr/ADR-001-error-audit.md` (separates Dokument, gleicher Status).
Klassifikation: `ocr_fehler` / `referenz_fehler` / `alignment_fehler` /
`struktur_fehler`.

## Offene Fragen

1. **Wie verteilen sich die Fehler auf Referenz und Engine?** Der Recall von
   50–59 % erlaubt zwei unvereinbare Lesarten: (a) die Engine verfehlt echte
   Zeilen, (b) die Referenz enthält Zeilen, die so nicht auf der Seite stehen.
   Der Audit in M4 soll das quantifizieren.
2. **Wie misst man mathematische Struktur?** Zeichengenauigkeit ist für
   Strukturfragen ungeeignet (`x` vs. `×`, `1` vs. `l`, `2` vs. `z`).
   Bestehende Standards (CROHME, OmniDocBench) sind zu recherchieren, bevor
   eigene Metriken definiert werden.
3. **Welche strukturierten Outputs sind verfügbar?** Apple Vision liefert
   `VNRecognizedTextObservation` mit Bounding-Boxen und einer impliziten
   Lesereihenfolge; Tesseract liefert `makebox`/TSV. Ob das für
   Formel-Rekonstruktion (Bruch, Exponent, unterer Index) ausreicht, ist
   ungeprüft.
4. **Was ist der verbindliche Eingabedatenvertrag?** Der Algebra-Tutor hat
   einen SymPy-Validator. Daraus muss ableitbar sein, **welche** Textform
   die OCR-Schicht produzieren muss, damit die Rechnung prüfbar ist.

## Entscheidung

**Es wird keine Entscheidung getroffen.** Dieses ADR hält nur fest:

- was gemessen wurde und unter welchen Bedingungen (M1–M3),
- welche Beobachtungen als *Befund* gelten (u. a. Ranking-Instabilität bei
  n=23, Filter-Anteil der Konsens-Bildung),
- welche Fragen offen sind.

Insbesondere wird **nicht** entschieden, ob Full-Page grundsätzlich besser
ist, und **nicht** entschieden, ob die Referenzdaten fehlerhaft sind.

## Konsequenz

- Keine weiteren großen Benchmarks, keine neuen OCR-Varianten, keine
  Architekturänderung, bis Q1–Q4 beantwortet sind.
- `real_math` hat weiterhin **keinen** Dev/Holdout-Split. Alle 57 Math-Zeilen
  liegen in einer Klasse. Vor jeder Optimierung, die auf Math-Zeilen zielt,
  muss das aufgelöst werden — andernfalls wiederholt sich der in M1
  dokumentierte Fall. (Split-Logik: `bench/vlm_consensus.py:158-162`;
  sie trennt nach Notebook, aber nur für `real_text_*`.)
- Das Konsens-Filterverhalten (M2) ist vor jeder Änderung an
  `build_consensus.py` zu berücksichtigen: 285 Zeilen liegen im Band
  50–89 % und sind bislang nicht ausgewertet.

## Verwandte Dokumente

- `docs/adr/ADR-001-error-audit.md` — manueller Fehleraudit (M4)
- `docs/adr/ADR-002-metriken.md` — Metrikdefinitionen (Q2), pending
- `docs/adr/ADR-003-strukturoutputs.md` — Bounding-Boxes / Lesereihenfolge (Q3), pending
- `docs/adr/ADR-004-eingabedatenvertrag.md` — Vertrag aus SymPy-Validator (Q4), pending
- `data/arena/arena_results.tsv` — Rohdaten M1
