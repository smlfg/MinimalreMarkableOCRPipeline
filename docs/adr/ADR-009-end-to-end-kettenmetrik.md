# ADR 009: End-to-End-Kettenmetrik (ProcessBench-F1) und Ketten-Kalibrierungsblatt

**Status:** provisional, 23.11.2026 · **Baut auf:** ADR-005 (Seitenschema), ADR-007 (nie still korrigieren), ADR-008 (Kalibrierungsblätter) · **Recherche:** `docs/research/UPSTREAM_SEARCH-struktur-benchmark.md` Teil C · **Code:** `bench/chain_bench.py`, `bench/formula_flywheel/kalib/ketten/`

## Kontext

Bisher wird nur Stufe ③ gemessen (OCR je Zeile). Am Ende zählt aber Stufe ⑤: Sagt der Tutor das Richtige?

```text
Handschrift -> Zeilen finden -> OCR -> Validator prüft Schritt n -> Tutor-Urteil
                    ②            ③              ④                    ⑤
```

Bei 99 % OCR auf Einzelzeilen kann der Tutor trotzdem falsch liegen. Umgekehrt kostet ein Lesefehler in einer Zeile, die für das Urteil keine Rolle spielt, nichts.

## Entscheidung

**Zielmetrik ist die ProcessBench-F1** (QwenLM/ProcessBench, `code/run_eval.py`, Apache-2.0). Das Format wird übernommen, nicht neu erfunden: `steps[0]` ist die Aufgabe, `label` ist der Index des frühesten falschen Schritts, `-1` heißt korrekt.

- `acc_err`: Anteil der fehlerhaften Ketten, bei denen der früheste Fehlerschritt exakt getroffen wird
- `acc_ok`: Anteil der korrekten Ketten ohne falschen Alarm
- `F1 = 2 · acc_err · acc_ok / (acc_err + acc_ok)`

**Zählregel für Nachfragen** (vor der ersten echten Messung festgelegt): Eine unsicher gelesene Zeile (ADR-007) oder eine leere Zeile führt zur Prognose `ask`. ProcessBench kennt diese Klasse nicht. Deshalb werden zwei F1-Werte berichtet:

- **F1_strict:** `ask` zählt als falsch.
- **F1_answered:** Ketten mit `ask` fallen heraus. Die **Abdeckung** wird immer mit angegeben.
- Getrennt davon die **Nachfrage-Rate** und die Zahl der **berechtigten** Nachfragen. Berechtigt heißt: In der Zeile lag tatsächlich ein Lesefehler, oder sie fehlte.

**Zwei Pfade je Lauf:**

| Pfad | Eingang | misst |
|---|---|---|
| `--oracle` | GT-LaTeX | Obergrenze von ④+⑤ (Validator, Tutor), ohne Tablet |
| echt | Slot-PNGs → `ocr/formula.py` → `ocr/coherence.py` | ganze Kette ③–⑤ |

**Fehlerzuordnung:** Liegt der echte Pfad falsch, das Orakel aber richtig, gilt die Ursache als ③ (OCR). Liegt auch das Orakel falsch, als ④/⑤. Pro Kette wird außerdem festgehalten, ob ein Lesefehler einen urteilsrelevanten Schritt traf (`miss_relevant`).

**Bausteine, alle wiederverwendet (kein eigener Prüfer):**
- `ocr/latex.parse` je Gleichungsseite
- `decimal_comma`
- `AlgebraAgentChecker` (urgent-Math-help → algebra-agent `v_b` / `arithmetic`)
- `SimpleTutor`, in v1 deterministisch: Prognose ist der erste Schritt, der nicht `correct` ist

**Ketten-Kalibrierungsblatt** (`bench/formula_flywheel/kalib/ketten/`, das PDF liegt in `data/kalib/Kalibrierung-Ketten.pdf`):
- 28 Ketten mit je 3–4 Schritten auf 6 Seiten, 60 Schreib-Slots
- 15 Ketten mit eingebautem Fehler, früheste Fehlerstelle bei Schritt 1/2/3 in 8/4/3 Ketten
- Fehlerarten: Vorzeichen, Distributivgesetz, Divisionsregel, quadratische Ergänzung (`18/13` statt `13/4`), fehlende zweite Wurzel, falsch gekürzt, Nenner addiert, Exponenten multipliziert
- Gedruckt ist die Aufgabe. Der Owner schreibt die Schritte rechts neben die graue Vorlage ab.

## Befunde aus der Validator-Probe (23.11.)

- `v_b` vergleicht jeden Schritt mit der **Lösungsmenge der Aufgabe**, nicht mit dem Vorschritt. Ein Fehler zieht sich deshalb durch alle folgenden Schritte. Der erste `incorrect` ist der früheste Fehler, das passt zu ProcessBench.
- `arithmetic` prüft jede Zeile für sich. Ein Folgeschritt nach einem Fehler kann wieder `correct` sein. Für die F1 zählt nur der erste Fehler.
- Nicht prüfbar, deshalb nicht in v1: `±` und Wurzelziehen (Ergebnis `uncertain`), zwei Lösungen als „x=a oder x=b“, irrationale Lösungen, Ableitungen. Zwei Lösungen werden deshalb als Faktorform geschrieben: `(x-a)(x-b)=0`.
- SymPy wertet ganze Zahlengleichungen sofort zu `True` aus. Deshalb wird jede Gleichungsseite einzeln geparst. Ein Schritt, der mit `=…` beginnt, setzt den vorigen Ausdruck fort.

## Stand 23.11.

| Lauf | F1_strict | F1_answered | Abdeckung | Nachfrage |
|---|---:|---:|---:|---:|
| Orakel (28 Ketten) | 1,00 | 1,00 | 100 % | 0 % |
| echt | offen: Blatt noch nicht geschrieben | | | |

Ein Rauchtest des echten Pfads mit OCR-Attrappe (ein Lesefehler, eine unsichere Zeile, eine fehlende Zeile) ergab F1_strict 0,87 und F1_answered 0,95. Die Zuordnung zu ③ hat in allen drei Fällen gestimmt.

## Ablauf echte Messung

1. `Kalibrierung-Ketten.pdf` aufs Tablet laden, abschreiben, Dokument-ID in `kalib_eval.py` → `DOCS["ketten"]` eintragen.
2. `python bench/formula_flywheel/kalib_eval.py ketten` erzeugt `data/own_ketten.jsonl`.
3. `.venv_tt/bin/python bench/formula_flywheel/tt_run.py own_ketten` füllt den TexTeller-Cache. Ohne diesen Schritt bricht der echte Pfad mit `KeyError` ab.
4. `.venv_structure/bin/python bench/chain_bench.py "notiz"` schreibt eine Zeile in `bench/results_chain.tsv` und die Details je Kette in `kalib/ketten/last_real.jsonl`.

## Folgen

- Die OCR-Zahlen aus ADR-008 sind nur noch Diagnose. Ob eine OCR-Änderung behalten wird, entscheidet auch die Ketten-F1.
- **v2:** dasselbe Blatt, aber statt `SimpleTutor` ein lokales LLM mit den Format-Varianten aus Teil B (JSON, LaTeX, Text mit Prüfzeile), gemessen mit derselben Zählregel. Das beantwortet, in welcher Form das LLM die Mathe bekommen soll.
- **Später:** dieselben Ketten als freie Seite ohne Slots. Dann wird auch ② gemessen (Zeilenfindung).
