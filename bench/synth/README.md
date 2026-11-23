# bench/synth — Ouroboros: synthetische Kettenseiten (ADR-009)

Der AI-Student schreibt GT, die Schriftsimulation schreibt ab, die Pipeline liest —
die Schlange beißt sich in den Schwanz: GT ist **per Konstruktion** gegen denselben
Validator+Tutor bewiesen (`chain_bench.judge`, Oracle-F1 = 1.0), und die OCR-Messung
läuft durch exakt denselben Pfad wie das reale Kalibrierungsblatt.

## Erzeugen

```bash
.venv_structure/bin/python bench/synth/gen_ketten.py [seiten=10] [seed=23]
cd bench/formula_flywheel && ../../.venv_tt/bin/python tt_run.py --files ../synth/png/synth_S*.png
.venv_structure/bin/python bench/chain_bench.py --oracle --synth   # muss F1 = 1.0 sein
.venv_structure/bin/python bench/chain_bench.py --synth "notiz"    # OCR-Pfad
```

## Dateien

- `gen_ketten.py` — Generator (deterministisch per Seed). Ketten nur in validatorfähigen
  Formen (Vokabular aus `kalib/ketten/items.py`): linear, Klammer, quadratisch ±k/pq,
  Bruch, Zahlterm, Potenz. ~45% mit bekanntem Erstfehler, konsistent weitergeschrieben.
  **Gate:** jede Kette wird vor dem Rendern durch `chain_bench.judge()` geprüft;
  `pred != label` ⇒ verworfen. GT wird nie nachträglich korrigiert.
- `ketten_gt.jsonl` — Schema wie `kalib/ketten/ketten_gt.jsonl` (versioniert).
- `synth_ketten.jsonl` — Schema wie `own_ketten.jsonl`, `png` relativ zu diesem Ordner.
- `png/`, `pages/` — Slot-PNGs (render-Stil wie `kalib_eval.render`: Breite 4, Pad 20)
  und ganze Seiten 1404×1872 (gitignored, deterministisch regenerierbar).

Schriftsimulation: `SchlangebeißtinSchwanz/dynamic_writer` (read-only import),
Style `student`, per Seite ein "Stimmungs"-Scale. Potenzen = hochgestellte kleine
Ziffer (0.62×, +6.5·scale), Brüche inline (`5/2` ⇒ `\frac{5}{2}`).

## Messungen (2026-11-23, seed 23)

| Pfad | n | F1_strict | Bemerkung |
|---|---:|---:|---|
| synth_oracle | 47 | 1.000 | GT gegen Validator+Tutor bewiesen |
| synth (OCR) | 47 | 0.934 | coverage 0.98, 1 Nachfrage (unberechtigt) |
| real (OCR, ganzes Blatt) | 28 | 1.000 | zum Vergleich, eigenes Blatt |

Alle 3 Fehltreffer Stufe ③ OCR, 2 davon dasselbe systematische Bild:
hochgestellter Exponent zu flach ⇒ TexTeller liest `3^{5}` als `35`.
Nächster Generator-Schritt: Exponent stärker anheben (≈ +8.5·scale, 0.55×) —
Realismusloch im Simulator, kein Pipeline-Fehler.
