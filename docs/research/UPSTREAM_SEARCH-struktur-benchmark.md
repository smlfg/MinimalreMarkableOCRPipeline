# UPSTREAM_SEARCH — Struktur-Benchmark für handschriftliche Mathe

Stand: 2026-11-23 · Status: Recherche, keine Messung. Ohne HAI-Mission, Owner-Freigabe im Chat 23.11.2026 (gilt nur für die drei Auftragsdateien + .venv_structure). Bezug: ADR-002 (Metriken), ADR-004 (Validator), ADR-005 (Ziel-Schema).
Lizenzen: PyPI-JSON bzw. GitHub-API am 2026-11-23 abgefragt. "nicht verifiziert" = keine Primärquelle gefunden.

## Teil A — Strukturmetriken für Formel-Erkennung

| Kandidat | Was | Lizenz | pip-Name | passt weil / nicht weil |
|---|---|---|---|---|
| CROHME ExpRate + Struktur/Relation-Metriken (LgEval) | Exakte Ausdrucksrate über Label-Graphen, Varianten "≤1 Fehler", Relations-P/R [1][2] | LgEval-Forks: "Other" (GitHub); Original nicht verifiziert | – (kein PyPI) | Industriestandard für HMER. Braucht SymLG/Label-Graph-Konvertierung mit CROHME-Tools, Strokes/Symbolsegmentierung nicht vorhanden (ADR-002). Konzept (Exact-Match) übernehmen, Tool nicht. |
| CDM (Character Detection Matching) | LaTeX beider Seiten rendern, Zeichen visuell + räumlich matchen [3] | Apache-2.0 (Repo UniMERNet, GitHub-API) | – (Repo, `requirements.txt`) | Repräsentationsunabhängig, CVPR 2025. Aber: braucht pdflatex (texlive), ImageMagick 7, Node 16 (README [4]) — viel Systemballast gegen "Glue only". Unabhängige Validierung: CDM r=0.34 zu Menschenurteil, LLM-Judge r=0.78 (250 Paare, 30 Rater) [5]. Als Zusatz später, nicht als Kern. |
| Tree-Edit-Distance auf Ausdrucksbaum: `zss` | Zhang-Shasha-Algorithmus [6] | PyPI-Feld leer, GitHub: NOASSERTION (nicht verifiziert) | `zss` | Klein, reines Python. Lizenz unklar -> Risiko. |
| Tree-Edit-Distance: `apted` | APTED (Pawlik/Augsten), schnellste bekannte Variante [7] | MIT | `apted` | Gleiche Funktion, klare Lizenz. **Gewählt** für tree_sim. |
| SymPy-Äquivalenz (`simplify(a-b)==0`, `srepr`) | Semantische Gleichheit zweier geparster Ausdrücke [8] | BSD | `sympy` | Beantwortet genau die Tutor-Frage "mathematisch dasselbe?" (`17·3` = `17x3`). Parse-Fehler -> `None`. Heuristisch: `simplify`==0 ist nur hinreichend, nicht notwendig (Unentscheidbarkeit allgemein). |
| LaTeX -> SymPy Parser: `latex2sympy2_extended` | ANTLR-Parser, von Math-Verify genutzt [9][10] | MIT | `latex2sympy2_extended` (+ `antlr4-python3-runtime==4.13.2`) | Aktiv gepflegt (1.11.0). Das ältere `latex2sympy2` (1.9.1, MIT) pinnt alte ANTLR-Runtime; nicht gewählt. |
| Math-Verify (HF) | Extraktion + Parsing + Vergleich von LLM-Antworten gegen Gold [9] | Apache-2.0 | `math-verify` | Gut für Endantwort-Grading. Erwartet LaTeX in Math-Umgebung (`$..$`, `\boxed`); unsymmetrisch bei Ungleichung/Intervall und Zahl/Lösungskette [9]. Zu viel Extraktionslogik für Formel-zu-Formel; ADR-005 nennt zudem 3/7 falsch beurteilte Schrittpaare. Nur als Fallback. |
| Edit-Distanz / BLEU auf normalisiertem LaTeX: `rapidfuzz`, `sacrebleu` | Zeichen-/Token-Ähnlichkeit [11][12] | MIT / Apache-2.0 | `rapidfuzz`, `sacrebleu` | Gleiches Problem wie heute (Zeichen-Treffer ≠ Struktur) [3]; bleibt als billiger Zusatz (`latex_edit_sim`). `rapidfuzz` gewählt, BLEU nicht. |

