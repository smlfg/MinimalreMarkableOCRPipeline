# OCRia-nano-1 det.onnx auf eigener Handschrift – Ergebnis 2026-11-24

**Urteil: verworfen.** Das Gate (≥95 % der Zeilen sauber gefunden) ist nicht erfüllt.

## Aufbau
- Daten: 4 Probe-Blätter `bench/formula_flywheel/own/probe/sheet*.png` mit je 10 Zeilen, also 40 Zeilen. Die gedruckten Zeilennummern wurden abgeschnitten.
- Modell: `det.onnx` von huggingface.co/llamaindex/OCRia-nano-1 (main), Schwelle 0,55 aus `det.meta.json`.
- `lit models pull ocria-nano` (liteparse) brach ab, weil die Revision `v1.0.0` nicht auf HF liegt. Deshalb lief det.onnx direkt über onnxruntime. Getestet wurden Normalisierung (plain/ImageNet) × Skala (1×/2×), gewertet wurde die beste Variante.
- Glue und venv liegen nur im Scratchpad, im Repo wurde nichts installiert.

## Zahlen (beste Variante pro Blatt, meist plain 1×)
| Blatt | Zeilen mit ≥1 Box | Zusammengelegt | Zusatzfragmente | Tinte in Boxen |
|---|---:|---:|---:|---:|
| sheet  | 10/10 | 0 | 8 | 50 % |
| sheet2 | 10/10 | 0 | 5 | 60 % |
| sheet3 |  9/10 | 0 | 8 | 41 % |
| sheet4 |  9/10 | 0 | 6 | 58 % |
| **Summe** | **38/40 (95 %)** | 0 | 27 | **≈52 %** |

„38/40“ ist geschönt. Es zählt jede Zeile, in der irgendeine Box liegt, und die Zeilenbänder waren vorgegeben. Die Overlays (`overlay_*.png`) zeigen das Problem:
- Die Boxen decken nur einen Teil jeder Zeile ab. Ziffern am Zeilenende fehlen („8 9“, „88“, „5“, „51“).
- Brüche, Exponenten und Wurzeln werden fast nie erfasst, zum Beispiel `(x+3/2)^2 = 13/4` oder `x=-3/2±√(13/4)`.
- Die Zeile `x = 5` wurde gar nicht gefunden.
- Nur etwa die Hälfte der Tinte liegt in einer Box. Ein Leser hinter diesem Detektor bekäme halbe Formeln.

## Warum
Der Detektor wurde auf gedruckte Dokumente destilliert. Er erwartet gleichmäßige Glyphen auf einer Grundlinie. Handschrift, 2D-Mathe und große Wortabstände passen nicht in dieses Muster.

## Nächster Schritt (offen)
Für die Lücke „Seitenstruktur“ bleiben Kandidaten 2–4 aus `UPSTREAM_SEARCH.md`. Am billigsten ist das y-Clustering der .rm-Striche, weil die Strichdaten schon vorliegen.
