# Missions-Belege M-20261123T215216-c4b32696 (Ouroboros v2) + Änderungsprotokoll

## dc4 — Eingefrorenes unangetastet

- `prepare.py`, `models.py`, `pipeline.py` (Flywheel, EINGEFROREN laut program.md): kein Diff.
- `urgent-Math-help` (Validator/Tutor): kein Diff, nicht betreten.
- `SchlangebeißtinSchwanz`: read-only Import; Glyph-Erweiterung (∫, Σ, π) nur lokal
  im RAM über `font.GLYPHS` — keine Datei dort geändert.
- `ocr/formula.py`, `ocr/coherence.py`: unverändert seit Owners Commit `ee1fa9d`.

## Änderungsprotokoll (was / wie / wann)

| Zeit (MEZ) | Was geändert | Wie | Warum |
|---|---|---|---|
| 21:52 | `bench/synth/gen_ketten.py` | Exponent-Anhebung `6.5·scale, 0.62×` → `8.5·scale, 0.55×` | v1-Fund: flache Exponenten wurden als Nachbarziffer gelesen (`3^{5}`→`35`) |
| 21:55 | `bench/synth/gen_ketten.py` | Neue Templates `g_beidseitig`, `g_klammer2` (verschachtelt), `g_bruchgl` (Bruchgleichung) | "kompliziertere Algebra", validatorfähig |
| 21:58 | `bench/synth/gen_ketten.py` | Bugfix `g_bruchgl`: `c=b+k`, `x=a·k` statt falscher `c=sol+a·b`-Arithmetik | Schwanz-Gate verwarf alle Ketten des Templates — Generator-Bug, GT nie gebogen |
| 21:58 | `bench/synth/gen_ketten.py` | Randfall ausgeschlossen: `m=n=2` bei Potenz-Fehlern (`m+n=m*n`, der "Fehler" wäre wahr) | Gate-Fund: label 1 wurde korrekt als -1 erkannt |
| 21:52 | `bench/formula_flywheel/synth/gen_hard.py` (neu) | 19 Formel-Generatoren (Integral/Summe/Algebra/Wurzel/Pi/Bruch), SymPy-Wahrheits-Gate (`doit`/`expand`, numerische Stichprobe, C→0) | schwere Mathe mit bewiesenem GT |
| 21:58 | `gen_hard.py` | Bugfix bestimmte Integrale: gerade Differenz `hi-lo+2k` | Gate verwarf `∫₀⁵x dx=12` (wahr: 12.5) — Generator-Bug |
| 22:0x | `bench/synth/gen_ketten.py 30 47` / `gen_hard.py` | Final erzeugt: 30 Seiten, 143 Ketten (81/62 korrekt/Fehler), 303 Slots; 136 Formeln (40 Integral, 28 Summe, 33 Algebra, 16 Wurzel, 7 Pi, 12 Bruch) | Kampagne v2 |

## Messungen v2 (2026-11-23, seed 47/31)

| Pfad | n | Ergebnis | Vergleich |
|---|---:|---|---|
| synth_oracle (chain) | 143 | F1 **1.000** | GT per Konstruktion gegen Validator+Tutor bewiesen |
| synth (chain, OCR) | 143 | F1 **0.965**, coverage 1.0, **0 Nachfragen** | v1: 0.934, 1 unberechtigte Nachfrage |
| synth_hard (Formeln) | 136 | struct **0.603**, char 0.738, p95 0.93 s, coverage 0.603, **prec_certain 1.0** | neue Stufe |

Themen-Breakdown synth_hard (struct): Algebra 0.91 · Bruch 1.00 · Pi 1.00 ·
Integral 0.65 · Wurzel 0.44 · Summe 0.00.

Funde (Stufe ③ OCR, Simulator-Realismus):
1. **Σ-Glyph** wird als `z`/`3`/`s` gelesen — Inhalt dahinter (`k=1`, `^{n}`, `n(n+1)/2`)
   sitzt perfekt. Realismusloch im selbstgezeichneten Glyph, kein Pipeline-Fehler.
2. **∫-Glyph funktioniert meist**; Integral-Fehler sind fast nur `C→6`/`c` (Symbolname in SymPy).
3. **prec_certain 1.0**: jede sicher gelesene Zeile war strukturell richtig —
   die Vertrauenslogik (ADR-007) trägt bis zum Integral-Niveau.

## Batch-Protokoll (ab v3, Owner-Anweisung 23.11. ~22:15)

Kampagnen laufen in **Batches à 50**, pro Batch: erzeugen → rendern → TexTeller →
Messung → Sprachausgabe (Thorsten) + Protokoll-Eintrag. Kein Monolith-Lauf.
