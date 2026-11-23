# ADR 002: Getrennte Metriken für Text, Dokumentstruktur und mathematische Struktur

**Status:** provisional, 23.11.2026 · **Beantwortet:** offene Frage Q2 aus `ADR-001-ocr-messaufbau-provisional.md`

> **Warum provisional:** Die Recherche hat bestehende Standards identifiziert, die
> für den Anwendungsfall **nicht direkt übertragbar** sind. Die Metrik-Auswahl
> steht unter dem Vorbehalt der Datenlage (siehe „Konsequenz").

## Kontext

Der aktuelle Messaufbau kennt **eine** Metrik: `post.accuracy(gt, pred)`,
eine normalisierte zeichenbasierte Levenshtein-Distanz. Das ist für die
Fragestellung „liest die Engine den Text richtig" adäquat, für zwei andere
Fragen nicht:

1. **Dokumentstruktur** — Welche Zeile steht wo? In welcher Reihenfolge?
2. **Mathematische Struktur** — Ist `17·3=3·10+3·7` mathematisch dasselbe
   wie `17x3=3x10+3x7`? Zeichenmetriken verwechseln `x` und `·` als
   gleichwertig falsch, obwohl die Rechnung stimmt.

## Recherche: bestehende Standards

### CROHME (Competition on Recognition of Online Handwritten Mathematical Expressions)

Chronologie: ICFHR 2014/2016, ICDAR 2019, ICDAR 2023 (7. Ausgabe).
Zuletzt: 3 905 neue handschriftliche Gleichungen, drei Modalitäten
(on-line Strokes, off-line Bilder, bimodal).

**Repräsentation:** *Symbol Layout Tree* (SLT) — ein **label graph** über
Strokes. Jeder Stroke trägt ein Symbol-Label, jede Kante eine
räumliche Beziehung (parent/child, merge, horizontal). Weil ein einzelner
Stroke多种 Rollen haben kann (z. B. ein `2` in einer Zelle einer Matrix),
erlaubt das Label-Graph-Format **konfligierende Segmentierungen** direkt
zu vergleichen.

**Metriken (CROHME Task 2 / 2013-Protokoll):**

| Ebene | Metrik |
|---|---|
| Expression | Expression Recognition Rate (Ranking-Metrik) |
| Expression | Rate mit 1, 2 oder 3 Symbol-/Relations-Fehlern ohne Strukturänderung |
| Symbol | Recall/Precision für **Segmentierung** |
| Symbol | Recall/Precision für **Detektion** (Segmentierung **und** Klassifikation) |
| Relation | Recall/Precision für Symbolpaar-Beziehungen, in SLT und in SRT+DAG |
| Stroke | Label Hamming Distance (ΔB), gewichtete Hamming-Distanz (ΔE) |
| Struktur | **Structure Confusion Histograms** (falsche Subgraphen nach Größe) |

**Für uns relevant:** Die Relations-Recall/Precision und die
Structure-Confusion-Histogramme sind exakt das, was für Q3 fehlt.
Die Label-Graph-Darstellung ist der eigentliche Beitrag — sie erlaubt,
**teilweise korrekte** Ergebnisse zu quantifizieren statt nur „ganz oder
gar nicht".

**Nicht direkt anwendbar:** CROHME ist **stroke-basiert** (on-line). Unsere
Quelle ist ein **Rendered-PNG** (off-line). Strokes sind bei uns nicht
verfügbar — der reMarkable liefert zwar `.rm` mit Strokes, aber die
Rasterung zu PNG verliert diese. Eine Umstellung auf off-line CROHME
Task 2 (2023) wäre möglich, setzt aber Symbolsegmentierung voraus, die
unsere Engine (Apple Vision, reiner Text-OCR) nicht liefert.

### CDM (Character Detection Matching)

Quelle: arXiv 2409.03643, UniMERNet-Projekt, Shanghai AI Laboratory.

**Kernidee:** Statt LaTeX-Strings zeichenweise zu vergleichen, werden
**beide** Vorhersage- und Referenzformel als **Bild** gerendert und dann
visuell abgeglichen — Character-Detection-Matching mit räumlicher
Positionsinformation.

**Begründung (direkt zitierbar aus dem Abstract):** „They overlook the fact
that the same formula has diverse representations and are highly sensitive
to the distribution of training data, thereby causing the unfairness in
formula recognition evaluation."

**Vergleich zu BLEU/Edit Distance** (aus der Arbeit): CDM stimmt enger mit
der menschlichen Bewertung überein und ist gerechter, weil
Repräsentationsunterschiede verschwinden.

**Für uns relevant:** CDM löst **genau** das Problem, dass `17·3` vs. `17x3`
in einer Zeichenmetrik bestraft wird, obwohl es dieselbe Formel ist.

**Nicht direkt anwendbar:** CDM vergleicht **gerenderte Formeln** (LaTeX →
Bild) — also **gesetzt** und **strukturiert**. Unsere Handschrift ist weder
gesetzt noch strukturiert. CDM setzt außerdem eine LaTeX-Ground-Truth
voraus, die wir nicht haben (unser Referenztext ist freier Text).

### OmniDocBench (CVPR 2025)

1651 PDF-Seiten, 10 Dokumenttypen, 5 Layouttypen, 5 Sprachen. Enthält
ausdrücklich **handschriftliche Notizen**. 28 Block-Level- und
4 Span-Level-Annotationen.

**Metriken:**

| Dimension | Metrik | Richtung |
|---|---|---|
| Text | **Normalized Edit Distance** | ↓ besser |
| Formel | **CDM** | ↑ besser |
| Tabelle | **TEDS** / TEDS-S | ↑ besser |
| Lesereihenfolge | **Read Order Edit Distance** | ↓ besser |
| Layout | **COCODet** (mAP, mAR) | ↑ besser |

**Gesamtwert:**
```
Overall = ((1 - Text Edit Distance) * 100 + Table TEDS + Formula CDM) / 3
```

**Lesereihenfolge** wird als Edit-Distanz über die **Sequenz der
Text-Elemente** berechnet.

**Für uns relevant:**
1. OmniDocBench trennt **genau die drei Dimensionen**, die wir brauchen:
   Text (Edit Distance), Lesereihenfolge (Read Order Edit Distance),
   Formel (CDM). Das ist die **normative Vorlage** für unsere Metriktrennung.
2. Das Matching-Verfahren ist direkt übertragbar: **Adjacency Search
   Match** — normalisierte Edit-Distanz zwischen allen Absatzpaaren
   berechnen, Paare oberhalb eines Schwellwerts direkt matchen, für den
   Rest Fuzzy-Matching mit optionaler Merge-Suche.
3. OmniDocBench bewertet **handschriftliche Notizen** — der Domänen-
   übertrag auf reMarkable-Seiten ist belegt.

**Nicht direkt anwendbar:** OmniDocBench setzt **LaTeX-Annotationen für
Formeln** voraus. Unsere Ground Truth ist freier OCR-Text. Der CDM-Teil
des Scores ist daher zunächst nicht berechenbar.

## Entscheidung (Entwurf, noch nicht in Kraft)

**Drei getrennte Metrikfamilien**, abgeleitet aus OmniDocBench, mit
CROHME/CDM als Referenz für den Formelteil:

### M-A — Textgenauigkeit (existiert bereits)

**Normalized Edit Distance**, normalisiert über die Zeilenlänge.
= das heutige `post.accuracy`, invers skaliert.
Referenz: OmniDocBench „Text Recognition".
**Status:** bereits im Einsatz, an CROHME/OmniDocBench-Norm ausgerichtet.

### M-B — Dokumentstruktur und Lesereihenfolge (neu)

| Metrik | Definition | Referenz |
|---|---|---|
| **B1 Segmentierungs-Recall** | Anteil der GT-Zeilen, die im Output als (normalisierte) zusammenhängende Zeichenfolge vorkommen | CROHME „Symbol Recall", adaptiert |
| **B2 Zeilenanzahl-Delta** | \|Anzahl erkannter Zeilen − Anzahl GT-Zeilen\| pro Seite | OmniDocBench-Ähnlich, elementweise |
| **B3 Read Order Edit Distance** | Levenshtein zwischen der Sequenz der GT-Zeilen-Indizes und der Sequenz der erkannten Zeilen | OmniDocBench „Read Order" |

**B3 ist die zentrale neue Metrik**, weil sie beantwortet: *Ist die
Reihenfolge der Zeilen auf der Seite richtig?* Das ist für einen Tutor
entscheidend (Rechenschritte müssen in Reihenfolge gelesen werden), und
es ist mit Zeichengenauigkeit **nicht** messbar.

### M-C — Mathematische Struktur (neu, mit Abhängigkeit)

Drei Stufen, abhängig von der Verfügbarkeit strukturierter Ground Truth:

| Stufe | Anforderung | Metrik | Referenz |
|---|---|---|---|
| C1 | GT ist parsebarer Ausdruck | **Symbol-Rate**: Anteil GT-Zeilen, die von `sympify` fehlerfrei geparst werden | Zwischenstufe, selbst definiert |
| C2 | GT + Prediction sind parsebar | **Äquivalenz-Rate**: Anteil, bei denen `simplify(lhs-rhs) == 0` | CROHME „Expression Recognition Rate" |
| C3 | GT in LaTeX normalisierbar | **CDM** | CDM (arXiv 2409.03643) |

**C3 ist heute nicht berechenbar** — es fehlt die LaTeX-Referenz. C1/C2
sind es, sobald die OCR-Schicht den in `ADR-004` definierten
Eingabedatenvertrag erfüllt.

**Warum die Stufen getrennt:** C1 misst die *Referenz-Parsebarkeit*,
C2 misst die *semantische* Korrektheit. Der Audit aus
`ADR-001-error-audit.md` hat gezeigt, dass 4 von 30 Beispielen
alignment-Instabil sind — die Richtung (falsche Referenz vs. falsche
Erkennung) ist mit Textmetriken nicht auflösbar. C1 allein kann das
teilweise trennen: eine nicht parsebare GT-Zeile ist per Definition
**kein verwertbarer Math-Konsens**.

## Konsequenz

- **Keine eigene Metrik ohne Normverweis.** Jede der obigen Metriken nennt
  ihre Quelle. Wo wir abweichen (B1–B3, C1–C2), ist das explizit markiert.
- **Die heutige Gesamt-Auswertung bleibt zeichenbasiert.** B/C sind
  zusätzliche Sichten, kein Ersatz — der Vergleich der 9 Arena-Varianten
  bleibt gültig, weil er für alle Varianten gleich ist.
- **C3 (CDM) ist blockiert** bis LaTeX-Referenzdaten existieren. Das ist
  eine **Datenfrage**, keine Codefrage.
- **`real_math` braucht weiterhin einen Split** (siehe ADR-001). C2 macht
  die Auswertung erst nach dem Split aussagekräftig.
- **Nächster Schritt:** B3 (Read Order) und C1 (Parsebarkeit) sind ohne
  zusätzliche Daten berechenbar und eignen sich als **erster Test** der
  neuen Metriken. C3 braucht eine separate Anstrengung.

## Offen

- LaTeX-Referenz für C3: gibt es sie im Workspace?
- Schwellwert für B1-Recall („normalisiert" ist definiert, der Cut-off
  zwischen „enthält" und „enthält nicht" nicht).
- B3 braucht eine Referenz-Lesereihenfolge — die GT-Zeilen-Reihenfolge im
  Manifest ist **nach Notebook** sortiert, nicht nach Position auf der
  Seite. Das ist eine Datenlücke.
