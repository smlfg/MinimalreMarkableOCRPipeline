# B1 — Visuelle Gegenprüfung der `alignment_fehler` + `real_math`-Fälle

**Status:** abgeschlossen, 23.11.2026 · **Teil von:** `ADR-001-ocr-messaufbau-provisional.md`
**Beantwortet:** Q1 (Richtung der `alignment_fehler`) · **Öffnet:** B1b (Bucket-Bereinigung)

## Methode

Kein Code an der Pipeline, kein Benchmark. Ein Lese-Hilfsskript
(`Projek-Managment/b1/compose.py`) baut pro Fall ein Bild: links die ganze
Seite mit allen erkannten Zeilen-Bändern (Ziel-Zeile rot), rechts der
Zeilen-Crop 4–6× vergrößert, oben GT / LINE / FULL im Vergleich.

Fallauswahl = **4 `alignment_fehler` + 12 `real_math`**, Schnittmenge 2
→ **14 Fälle** (nicht 16: `#2` und `#27` sind `real_math` *und*
`alignment_fehler` und wurden im Plan doppelt gezählt).

Bilder: `Projek-Managment/b1/cases/case_NN.png`. Quelle:
`data/real_corpus/rendered/` + `data/real_corpus/lines/`,
Klassifikation `data/arena/audit_classified.json`.

Urteil = mein visueller Vergleich der Handschrift mit der GT. Ein
Beurteiler, keine Zweitprüfung. Grenzfälle sind als solche markiert.

## Ergebnis: die 4 `alignment_fehler` sind aufgelöst

| # | GT | LINE | FULL | was auf dem Bild steht | Urteil |
|---|---|---|---|---|---|
| 2 | `j=1` | `V=P` | `J=1` | `j=1` in einem Kasten, klar lesbar | **GT korrekt**, FULL korrekt, **LINE-Fehler** |
| 13 | `knowledge start` | `o uno wiod stand` | `O knowledg stande` | `knowledg stant/start` | **GT tragfähig**, beide Modi scheitern |
| 27 | `0 1 2 3 4 5` | `S` | `0 12` | 6 leere Kästchen, darunter `0 1 2 3 4 5` | **GT exakt korrekt**, beide Modi scheitern |
| 29 | `tun doch period wol aus sin/cos gebildet` | `Can date period` | `ed das sin/es gebildet` | zwei physische Zeilen, GT in Lesereihenfolge zusammengeführt | **GT korrekt** (Merge richtig), beide Modi scheitern |

**→ 0 von 4 sind Referenzfehler. 4 von 4 sind Erkennungsfehler.**

Damit ist die in ADR-001 §„Was dieser Audit noch nicht beantwortet"
Punkt 1 offene Frage entschieden: **die Referenz trägt in diesen vier
Fällen.** Die Klasse `alignment_fehler` war eine **Metrik-Artefakt-Klasse**,
keine Datenklasse — sie hat Fälle gesammelt, in denen die Engine
scheitert, und das als „GT passt nicht" fehletikettiert.

Nebenbefund `#2`: LINE `V=P` vs. FULL `J=1` bei identischem Bildinhalt
bestätigt, dass der **Modus** (Zeilen-Crop vs. ganze Seite) ein eigener
Fehlerfaktor ist — auf einem 150×142-px-Crop verliert Vision den Kontext.

## 3 neue Befunde, die schwerer wiegen als B1

### Befund A — `real_math` ist überwiegend kein Mathe (Bucket-Verschmutzung)

Von den 12 `real_math`-Fällen sind **nur 4 echte Rechenzeilen**:

| # | Inhalt | echt Mathe? |
|---|---|---|
| 1 | `X=7` | ja |
| 3 | `2 + 3 + 10 + 29` | ja |
| 4 | `17·3=3·10+3·7=30+21` | ja |
| 8 | `2,5·6=12+3=15` | ja |
| 27 | Index-Diagramm `0 1 2 3 4 5` unter 6 Kästchen | nein — Layout-Grafik |
| 7 | `watcher 1,5 seh → review` (Dev-Notiz) | nein |
| 9 | komplette Seite „P4 Review — was der 2. Agent fand" | nein — gedrucktes HTML |
| 10 | `Rechenterm erkannt ? Ergebnis mit = ergänzen` | nein — Tutor-Hinweistext |
| 28 | `weil +30 Shoft geht` (Dev-Notiz, SpongeBob-Zeichnung) | nein |
| 6 | `2x + 6 = 16  Ausdruck nicht eindeutig erkannt` | nein — Tutor-Overlay |
| 2 | `j=1` | ja (trivial) |
| 5 | `PAPER-PRO SKILLTEST 22.10.26: OK` (roter Druckkopf) | nein — Überschrift |

**Konsequenz:** Der ausgewiesene Wert `Real Math 87,4 %` / `vision_batch_acc`
misst **nicht** Mathematik. Er misst zu ~⅔ Text- und Dev-Notizen. Der
Math-Anteil im Datensatz ist nicht 57 Zeilen, sondern nach dieser
Stichprobe grob **4 von 12 = 33 % → hochgerechnet ~19 von 57**. Das ist
eine Schätzung aus 12 Fällen, keine Messung.

### Befund B — Seiten enthalten Maschinenschrift und Tutor-Overlays