### Empfehlung A
- **Hauptmetrik: `sympy_equal`-Rate** (Anteil Formeln, die nach Parsing symbolisch gleich der GT sind; Parse-Fehler zählt als falsch). Begründung: entspricht ExpRate (Anteil exakt richtig) [1], aber repräsentationsunabhängig, und misst genau, was der Tutor braucht (stimmt die Rechnung).
- **Begleitmetrik (gestuft): `tree_sim`** = 1 − APTED/max(|T1|,|T2|) auf dem SymPy-Baum (Selbsttest: Summanden-Umordnung gibt tree_sim 0.25 bei sympy_equal=True — der Baum ist nicht kanonisch, daher nur Begleitmetrik; Normierung mit |T1|+|T2| war zu milde, flacher Bruch bekam 0.54); gibt Teilpunkte, wenn Struktur halb stimmt (CROHME-Idee der Relations-/Struktur-Metriken, ohne Strokes [2]).
- Zusatz: `exact` (normalisierter String, ExpRate-Analogon), `latex_edit_sim` (Kontinuität zur alten Accuracy), `parse_ok` (Diagnose: Rate unparsebarer Vorhersagen).
- Nicht jetzt: CDM (Systemballast, schwache Menschkorrelation in [5]); ggf. später als Gegenprobe auf kleiner Stichprobe.
- Grenze: SymPy-Parsing von OCR-Müll scheitert oft -> `sympy_equal=None`; deshalb sind `tree_sim`/`latex_edit_sim` nötig, und beide werden in der Tabelle getrennt von der Hauptmetrik ausgewiesen.

## Teil B — Wie füttert man LLMs mit Mathe?

Vorab ehrlich: **Direkter Vergleich LaTeX vs. MathML vs. SymPy vs. Klartext als LLM-Input fand ich in Primärquellen nicht** (Suche nach arXiv-Papern ergab nur indirekte Hinweise [13]). Die Empfehlung ist daher eine Schlussfolgerung, keine gemessene Tatsache; sie gehört in den getrennten Tutor-Eval aus ADR-005.

| Kandidat | Was | Lizenz/Zugang | passt weil / nicht weil |
|---|---|---|---|
| MATH (Hendrycks et al.) | 12 500 Wettbewerbsaufgaben, je mit Schritt-für-Schritt-Lösung [14] | Dataset (GitHub) | Standardbenchmark für Lösungswege; Notationsformat im Abstract nicht angegeben, nicht verifiziert. |
| GSM8K + Verifier (Cobbe et al.) | 8,5k Textaufgaben; trainierter Verifier wählt beste Kandidatenlösung [15] | arXiv/Dataset | Belegt: separate Prüfinstanz hebt Genauigkeit [15]. |
| Let's Verify Step by Step (PRM800K) | Prozess- schlägt Ergebnis-Supervision auf MATH, 78 % auf Teilmenge, 800k Schrittlabels [16] | Dataset PRM800K | Belegt Wert der Schritt-für-Schritt-Prüfung, passt zu ADR-005 `checks` pro Schritt. |
| PAL | LLM schreibt Programm, Interpreter rechnet; GSM8K SOTA, +15 % abs. vs. PaLM-540B CoT [17] | arXiv | Beleg: Auslagern der Rechnung an Tool schlägt reine Textrechnung. |
| ToRA | Tool-integriertes Schließen (CAS/Bibliotheken); ToRA-7B 44,6 % MATH, Code-34B >50 % [18] | arXiv | Symbolische Tools im Loop helfen auch auf MATH. |
| CRITIC | Tool-Feedback für Selbstkorrektur [19] | arXiv | Externe Prüfung hilft... |
| Huang et al. "cannot self-correct yet" | Ohne externes Feedback verschlechtert Selbstkorrektur teils [20] | arXiv | ...und das ist das Gegenstück: Validator-Ergebnis muss **extern** kommen, nicht vom LLM. |
| GSM-Symbolic | Leistung fällt bei geänderten Zahlen und irrelevanten Zusatzsätzen (bis −65 %) [21] | arXiv | Warnung: Zusatztext im Prompt kann schaden -> Prüfblock knapp und strikt halten. |

