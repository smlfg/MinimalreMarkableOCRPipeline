# ADR 005: Ausgabeschema der Pipeline (Seiten-JSON für Validator und Tutor-LLM)

**Status:** provisional, 23.11.2026 · **Baut auf:** `ADR-003-strukturoutputs.md`, `ADR-004-eingabedatenvertrag.md` · **Bezug:** `ADR-002-metriken.md` (B3, C1, C2)

## Kontext

ADR-004 legt fest, welche **Zeichenform** eine Zeile haben muss, damit ein Validator sie lesen kann (V1–V7). Offen ist bisher, **welches Objekt** die Pipeline am Ende einer Seite übergibt. Zwei Abnehmer gibt es:

1. einen **deterministischen Validator**, der Rechenschritte prüft (`arithmetic` aus `algebra-agent` oder `SymPyChecker` aus `urgent-Math-help`, siehe ADR-004 Befund 1/2)
2. ein **lokales Tutor-LLM**, das daraus genau einen Lernhinweis ableitet

Aus den Vorgängerprojekten sind drei Fehler belegt, die dieses Schema verhindern soll:

| Fehler | Beleg | Folge für das Schema |
|---|---|---|
| Parser gibt die ganze Seite auf, wenn die erste Zeile unlesbar ist („First-Line-Curse“): 78,6 % der Gold-Zeilen richtig gelesen, aber 97,8 % der Turns `uncertain` | `SchlangebeißtinSchwanz/ARCHITEKTUR_NOTIZEN.md:76-86` | Unsicherheit wird **pro Zeile** markiert, die Kette läuft weiter |
| Guardrails ohne Messung verwerfen richtige Zeilen (Recall 91 % → 20 %) | `mlops-gedanken/5-seiten-labor/BENCHMARK-10-SEITEN.md:21` | Die Pipeline **verwirft keine** Zeile, sie kennzeichnet nur |
| Erkennungsfehler werden als Rechenfehler des Lernenden gewertet | Atlas-Ziel, Plaud-Beratung 22.11. | Ursache `recognition` vs. `math` ist ein Pflichtfeld |

Aus ADR-003 folgt außerdem: **Die Vision-Confidence ist bei `.accurate` durchgehend 1.00** und taugt deshalb nicht als Unsicherheitssignal. Brauchbar sind die **Top-N-Kandidaten** und die **Bounding-Box**.

## Entscheidung

**JSON ist der Datenvertrag, ein Objekt pro Seite.** LaTeX und SymPy-Ausdrücke sind Felder darin. HTML ist nur eine Ansicht, kein Austauschformat. Das LLM bekommt nicht das rohe JSON, sondern eine daraus **gerenderte** Fassung (siehe unten).

### Struktur

```json
{
  "schema_version": "0.1",
  "page": {
    "notebook": "Test1",
    "page_id": "87413696",
    "png_sha256": "…",
    "pipeline_version": "961473e",
    "engine": {"name": "apple_vision", "level": "accurate", "language_correction": false, "languages": ["de-DE"]}
  },
  "lines": [
    {
      "id": "l1",
      "order": 1,
      "bbox": [0.314, 0.073, 0.293, 0.035],
      "text": "4x+1 = 2x+5",
      "candidates": ["4x+1 = 2x+5", "4x+1=2x+5", "4x+1 = 2x+S"],
      "kind": "math",
      "image_ref": "real_corpus/lines/87413696_l1.png"
    },
    {
      "id": "l2",
      "order": 2,
      "bbox": [0.314, 0.121, 0.210, 0.033],
      "text": "2x = 4",
      "candidates": ["2x = 4", "2x=4", "2x = 9"],
      "kind": "math",
      "image_ref": "real_corpus/lines/87413696_l2.png"
    },
    {
      "id": "l3",
      "order": 3,
      "bbox": [0.314, 0.170, 0.180, 0.031],
      "text": "x = 2",
      "candidates": ["x = 2", "x=2", "x = 2."],
      "kind": "math",
      "image_ref": "real_corpus/lines/87413696_l3.png"
    }
  ],
  "steps": [
    {"id": "s1", "from_lines": ["l1"], "latex": "4x+1=2x+5", "sympy": "Eq(4*x + 1, 2*x + 5)"},
    {"id": "s2", "from_lines": ["l2"], "latex": "2x=4", "sympy": "Eq(2*x, 4)"},
    {"id": "s3", "from_lines": ["l3"], "latex": "x=2", "sympy": "Eq(x, 2)"}
  ],
  "checks": [
    {"from": "s1", "to": "s2", "status": "correct", "validator": "sympy_solveset", "cause": "recognition"},
    {"from": "s2", "to": "s3", "status": "correct", "validator": "sympy_solveset", "cause": "recognition"}
  ],
  "uncertain": [
    {"line": "l2", "cause": "recognition", "signal": "top3_disagree", "detail": "4 vs 9 in candidates"}
  ]
}
```

