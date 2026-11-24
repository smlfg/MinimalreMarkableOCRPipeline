## Batch 1 (22:17) — kette L1, 50 Einheiten, 0.5 min, glm=an
{"batch": 1, "level": "L1", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 2 (22:18) — kette L1, 50 Einheiten, 0.5 min, glm=an
{"batch": 2, "level": "L1", "art": "kette", "n": 50, "F1_strict": 0.9836065573770492, "coverage": 0.98}
  daneben: {'id': 'C078', 'label': -1, 'pred': 'ask', 'stage': '③ OCR', 'read': ['3x+7=31', '3x=24', 'x=8']}
## Batch 3 (22:18) — kette L1, 50 Einheiten, 0.5 min, glm=an
{"batch": 3, "level": "L1", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 4 (22:19) — kette L1, 50 Einheiten, 0.5 min, glm=an
{"batch": 4, "level": "L1", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 5 (22:20) — kette L2, 50 Einheiten, 0.6 min, glm=an
{"batch": 5, "level": "L2", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 6 (22:20) — kette L2, 50 Einheiten, 0.6 min, glm=an
{"batch": 6, "level": "L2", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 7 (22:21) — kette L2, 50 Einheiten, 0.6 min, glm=an
{"batch": 7, "level": "L2", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 8 (22:22) — kette L2, 50 Einheiten, 0.6 min, glm=an
{"batch": 8, "level": "L2", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 9 (22:23) — kette L3, 50 Einheiten, 0.7 min, glm=an
{"batch": 9, "level": "L3", "art": "kette", "n": 50, "F1_strict": 0.962962962962963, "coverage": 1.0}
  daneben: {'id': 'C434', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['x^{2}-11x+30=0', '(x-11/2)^{2}=114', '(x-5)(x-6)=0']}
  daneben: {'id': 'C436', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['x^{2}-8x+15=0', '(x-8/2)^{2}=414', '(x-3)(x-5)=0']}
## Batch 10 (22:24) — kette L3, 50 Einheiten, 0.7 min, glm=an
{"batch": 10, "level": "L3", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## 2026-11-23 22:25 — Verzahnung aktiv (Owner-Freigabe "sofort verzahnen", Vertrag v2 per TouchID)
- Baseline Batches 1-9 (Pipeline unveraendert): L1 1.000/0.984/1.000/1.000, L2 4x 1.000, L3 0.963 (Batch 9 komplett, Batch 10 beim Abbruch noch nicht begonnen).
- H1 gelandet (Synth-Stellschraube, kein Pipeline-Code): Sigma-Glyph v2 (groesser, schaerfer) via `gen_campaign.py 314 v2`; nur die 40 Summen-Zeilen rendern anders, alle Ketten byte-identisch. A/B: v1-Messung aus v2-hard (struct 0.00, 40 Zeilen) steht als Referenz.
- Messung läuft ab Batch 10 weiter; L5/L6-Befunde werden zu Pipeline-Hypothesen (je Fund eine, keep/discard, Holdout frischer Batch, reales Blatt 28/28 als Gate).
## Batch 10 (22:24) — kette L3, 50 Einheiten, 0.2 min, glm=an
{"batch": 10, "level": "L3", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 11 (22:26) — kette L3, 50 Einheiten, 0.7 min, glm=an
{"batch": 11, "level": "L3", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## 2026-11-23 22:27 — Owner: "thorsten stoppen"
Sprachausgabe deaktiviert (MUTE-Datei als Schalter, speak() prueft sie). Messung laeuft stumm ab Batch 12 weiter; Batch-10-Doppelzeile in RESULTS.tsv entfernt. Batches 10/11: L3 je F1 1.000.
## Batch 12 (22:27) — kette L4, 50 Einheiten, 0.5 min, glm=an
{"batch": 12, "level": "L4", "art": "kette", "n": 50, "F1_strict": 0.9454545454545454, "coverage": 1.0}
  daneben: {'id': 'C573', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['14\\cdot7', '=7.10+7.4', '=70+28', '=98']}
  daneben: {'id': 'C588', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['11\\cdot5', '=5.10+5.1', '=50+5', '=55']}
  daneben: {'id': 'C598', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['15\\cdot4', '=4.10+4.5', '=40+20', '=60']}
## Batch 13 (22:27) — kette L4, 50 Einheiten, 0.6 min, glm=an
{"batch": 13, "level": "L4", "art": "kette", "n": 50, "F1_strict": 0.8483033932135728, "coverage": 1.0}
  daneben: {'id': 'C618', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['12\\cdot8', '=8.10+8.2', '=80+16', '=96']}
  daneben: {'id': 'C620', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['\\frac{1}{6}\\cdot\\frac{4}{2}', '=4112', '=1/3']}
  daneben: {'id': 'C628', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['17\\cdot7', '=7.10+7.7', '=70+49', '=119']}
  daneben: {'id': 'C633', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['15\\cdot7', '=7.10+7.5', '=70+35', '=105']}
  daneben: {'id': 'C638', 'label': -1, 'pred': 1, 'stage': '③ OCR', 'read': ['11\\cdot9', '=9.10+9.1', '=90+9', '=99']}
  daneben: {'id': 'C639', 'label': -1, 'pred': 2, 'stage': '③ OCR', 'read': ['\\frac{4}{2}+\\frac{5}{3}', '=12/6+10/6', '=2216', '=11/3']}
  daneben: {'id': 'C645', 'label': 2, 'pred': 1, 'stage': '③ OCR', 'read': ['\\frac{4}{6}\\cdot\\frac{1}{2}', '=41.12', '=2/3']}
  daneben: {'id': 'C648', 'label': 3, 'pred': 1, 'stage': '③ OCR', 'read': ['13\\cdot6', '=6.10+6.3', '=60+18', '=80']}
## Batch 14 (22:28) — kette L4, 50 Einheiten, 0.6 min, glm=an
{"batch": 14, "level": "L4", "art": "kette", "n": 50, "F1_strict": 1.0, "coverage": 1.0}
## Batch 15 (22:29) — formel L5, 50 Einheiten, 0.7 min, glm=an
{"batch": 15, "level": "L5", "art": "formel", "n": 50, "struct": 0.72, "char": 0.7391300428217263, "coverage": 0.72, "prec_certain": 0.9722222222222222}
  daneben: {'id': 'H027', 'topic': 'integral', 'pred': '\\int(5x+6)dx=5/2 \\cdot x^{2}+6x+6'}
  daneben: {'id': 'H029', 'topic': 'integral', 'pred': '\\int(5x+5)dx=5/2 \\cdot x^{2}+5x+6'}
  daneben: {'id': 'H030', 'topic': 'integral', 'pred': 'f(3x+3)dx=3/2 \\cdot x^{2}+3x+C'}
  daneben: {'id': 'H031', 'topic': 'integral', 'pred': 'f(2x+3)dx=2/2 \\cdot x^{2}+3x+C'}
  daneben: {'id': 'H036', 'topic': 'integral', 'pred': '\\int(2x+5)dx=2/2x^{2}+5x+c'}
  daneben: {'id': 'H039', 'topic': 'integral', 'pred': '\\int o^{4}xdx=8'}
  daneben: {'id': 'H041', 'topic': 'integral', 'pred': '\\int 2^{6}xdx=16'}
  daneben: {'id': 'H042', 'topic': 'integral', 'pred': '\\int 2^{8} \\times dx=30'}
## Batch 16 (22:29) — formel L5, 50 Einheiten, 0.7 min, glm=an
{"batch": 16, "level": "L5", "art": "formel", "n": 50, "struct": 0.2, "char": 0.6550079849012777, "coverage": 0.2, "prec_certain": 1.0}
  daneben: {'id': 'H051', 'topic': 'summe', 'pred': '3_{k=1}^{n}k=n(n+1)/2'}
  daneben: {'id': 'H052', 'topic': 'summe', 'pred': '3_{k=1}^{n}k=n(n+1)/2'}
  daneben: {'id': 'H053', 'topic': 'summe', 'pred': '3_{k=1}^{n}k=n(n+1)/2'}
  daneben: {'id': 'H054', 'topic': 'summe', 'pred': '3 \\times 2^{n}k=n(n+1)/2'}
  daneben: {'id': 'H055', 'topic': 'summe', 'pred': '3^{n}_{k=1}k=n(n+1)/2'}
  daneben: {'id': 'H056', 'topic': 'summe', 'pred': 's_{k=1}^{n}k=n(n+1)/2'}
  daneben: {'id': 'H057', 'topic': 'summe', 'pred': 'S_{k=1}^{n}k=n(n+1)/2'}
  daneben: {'id': 'H058', 'topic': 'summe', 'pred': '3_{k=1}^{n}k=n(n+1)/2'}
## Batch 17 (22:30) — formel L5, 50 Einheiten, 0.5 min, glm=an
{"batch": 17, "level": "L5", "art": "formel", "n": 50, "struct": 0.8, "char": 0.7423518776150355, "coverage": 0.78, "prec_certain": 1.0}
  daneben: {'id': 'H111', 'topic': 'algebra', 'pred': '0^{m} \\cdot 0^{n}=0^{m+n}'}
  daneben: {'id': 'H112', 'topic': 'algebra', 'pred': '0^{m} \\cdot 0^{n}=0^{m+n}'}
  daneben: {'id': 'H119', 'topic': 'wurzel', 'pred': '12.58=4'}
  daneben: {'id': 'H120', 'topic': 'wurzel', 'pred': 'r_{6} \\sqrt{24}=12'}
  daneben: {'id': 'H121', 'topic': 'wurzel', 'pred': 'r2 \\cdot \\sqrt{8}=4'}
  daneben: {'id': 'H122', 'topic': 'wurzel', 'pred': 'r(ab)=ra \\cdot rb'}
  daneben: {'id': 'H123', 'topic': 'wurzel', 'pred': 'r(ab)=ra \\cdot rb'}
  daneben: {'id': 'H124', 'topic': 'wurzel', 'pred': 'r(ab)=ra \\cdot rb'}
## Batch 18 (22:32) — formel L6, 50 Einheiten, 1.6 min, glm=an
{"batch": 18, "level": "L6", "art": "formel", "n": 50, "struct": 0.06, "char": 0.6349441164955482, "coverage": 0.0, "prec_certain": 0.0}
  daneben: {'id': 'H151', 'topic': 'matrix_mm', 'pred': '(\n\\begin{matrix}\n44\\\\\n59\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n40 \\\\\n21\n\\end{matrix}\n)=(\n\\begin{matrix}\n244 \\\\\n389\n\\end{matrix}\n)'}
  daneben: {'id': 'H152', 'topic': 'matrix_mm', 'pred': '(\n\\begin{matrix}\n6&9 \\\\\n4&5\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n84 \\\\\n32\n\\end{matrix}\n)=(\n\\begin{matrix}\n75&42 \\\\\n4&26\n\\end{matrix}\n)'}
  daneben: {'id': 'H153', 'topic': 'matrix_mm', 'pred': '\\left(\n\\begin{matrix}\n91 \\\\\n91\n\\end{matrix}\n\\right) \\cdot \\left(\n\\begin{matrix}\n11 \\\\\n09\n\\end{matrix}\n\\right)= \\left(\n\\begin{matrix}\n918 \\\\\n918\n\\end{matrix}\n\\right)'}
  daneben: {'id': 'H154', 'topic': 'matrix_mm', 'pred': '(\n\\begin{matrix}\n82\\\\\n32\n\\end{matrix}\n)(\n\\begin{matrix}\n98\\\\\n20\n\\end{matrix}\n)=(\n\\begin{matrix}\n76&64\\\\\n31&24\n\\end{matrix}\n)'}
  daneben: {'id': 'H155', 'topic': 'matrix_mm', 'pred': '( \\frac{55}{27}) \\cdot( \\frac{90}{30})=( \\frac{600}{390})'}
  daneben: {'id': 'H156', 'topic': 'matrix_mm', 'pred': '( \\frac{33}{35}) \\cdot( \\frac{44}{48})=( \\frac{24}{32} \\frac{36}{52})'}
  daneben: {'id': 'H157', 'topic': 'matrix_mm', 'pred': '(\n\\begin{matrix}\n92\\\\\n57\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n95 \\\\\n21\n\\end{matrix}\n)=(\n\\begin{matrix}\n8547 \\\\\n5932\n\\end{matrix}\n)'}
  daneben: {'id': 'H159', 'topic': 'matrix_mm', 'pred': '(\n\\begin{matrix}\n29 \\\\\n18\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n0&8 \\\\\n5&1\n\\end{matrix}\n)=(\n\\begin{matrix}\n45&25 \\\\\n40&16\n\\end{matrix}\n)'}
## Batch 19 (22:33) — formel L6, 50 Einheiten, 1.1 min, glm=an
{"batch": 19, "level": "L6", "art": "formel", "n": 50, "struct": 0.14, "char": 0.6253581907670892, "coverage": 0.0, "prec_certain": 0.0}
  daneben: {'id': 'H202', 'topic': 'matrix_mv', 'pred': '( \\frac{13}{35}) \\cdot( \\frac{3}{8})=( \\frac{27}{49})'}
  daneben: {'id': 'H203', 'topic': 'matrix_mv', 'pred': '( \\frac{84}{76}) \\cdot( \\frac{4}{5})=( \\frac{52}{58})'}
  daneben: {'id': 'H204', 'topic': 'matrix_mv', 'pred': '(\n\\begin{matrix}\n84\\\\\n31\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n13\n\\end{matrix}\n)=(\n\\begin{matrix}\n20 \\\\\n6\n\\end{matrix}\n)'}
  daneben: {'id': 'H206', 'topic': 'matrix_mv', 'pred': '(\n\\begin{matrix}\n95 \\\\\n29\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n3 \\\\\n2\n\\end{matrix}\n)=(\n\\begin{matrix}\n37 \\\\\n24\n\\end{matrix}\n)'}
  daneben: {'id': 'H207', 'topic': 'matrix_mv', 'pred': '(\n\\begin{matrix}\n87\\\\\n93\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n31 \\\\\n1\n\\end{matrix}\n)=(\n\\begin{matrix}\n31 \\\\\n30\n\\end{matrix}\n)'}
  daneben: {'id': 'H208', 'topic': 'matrix_mv', 'pred': '( \\frac{85}{87}) \\cdot( \\frac{4}{9})=( \\frac{77}{95})'}
  daneben: {'id': 'H209', 'topic': 'matrix_mv', 'pred': '(\n\\begin{matrix}\n12 \\\\\n48\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n3 \\\\\n1\n\\end{matrix}\n)=(\n\\begin{matrix}\n5 \\\\\n20\n\\end{matrix}\n)'}
  daneben: {'id': 'H210', 'topic': 'matrix_mv', 'pred': '( \\frac{39}{52}) \\cdot( \\frac{7}{9})=( \\frac{102}{53})'}
## Batch 20 (22:34) — formel L6, 50 Einheiten, 1.3 min, glm=an
{"batch": 20, "level": "L6", "art": "formel", "n": 50, "struct": 0.14, "char": 0.5197253565857247, "coverage": 0.0, "prec_certain": 0.0}
  daneben: {'id': 'H251', 'topic': 'matrix_sm', 'pred': '9 \\cdot( \\frac{21}{43})=( \\frac{18}{36} \\frac{9}{27})'}
  daneben: {'id': 'H252', 'topic': 'matrix_sm', 'pred': '5 \\cdot( \\frac{33}{12})=( \\frac{15}{5} \\frac{15}{10})'}
  daneben: {'id': 'H253', 'topic': 'matrix_sm', 'pred': '9 \\cdot( \\frac{24}{97})=( \\frac{1836}{8163})'}
  daneben: {'id': 'H256', 'topic': 'matrix_sm', 'pred': '5 \\cdot( \\frac{95}{85})=( \\frac{4525}{4025})'}
  daneben: {'id': 'H257', 'topic': 'matrix_sm', 'pred': '7 \\cdot( \\frac{7}{94})=( \\frac{49}{63} \\frac{21}{28})'}
  daneben: {'id': 'H258', 'topic': 'matrix_sm', 'pred': '9 \\cdot( \\frac{42}{52})=( \\frac{36}{45} \\frac{18}{18})'}
  daneben: {'id': 'H260', 'topic': 'matrix_sm', 'pred': '4 \\cdot(\n\\begin{matrix}\n48 \\\\\n46\n\\end{matrix}\n)=(\n\\begin{matrix}\n1632 \\\\\n1624\n\\end{matrix}\n)'}
  daneben: {'id': 'H261', 'topic': 'matrix_sm', 'pred': '4 \\cdot( \\frac{92}{62})=( \\frac{368}{248})'}
## Batch 21 (22:34) — formel L6, 15 Einheiten, 0.6 min, glm=an
{"batch": 21, "level": "L6", "art": "formel", "n": 15, "struct": 0.06666666666666667, "char": 0.5470760233918129, "coverage": 0.0, "prec_certain": 0.0}
  daneben: {'id': 'H301', 'topic': 'matrix_2step', 'pred': '(\n\\begin{matrix}\n42&48 \\\\\n56&47\n\\end{matrix}\n).(\n\\begin{matrix}\n5 \\\\\n2\n\\end{matrix}\n)=(\n\\begin{matrix}\n306 \\\\\n374\n\\end{matrix}\n)'}
  daneben: {'id': 'H302', 'topic': 'matrix_2step', 'pred': '(\n\\begin{matrix}\n48 \\\\\n75\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n81 \\\\\n43\n\\end{matrix}\n)=(\n\\begin{matrix}\n64&28 \\\\\n76&22\n\\end{matrix}\n)'}
  daneben: {'id': 'H303', 'topic': 'matrix_2step', 'pred': '(\n\\begin{matrix}\n6428 \\\\\n7622\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n4 \\\\\n5\n\\end{matrix}\n)=(\n\\begin{matrix}\n396 \\\\\n414\n\\end{matrix}\n)'}
  daneben: {'id': 'H304', 'topic': 'matrix_2step', 'pred': '(\n\\begin{matrix}\n93\\\\\n96\n\\end{matrix}\n) \\cdot(\n\\begin{matrix}\n52\\\\\n98\n\\end{matrix}\n)=(\n\\begin{matrix}\n72&42 \\\\\n99&66\n\\end{matrix}\n)'}
  daneben: {'id': 'H305', 'topic': 'matrix_2step', 'pred': '\\left(\n\\begin{matrix}\n72&42 \\\\\n99&66\n\\end{matrix}\n\\right) \\cdot \\left(\n\\begin{matrix}\n1 \\\\\n4\n\\end{matrix}\n\\right)= \\left(\n\\begin{matrix}\n2&40 \\\\\n3&63\n\\end{matrix}\n\\right)'}
  daneben: {'id': 'H306', 'topic': 'matrix_2step', 'pred': '( \\frac{38}{98}) \\cdot( \\frac{51}{57})=( \\frac{55}{8}, \\frac{59}{665})'}
  daneben: {'id': 'H307', 'topic': 'matrix_2step', 'pred': '( \\frac{5559}{8565}) \\cdot( \\frac{4}{8})=( \\frac{692}{860})'}
  daneben: {'id': 'H308', 'topic': 'matrix_2step', 'pred': '( \\frac{3}{2} \\frac{3}{5}) \\cdot( \\frac{4}{6} \\frac{3}{1})=( \\frac{30}{38} \\frac{12}{11})'}
## Kampagne komplett — 2026-11-23 22:34
## Kampagne komplett — 2026-11-23 22:35 (21/21 Batches)

**Ketten (chain-F1, in bench/results_chain.tsv):**

- L1: n=200, F1_strict=0.995, coverage=0.99, ask_rate=0.01
- L2: n=200, F1_strict=1.000, coverage=1.00, ask_rate=0.00
- L3: n=150, F1_strict=0.987, coverage=1.00, ask_rate=0.00
- L4: n=150, F1_strict=0.930, coverage=1.00, ask_rate=0.00

**Formeln (struct je Thema, unsicher-Anteil):**

- algebra: n=25, struct=0.920, unsicher=0.12
- bruch: n=10, struct=1.000, unsicher=0.00
- integral: n=50, struct=0.720, unsicher=0.28
- matrix_2step: n=30, struct=0.133, unsicher=1.00
- matrix_mm: n=50, struct=0.060, unsicher=1.00
- matrix_mv: n=40, struct=0.150, unsicher=1.00
- matrix_pow: n=15, struct=0.067, unsicher=1.00
- matrix_sm: n=30, struct=0.133, unsicher=1.00
- pi: n=10, struct=1.000, unsicher=0.00
- summe: n=40, struct=0.000, unsicher=1.00
- wurzel: n=15, struct=0.467, unsicher=0.53

Fazit: L1-L4 robust (0.85-1.00). L5 haengt am Schriftsimulator (Sigma-Glyph) und
Integrationskonstante C, nicht am Rechnen. L6 Matrizen: Capability-Grenze von
TexTeller — die Pipeline behauptet nichts Falsches (Coverage 0, alles unsicher
markiert), sondern verweigert ehrlich. Naechste Hypothesen stehen im Logbuch.


## 2026-11-23 22:35 — Owner-Entscheidung fuer morgen: Methode festgezurrt (Chat)

- Synthetische Blaetter = Tuning/Dev: schnell (1000 Ketten in ~10 s statt handgeschriebene Blaetter je Reglerdreh); je Aenderung schneller Check auf frischem Batch.
- Echte Kalibrierungsblaetter = eingefrorenes Gate, nur final, nie Tuning-Material. Gepinnt: Kalibrierung-Ketten.pdf sha256 079caef44ec74789b8f8740559f1d3f74baf047c85323e76840add014082bf78; last_real.jsonl sha256 36f37de4aace332daefe742977925be3cded1ac6265ccf9125b1b79b1daf4651.
- Begruendung: L1 F1 0.996 auf Synthetik vs. 90 % Struktur auf echter Hand — die Differenz ist die Realismusluecke, sie misst nur das echte Blatt.
- Parallel festgehalten im HAI-Logbuch (2026-11-23, Eintrag „Kalibrierungsmethode: synthetisch tunen, real validieren").