### Empfehlung B (Format des gerenderten LLM-Inputs aus ADR-005)
1. **Zeilenweise nummerierte Schritte als LaTeX (in `$...$`), plus die SymPy-Kanonform in einer zweiten Spalte** nur dort, wo `parse_ok`; kein MathML (verbose, keine Evidenz für Vorteil; LaTeX ist für Modelle gut tokenisierbar [13]).
2. **Prüfung als kurze, maschinelle Zeile pro Schritt** (`1→2: correct | incorrect | undetermined`), vom Validator, nicht vom LLM [19][20]; `undetermined` und Unsicherheit der OCR ("4 oder 9") explizit lassen, nie zu richtig/falsch glätten.
3. **Kein Klartext-Flattening** (`cos(x)-1 x^2` zerstört den Bruch, vgl. Auftrag); Wirkung des Prüfblocks am eigenen Gold-Set A/B-testen (mit/ohne Validator, LaTeX-only vs. LaTeX+SymPy), da die Quellen sie nur indirekt stützen.

## Pakete für Teil 2 (venv `.venv_structure`, Python 3.12, nicht global)

| pip-Name | Zweck |
|---|---|
| `sympy` | Äquivalenzprüfung, Ausdrucksbaum |
| `latex2sympy2_extended` | LaTeX -> SymPy-Parser |
| `antlr4-python3-runtime==4.13.2` | Laufzeit des Parsers |
| `apted` | Tree-Edit-Distance (MIT) |
| `rapidfuzz` | Levenshtein-Ähnlichkeit auf LaTeX |
| `pillow` | PNGs der synthetischen Beispiele |

## Quellen
[1] ICDAR 2023 CROHME (Zenodo, ExpRate/LgEval): https://zenodo.org/records/8428035
[2] ADR-002 dieses Repos (CROHME-Metrikfamilien)
[3] CDM, arXiv 2409.03643 (CVPR 2025): https://arxiv.org/abs/2409.03643
[4] UniMERNet/cdm README: https://github.com/opendatalab/UniMERNet/tree/main/cdm
[5] Horn & Keuper, arXiv 2512.09874: https://arxiv.org/abs/2512.09874
[6] zss: https://pypi.org/project/zss/ · https://github.com/timtadh/zhang-shasha
[7] apted: https://pypi.org/project/apted/
[8] SymPy: https://pypi.org/project/sympy/
[9] Math-Verify: https://github.com/huggingface/Math-Verify
[10] latex2sympy2_extended: https://pypi.org/project/latex2sympy2-extended/
[11] rapidfuzz: https://pypi.org/project/rapidfuzz/
[12] sacrebleu: https://pypi.org/project/sacrebleu/
[13] Websuche "LaTeX vs MathML LLM": u. a. https://arxiv.org/html/2512.09874v1 (nur indirekte Hinweise)
[14] MATH, arXiv 2103.03874: https://arxiv.org/abs/2103.03874
[15] GSM8K/Verifier, arXiv 2110.14168: https://arxiv.org/abs/2110.14168
[16] PRM800K, arXiv 2305.20050: https://arxiv.org/abs/2305.20050
[17] PAL, arXiv 2211.10435: https://arxiv.org/abs/2211.10435
[18] ToRA, arXiv 2309.17452: https://arxiv.org/abs/2309.17452
[19] CRITIC, arXiv 2305.11738: https://arxiv.org/abs/2305.11738
[20] Huang et al., arXiv 2310.01798: https://arxiv.org/abs/2310.01798
[21] GSM-Symbolic, arXiv 2410.05229: https://arxiv.org/abs/2410.05229

## Eigene Logik in `bench/structure_bench.py` — Begründung und Ersatzpfad (Owner-Präzisierung 23.11.2026)

Stand: Die Datei enthält ca. 100 Zeilen eigenen Glue plus eigene Metrik-Logik. Sie wird **nicht erweitert**. Ungetestet ist alles Folgende; es sind Ersatzkandidaten, keine geprüften Behauptungen.

