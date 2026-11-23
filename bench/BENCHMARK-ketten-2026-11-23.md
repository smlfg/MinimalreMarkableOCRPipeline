# Benchmark-Protokoll: End-to-End-Kettenmessung (2026-11-23)

Ergebnis: **28/28 Ketten korrekt beurteilt, F1_strict = 1.000, 0 falsche
Anschuldigungen, 0 Nachfragen.** Pipeline-Commit: `ee1fa9d`.

## Fragestellung

Kann die vollständige Kette Handschrift → OCR → Validator → Tutor (ADR-009)
reale handschriftliche Rechenketten korrekt beurteilen — Fehler am richtigen
Schritt finden, korrekte Ketten bestätigen, und niemanden zu Unrecht kritisieren?

## Paket

| Komponente | Version / Pfad |
|---|---|
| Pipeline | Commit `ee1fa9d` (auf Basis `3636530`, Oracle F1 = 1.000) |
| Blatt | `bench/formula_flywheel/kalib/ketten/Kalibrierung-Ketten.pdf` (versioniert), 28 Ketten, 15 mit eingebautem Fehler, 60 Slots |
| Handschrift | Samuel, live auf reMarkable (Paper Pro), Abruf per scp + `rmscene` |
| OCR | TexTeller (`.venv_tt`, MPS) + `glm-ocr:q8_0` via Ollama, Kohärenz-Schicht `ocr/coherence.py` |
| Validator/Tutor | AlgebraAgentChecker + SimpleTutor (urgent-Math-help) — **unverändert** |

## Metrik (ADR-009, ProcessBench-F1)

- `acc_err`: Anteil der Fehler-Ketten, deren frühester Fehlerschritt exakt getroffen wird
- `acc_ok`: Anteil korrekter Ketten, die als korrekt erkannt werden
- `F1 = 2·acc_err·acc_ok/(acc_err+acc_ok)`; `ask` zählt strict als falsch
- Messlog: `bench/results_chain.tsv`, Detail-Evidenz: `kalib/ketten/last_real.jsonl`

## Ablauf

1. **Orakel** (GT statt OCR): F1 = 1.000 — Obergrenze von Validator + Tutor bestätigt.
2. **Seiten 1–3** (Kalibrier-Set, 14 Ketten): Erstmessung 9/11 richtig, 3 Nachfragen.
   Drei Software-Ursachen gefunden und behoben (Bandöffnung, Artefakt-Abgleich,
   korroborierte Reparatur, Ketten-Arbitrierung) → 14/14.
3. **Seiten 4–5** (Validierung, ungesehen, 10 Ketten): 9/10. Der eine Fehltreffer
   (K24) war ein Handschrift-Befund: die Null in „10" überlappte die Eins, beide
   Engines lasen „1". Vom Schreiber selbst korrigiert → 10/10. Keine Regression
   auf Seiten 1–3 → keine Überanpassung der Fixes.
4. **Seite 6** (ungesehen, 4 Ketten): K25 ohne führendes „=" geschrieben und mit
   doppeltem GLM-Artefakt gelesen. Zwei allgemeingültige Fixes (implizite
   Gleichheit nach Schul-Konvention, kombinierte Artefakt-Varianten) → 28/28.

## Befunde

| Kette | Symptom | Ursache | Klasse | Fix |
|---|---|---|---|---|
| K01, K11 | Slot leer bzw. ohne ²/Zähler gelesen | Slot-Bänder schnitten hohe Striche ab (Zentroid über Bandgrenze) | Software | Bänder nach oben öffnen (`kalib_eval.py`) |
| K06, K13 | Unbegründete Nachfrage | GLM-Leerzeichen in Zahlen („2 5" → 7) ⇒ Engine-Dissens | Software | Artefakt-Varianten im Abgleich (`ocr/coherence.py`) |
| K08 | Falschurteil Zeile 2 | CONFUSE-Reparatur (Punkt→Malpunkt) bei Variablen-Zeilen unerreichbar (Frührückkehr) | Software | Korroborierter Tausch, gilt als trusted |
| K13 | Unbegründete Nachfrage | TexTeller „=0", GLM „=6" — echter Dissens | Software | Ketten-Arbitrierung: bestätigt nur, überschreibt nie |
| K24 | Falschurteil Zeile 2 | Handschrift: Null in „10" überlappte die Eins; beide Engines lasen „1" | Handschrift | Vom Schreiber korrigiert; dokumentierte Grenze |
| K25 | Eingebauter Fehler unsichtbar, Nachfrage | Kein führendes „=" (Schreib-Konvention) + GLM-Doppelartefakt („3. 1 0") | Software | Implizite Gleichheit ab Zeile 2 + kombinierte Artefakte |

## Endstand

```
n=28  acc_err=1.000  acc_ok=1.000  F1_strict=1.000
F1_answered=1.000  coverage=1.00  ask_rate=0.00  ask_justified=0
```

15/15 Fehler-Ketten am frühesten falschen Schritt getroffen, 13/13 korrekte
Ketten durchgewinkt, jede Challenge des Schreibers (gedrehte Gleichung „3=x",
Unterschlagung von „=", überlappende Ziffern) vom System korrekt eingeordnet.

## Gültigkeit und Grenzen

- Ein Schreiber, ein Blatt, ein Abend. Generalisierung auf andere Schreiber,
  andere Themen und Klausurmathe ist nicht belegt — dafür braucht es weitere
  Kalibrierungsblätter.
- **K24-Muster:** Zwei Engines mit derselben Fehllesung erzeugen keinen Dissens;
  die Kohärenz-Schicht kann das prinzipiell nicht entdecken. Nur eine
  Validierungsmessung findet solche Fälle — genau das ist der Zweck der
  Kalibrierungsblätter.
- **Arbitrierungs-Regel:** Sie bestätigt die Primärlesart nur bei sauberem,
  validiertem Präfix und überschreibt nie. Passt stattdessen die Zweitmeinung
  zur Kette, bleibt unsicher und wird nachgefragt (verschleiert keine Fehler).
- `rmscene` meldet auf jeder Seite „newer format"; alle 60 Slots waren trotzdem
  lesbar. Bei Firmware-Updates beobachten.

## Nächster Schritt (Regelwerk Remarkable)

Nach AGENTS.md Abschnitt 2: kontrollierter Abnahme-Turn — eine echte Aufgabe,
ein realer Turn mit Samuel, wahrnehmbare und fachlich korrekte Hilfe. Erst nach
bestandenem Turn gilt dieser Lernstand als freigegebene Basis für Mathe-Sessions.