### Feldregeln

| Feld | Regel | Warum |
|---|---|---|
| `bbox` | normalisiert `[x, y, w, h]`, **y von oben** (Vision liefert y von unten, umrechnen) | Lesereihenfolge (ADR-004 V7, Metrik B3) |
| `order` | Reihenfolge auf der Seite, aus `bbox` abgeleitet, nicht aus der Array-Position | B3 messbar machen |
| `candidates` | Top-3 von Vision, `text` = gewählter Kandidat | Ersatz für die unbrauchbare Confidence (ADR-003) |
| `kind` | `math` \| `text` \| `annotation` | gedruckter Tutor-Text wird `annotation` und zählt nicht in die Metriken (PLAN-2026-11-23, B1b) |
| `sympy` | kanonisch nach ADR-004: `*` statt `·`/`×`, `.` statt `,` | ein Format für beide Validatoren (V3, V4) |
| `checks.status` | `correct` \| `incorrect` \| `undetermined` | deterministische Prüfung |
| `checks.cause` | `null` oder `recognition` \| `unsupported` \| `parse_error` \| `domain`; bei `undetermined` Pflicht | Erkennungsfehler ≠ Rechenfehler |
| `uncertain` | wird ergänzt, nie gefiltert; eine Zeile darin bleibt in `lines` | kein First-Line-Curse, keine stillen Verluste |

### Harte Regeln

1. **`incorrect` nur, wenn beide Schritte ohne Eintrag in `uncertain` sind.** Ist einer der beiden unsicher, wird ein negatives Ergebnis zu `undetermined` mit `cause: recognition`. Ein `correct` bleibt stehen, trägt aber `cause: recognition` als Hinweis, dass es auf einer unsicheren Lesart beruht.
2. **Was der Validator nicht kann, ist `unsupported`, nicht `incorrect`.** Das betrifft `≤`, `|`, `%` und `√` (ADR-004 V6).
3. **Eine unlesbare Zeile beendet die Kette nicht.** Der nächste prüfbare Schritt wird gegen den letzten prüfbaren geprüft, der Check bekommt `cause: recognition`.
4. **Keine Korrektur ohne Spur.** Wählt die Pipeline einen anderen Kandidaten als Top-1 (z. B. den, der `sympify` parst), bleibt `candidates` vollständig.

### Gerenderte Fassung für das Tutor-LLM

Das LLM bekommt einen kurzen Text, der aus dem JSON erzeugt wird, zum Beispiel:

```
Aufgabe (Seite 87413696):
1. 4x+1 = 2x+5
2. 2x = 4        [unsicher gelesen: "4" oder "9"]
3. x = 2
Prüfung: 1→2 richtig · 2→3 richtig
```

Ob das LLM mit dieser Fassung den Wahrheitswert richtig deutet, wird **getrennt** vom OCR-Benchmark evaluiert. Dafür gibt es synthetische Seiten-JSONs mit bekannter Wahrheit und eine Reaktion auf `undetermined`.

## Folgen

