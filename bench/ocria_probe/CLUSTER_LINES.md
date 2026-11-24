# cluster_lines (algebra-agent) auf eigener Handschrift – Ergebnis 2026-11-24

**Urteil: Gate erfüllt, 100 % saubere Zeilen.** Einschränkung siehe unten.

## Aufbau
- Funktion: `cluster_lines` aus `../algebra-agent/src/algebra_agent/rm_page.py:88`, unverändert. Sie gruppiert Striche transitiv nach Höhe, Diagonalen (Durchstreichungen) werden nachträglich zugeordnet.
- Daten: die echten .rm-Striche der Kalibrierblätter
  - probe: 4 Seiten, 40 Zeilen (`kalib/kalib_gt.jsonl`)
  - ketten: 6 Seiten, 60 Schritte (`kalib/ketten/ketten_gt.jsonl`)
- Wahrheit: die Slot-Bänder aus `kalib_eval.slots()`, also dieselben Bänder, mit denen das Flywheel die PNGs schneidet.
- „Sauber“ heißt: Alle Striche eines Slots liegen in genau einer Zeile, und diese Zeile enthält keine Striche eines anderen Slots.
- Glue: `scratchpad/ocria/glue/cluster_probe.py`, nicht im Repo.

## Zahlen
| Blatt | Slots | sauber | zerteilt | zusammengelegt |
|---|---:|---:|---:|---:|
| probe  | 40 | 40 | 0 | 0 |
| ketten | 60 | 60 | 0 | 0 |

Vergleich mit OCRia-nano-1 det.onnx auf denselben 40 Probe-Zeilen: etwa 52 % der Tinte lagen in Boxen, Brüche und Exponenten fehlten (`RESULT.md`).

Die Overlays (`cluster_*.png`) zeigen: Exponenten (`x^2`, `2x^3`), Doppelbrüche (`13/4`), Wurzeln und eng stehende Kettenschritte (`2x=-4` / `x=-2`) landen jeweils komplett in einer Box.

## Einschränkung
Die Kalibrierblätter haben vorgegebene Schreibzeilen mit viel Abstand. Freie, dichte Notizseiten ohne Vorlage sind noch nicht gemessen. Dort kann `pad=18` Zeilen zusammenkleben, zum Beispiel wenn ein Bruchnenner fast die nächste Zeile berührt.

## Nächster Schritt (offen)
1. Eine freie Notizseite mit dichten Zeilen schreiben, die GT von Hand festlegen und `cluster_lines` darauf messen.
2. Wenn das hält: `cluster_lines` per Pfad oder Import in die Seitenstufe dieser Pipeline übernehmen, statt `ocr/pre.py:split_lines` (Bild-Streifen). Das wird eine ADR.

---

# Nachtrag: freie Seiten aus data/real_corpus (265 Seiten, ohne GT)

**Urteil: Auf freien Seiten ist das Gate nicht erfüllt.** Auf den Kalibrierblättern lief es fehlerfrei, weil die Vorlage Abstand erzwingt.

## Zahlen
- 265 Seiten, 1373 Zeilen gefunden.
- 208 Zeilen (15 %) sind verdächtig: höher als 2,2× die mittlere Zeilenhöhe der Seite. Sie verteilen sich auf 116 Seiten (44 %).
- Stichprobe `corpus/rand_881240d5_9a5e90a6.png` (echte Handschrift, etwa 9 echte Zeilen): 2 Zusammenlegungen, also rund 78 % sauber.

## Drei Fehlerarten (Overlays in `corpus/`, orange = verdächtig)
1. **Dichte Handschrift:** Unterlängen (g, J, y) reichen in die nächste Zeile. Weil das Clustering transitiv ist, werden zwei Zeilen zu einer. Beispiele: „endliches Eingabealphabet / endliches Bandalphabet“ und „alles ist berechenbar / Berechenbarkeit“.
2. **Diagramme und Kästen:** Ein Rahmen oder eine Skizze wird als eine einzige „Zeile“ gezählt (`rand_1c326815_*`). Für Formel-OCR ist das harmlos, es braucht aber eine eigene Klasse „Zeichnung“.
3. **Vom Agenten gezeichnete Textseiten** (Druckschrift, eng): `pad=18` ist größer als der Zeilenabstand, also kleben Zeilen zusammen. Diese Seiten sind keine Handschrift und sollten aus dem Korpus gefiltert werden.

## Folgerung
`cluster_lines` ist ein guter Start, so wie es ist reicht es aber nicht. Nötig ist, eine zu hohe Zeile wieder zu teilen: Für jede verdächtige Zeile wird das y-Histogramm der Strich-Schwerpunkte nach zwei Gipfeln durchsucht. Dafür gilt vorher das Upstream-First-Gate, zum Beispiel ein Vergleich mit Kraken-blla auf denselben Seiten.
