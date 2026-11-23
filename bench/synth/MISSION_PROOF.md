# Missions-Belege M-20261123T213828-83726581 (dc4)

**dc4 — Validator und Tutor unangetastet; `ocr/formula.py`, `ocr/coherence.py`, `kalib_eval.py` unverändert geblieben.**

- Die vier Pipeline-Änderungen (Bandöffnung `kalib_eval.py`, Artefakt-Abgleich +
  korroborierte Reparatur `ocr/coherence.py`, Vertrauenslogik + Zweitmeinung
  `ocr/formula.py`, Ketten-Arbitrierung `bench/chain_bench.py`) stammen vom Owner
  und wurden von ihm selbst committet: `ee1fa9d` (21:45:25) und `0087e8d` (21:45:56).
- Diese Session hat danach keine dieser Dateien angefasst:
  `git diff ee1fa9d..HEAD -- ocr/formula.py ocr/coherence.py bench/formula_flywheel/kalib_eval.py`
  ist leer; `urgent-Math-help/` liegt außerhalb des Repos und wurde nicht betreten.
- Einzige eigene Änderung an Produktivcode dieser Session: `--synth` in
  `bench/chain_bench.py` (Suffix, Defaults byte-identisch; geriet versehentlich in
  den Owner-Commit `ee1fa9d`).
- Schreibpfad der Session laut Contract: `bench/synth/**`,
  `bench/chain_bench.py`, `bench/results_chain.tsv` — eingehalten.

Beleg-Kommandos:
```
git show --stat ee1fa9d
git diff ee1fa9d..HEAD -- ocr/formula.py ocr/coherence.py bench/formula_flywheel/kalib_eval.py
grep -c synth bench/chain_bench.py   # --synth-Erweiterung
```