- **Die Swift-CLI muss mehr ausgeben:** `bbox` und `topCandidates(3)` pro Zeile. Das ist der additive Schritt aus PLAN-2026-11-23, Priorität 4. Das bestehende Verhalten bleibt als Default.
- **Zwei neue Stufen zwischen `ocr/post.py` und Ausgabe:** Layout (`order`, `kind`) und Struktur (`steps`, `checks`). Der Core bleibt in drei Stufen, die neuen hängen dahinter.
- **Struktur wird messbar:** B3 aus `order`, C1 aus `steps.sympy`, C2 aus `checks`. Die HPO kann damit auf Erkennung *und* Struktur optimieren statt nur auf Zeichen-Accuracy.
- **Der Tutor-Benchmark ist entkoppelt.** Er braucht nur gültige Seiten-JSONs, keine laufende OCR. Er kann deshalb parallel zur Pipeline-Arbeit entstehen.

## Nachtrag 23.11. (aus ADR-006/007/008)

- **Neues Zeilenfeld `repair`:** `null` oder `"<vorher> -> <nachher>"`, wenn die Kohärenz-Schicht ein Verwechslungspaar getauscht hat. Eine reparierte Zeile ist immer `uncertain` (ADR-007).
- **„Unsicher" ist jetzt gemessen definiert:** `uncertain` ist **reine OCR-Unsicherheit**: TexTeller und GLM-OCR SymPy-ungleich oder eine Reparatur. Ersetzt den Vorschlag `top3_disagree` (Vision-Top-N spielt für Formeln keine Rolle mehr, ADR-006).
- **`math_status` (neu, Issue #1):** `closed_truth(fixed)` als getrennte Diagnose (`True`/`False`/`None`). Eine falsche, aber übereinstimmend gelesene Gleichung ist OCR-**sicher** mit `math_status=False` — die Rechenwahrheit beeinflusst `uncertain` nicht.
- **Dezimalkomma:** `latex` enthält `0.5`, auch wenn `0,5` geschrieben wurde; in Mengen/Tupeln bleibt das Komma Trenner.
- **Teilweise implementiert und gemessen:** Zeilen-`latex`, `uncertain`, `repair`, `math_status` in `ocr/formula.py`. Seitenstruktur (`order`, `steps`, `checks`) weiter offen.
- **Multi-line Gruppen (Pass 5, umgesetzt):** `ocr/multiline.py:group_lines`/`page_structure` gruppiert Zeilen strukturell zu Rechenketten (`chain.line_indices`/`chains`, `has_uncertain_step`, `uncertain_line_indices`) — rein additiv, Zeilen unverändert, kein Domino (Issue #1). `ocr/pre.py:split_lines_with_boxes` liefert die nötigen `bbox`en, `ocr/pipeline.py:recognize_page` verdrahtet es. `checks` (Validator/Tutor) bleibt bewusst offen.

## Offen

- **Welcher Validator ist kanonisch?** `arithmetic` kennt keine Variablen, `SymPyChecker` hat den Komma-Tupel-Fehler (ADR-004). Vorschlag zur Prüfung: `sympy.solveset` für Rechenketten, wie in `SchlangebeißtinSchwanz/eval_runs/upstream-mathverify/RESULT.md:10-16` (math-verify hat dort 3 von 7 Schrittpaaren falsch beurteilt).
- **Wann ist ein Kandidat „unsicher“?** `top3_disagree` an einer Ziffer ist ein Vorschlag, aber noch ungemessen. Die Schwelle legt das Gold-Set fest, nicht diese ADR.
- **Ungleichungen:** eigener Pfad (`solveset` kann sie) oder vorerst `unsupported`?
- **Mehrzeilige Ausdrücke** (Bruch über zwei Zeilen, Nebenrechnung am Rand): `steps.from_lines` erlaubt mehrere Zeilen, aber wie man das zusammenführt, ist nicht entschieden. **Teilantwort (Pass 5):** vertikale Ableitungen werden als Ketten gruppiert (Fortsetzungssignale/Nähe/Spalte/Label); echte *zeilenübergreifende Einzelausdrücke* (Bruch über zwei Zeilen) bleiben offen.
- **`schema_version`:** Erst nach der Analyse des echten Tutors von `0.1` auf `1.0` heben.

**Hinweis:** Das Seitenschema ist weiter ein Vorschlag. Implementiert und gemessen sind nur die Zeilenfelder aus dem Nachtrag.