`#9` ist eine **komplett gedruckte Seite** (HTML-Text, Zeilen wie
„17 Checks gruen", „Groesse 474 Zeilen, davon 153 Tests"). `#6` und `#5`
sind maschinengedruckte Tutor-Ausgaben auf einer handschriftlichen Seite.
`#2`, `#3`, `#13` enthalten gedruckte deutsche Tutor-Hinweise
(„Zeile 1 kann ich nicht sicher lesen. Schreibst du sie bitte etwas
deutlicher?").

Gedruckter Text ist für jede OCR trivial. Er hebt die gemessene Accuracy
systematisch und liefert **keinen** Erkenntniswert für Handschrift.

Zusätzlich: die gedruckten Tutor-Hinweise sind **Metatext**, kein
Lerninhalt. Für einen Tutor-Input sind sie Gift (der Tutor würde seinen
eigenen Hinweis als Lernenden-Text lesen) — das ist genau die
Vertragsverletzung, die `ADR-004` verhindern soll.

### Befund C — erster belegter Referenz-Teilfehler

`#8`: GT = `215·6 = 12+3 = 15`. Auf dem Bild steht eindeutig
**`2,5 · 6 = 12+3 = 15`** — das Komma fehlt in der GT.

Fachlich entscheidend: `2,5·6 = 15` ist die richtige Rechnung,
`215·6` ist Unsinn. Die GT hat den Ausdruck **mathematisch zerstört**,
und zwar durch ein einziges fehlendes Zeichen.

Das ist die Bestätigung des in ADR-001 §„Was dieser Audit noch nicht
beantwortet" Punkt 2 vorhergesagten Risikos: ein Referenzfehler, der wie
normaler Text aussieht, ist mit Textmarkern nicht auffindbar. Die
Aussage „0 `referenz_fehler`" gilt weiterhin für die Klasse
*fabrizierter Text*, aber **nicht** für die neue Klasse
`referenz_teilfehler` (fehlendes/falsches Einzelzeichen bei korrekter
Zeichenzahl-Umgebung).

Nebenbefund: **`·` → `:` ist visuell bestätigt und systematisch.**
`#4` und `#8` sind beide echte Multiplikationszeilen, beide werden mit
`:` gelesen. Damit ist die Multiplikation in **2 von 2** Fällen zerstört
— der teuerste mathematische Einzelfehler im Datensatz.

## Was das für Q1 und den Plan heißt

**Q1 ist beantwortet:** Die Referenz ist in den geprüften Fällen
tragfähig; die `alignment_fehler` zeigen Engine-Versagen, nicht
GT-Fehler. Die Metrik „Zeilen-Recall" misst damit tatsächlich
Erkennungsleistung und nicht Referenzrauschen.

**Q1 ist aber nicht der eigentliche Blocker.** Die visuelle Prüfung hat
einen größeren gefunden: der Datensatz enthält überwiegend etwas anderes
als das, was er zu messen behauptet.

### Konsequenz für B2 (Math-Split einfrieren)

**B2 darf so nicht laufen.** Ein Holdout über 57 Zeilen, von denen nach
Stichprobe ~⅔ Dev-Notizen und Drucktext sind, friert Rauschen ein und
wiederholt strukturell den `tess_best_s15`-Fehler — nur mit anderem
Namen.

Stattdessen **B1b** (neu, blockierend, ~1 h):

1. `real_math`-Bucket inhaltlich filtern: nur Zeilen, die einen
   Rechenterm mit Operator und `=` enthalten (oder eine erkennbare
   Rechenaufgabe). Index-Diagramme, Dev-Notizen, Tutor-Hinweise fliegen
   raus.
2. Gedruckte Zeilen markieren (`annotation`-Flag) und **aus allen
   Metriken ausschließen** — sie sind trivial und für Handschrift-OCR
   nicht aussagekräftig.
3. Danach erst splitten (B2) und einfrieren.

Ergebnis wird ein deutlich kleinerer, aber ehrlicher Math-Datensatz sein.
Das ist richtig so: 19 echte Zeilen mit belastbarem Holdout sind mehr
wert als 57 Zeilen, von denen keine Aussage stimmt.

## Grenzen dieser Prüfung

- **14 Fälle, 1 Beurteiler.** Keine Zweitmeinung, kein Cohen's Kappa.
  Die 4 `alignment`-Urteile halte ich für eindeutig (`#27` und `#2` sind
  nicht anders lesbar). `#13` (`start` vs. `stant`) ist ein Grenzfall,
  ändert aber die Richtung des Urteils nicht.
- **Hochrechnung 33 % Math-Anteil ist extrapoliert** aus 12 Fällen.
  Sie begründet B1b, sie ersetzt keine Messung über alle 57 Zeilen.
- **Keine Vollseiten-Prüfung.** Ich habe die Ziel-Zeile im Seitenkontext
  gesehen, aber nicht jede Seite komplett gelesen. Der Anteil gedruckter
  Seiten (`#9`) ist damit untererfasst.
- `#5`: GT enthält `OK` und `2026`, der sichtbare Druckkopf sagt
  `PAPER-PRO SKILLTEST 22.10.26`. Ob `OK`/`2026` anderswo auf der Seite
  stehen, habe ich nicht geprüft — als Grenzfall markiert, nicht als
  Referenzfehler gewertet.

## Belege

| Artefakt | Pfad |
|---|---|
| Vergleichsbilder (14) | `Projek-Managment/b1/cases/case_01…29.png` |
| Lese-Hilfsskript | `Projek-Managment/b1/compose.py` |
| Klassifikation (Eingang) | `data/arena/audit_classified.json` |
| Seiten-Render | `data/real_corpus/rendered/*.png` |
| Zeilen-Crops | `data/real_corpus/lines/*.png` |

**Hinweis gemäß Workspace-Regeln:** reine Offline-Evaluierung. Kein
eingefrorener Algebra-Tutor-Lernstand, keine Lernfreigabe.