| Eigene Logik | Warum entstanden | Möglicher fertiger Ersatz |
|---|---|---|
| `normalize()` (Regex für `\cdot`, `\dfrac`, Leerzeichen) | Für `exact` | Normalisierung der Eval-Skripte von UniMERNet/pix2tex (Inhalt nicht geprüft) |
| `parse` + `_eq` (SymPy-Äquivalenz, Eq-Vergleich) | `sympy_equal` | `math-verify` (`parse`/`verify`, Apache-2.0 [9]); Einschränkungen: LaTeX muss in Math-Umgebung stehen, nicht symmetrisch bei Ungleichung/Intervall; Formel-zu-Formel-Eignung ungeprüft |
| `_tree` + APTED-Aufruf (`tree_sim`) | Kein fertiges Tool gefunden, das SymPy-Ausdrucksbäume vergleicht; `apted` liefert nur die Distanz. Begründung für Eigenlogik, aber nur ca. 10 Zeilen | CROHME/LgEval-Relationsmetriken (Label-Graph, braucht SymLG-Konvertierung) |
| `latex_edit_sim` | rapidfuzz-Aufruf | bereits Bibliothek |
| Gesamt-Hauptmetrik | — | CDM (`opendatalab/UniMERNet/cdm`, Eingabe-JSON mit `gt`/`pred`/`img_id`, [4]): Adapter von manifest/pred.jsonl wäre trivial, aber Laufzeit braucht texlive, ImageMagick 7, Node 16 — nicht installiert, nicht getestet |

Nächster Schritt falls gewünscht: dünner Adapter auf `cdm/evaluation.py` (und/oder `math-verify`) statt Ausbau von `structure_bench.py`; vorher Systemabhängigkeiten von CDM mit dem Owner klären.

## Teil C — End-to-End: Findet der Tutor den richtigen Schritt? (Nachtrag 23.11.2026)

Lücke aus Teil B geschlossen (Recherche-Agent, nur Primärquellen-Lesestand; nichts lokal getestet).

| Benchmark | Metrik | Größe / Niveau | Lizenz | Eval-Skript |
|---|---|---|---|---|
| **ProcessBench** (arXiv 2412.06559, QwenLM/ProcessBench) | frühester Fehlerschritt oder „alles korrekt“; **F1 aus Accuracy auf fehlerhaften und korrekten Fällen** (bestraft falschen Alarm) | 3,4k; GSM8K-Split 400 schulnah | Apache-2.0 | ja (`code/`) |
| MR-GSM8K (arXiv 2312.17080) | MR-Score: MCC + erster Fehlerschritt + Fehlergrund (LLM-Judge) | 3000, Mittelstufe | MIT | ja |
| Verify-then-Generate (arXiv 2407.09136) | Schritt-Verifikation F1; Feedback „zielgenau, korrekt, umsetzbar“ | 1002 echte Schülerlösungen (MathDial) | Daten CC BY 4.0 (angekündigt) | Repo, ungeprüft |
| **FERMAT** (arXiv 2501.07244) | Erkennen/Lokalisieren/Korrigieren auf **handschriftlichen** Lösungen | 2244, Klassen 7–12 | Code MIT, Daten unklar | Repo |
| MathTutorBench, MathCheck, ErrorRadar, Bridge, MathDial | Tutoring-/Prozess-Aufgaben | englisch | teils unklar/widersprüchlich | teils |

Belegte Befunde, die unsere Architektur stützen:
- **FERMAT:** OCR-dann-LLM lokalisiert Fehler besser als Bild direkt (z. B. Llama-3.2-90B 0,18 → 0,41). Stützt ADR-006/005 (Text-Fassung statt Bild an das LLM).
- **Yu et al. (arXiv 2603.00895, nur Snippet):** OCR hat **Schülerfehler stillschweigend korrigiert**. Genau das Risiko aus ADR-007 („nie still korrigieren“).
- **Kein** Benchmark misst systematisch OCR-Unsicherheit gegen Fehlerlokalisierung; **kein** deutscher Datensatz mit Schülerfehlern gefunden.

Folgerung für uns: **Zielmetrik der ganzen Kette = ProcessBench-F1** (frühester Fehlerschritt bzw. „korrekt“, auf fehlerhaften *und* korrekten Ketten), ergänzt um Nachfrage-Rate bei `uncertain`. Datenform (Schrittliste + erster Fehlerschritt) passt 1:1 auf ADR-005 `steps`/`checks`. Die fehlenden Teile (Deutsch, eigene Handschrift, OCR-Unsicherheit) liefert ein eigenes Ketten-Kalibrierungsblatt mit eingebauten Fehlern; das ProcessBench-Format wird dafür übernommen statt erfunden.
