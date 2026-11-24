#!/bin/bash
# Rechenkette (seriell, saubere Latenz). Gewichte kommen per mb_fetch.py parallel im Voraus.
# Je Modell: Smoke (5 Bilder own_probe) -> alle Splits in EINEM Prozess (einmal laden) -> Gewichte löschen. 'test' wird nie angefasst.
cd "$(dirname "$0")"; PY=../../.venv_mb/bin/python
for M in "$@"; do
  echo "##### $M $(date +%T)"
  until [ -f hf_cache/$M/.done ]; do sleep 10; done
  echo "rechnet $M $(date +%T)"
  OK=1
  $PY -I mb_run.py --model $M --split own_probe --limit 5 --tag smoke >> logs/$M.log 2>&1 || { echo "SMOKE FEHLGESCHLAGEN $M" | tee -a logs/$M.log; OK=0; }
  [ $OK = 1 ] && { $PY -I mb_run.py --model $M --split own_probe,own_ketten,dev,synth,synth_hard >> logs/$M.log 2>&1 || { echo "LAUF FEHLGESCHLAGEN $M" | tee -a logs/$M.log; OK=0; }; }
  if [ $OK = 1 ]; then rm -rf hf_cache/$M; echo "Gewichte entfernt: $M" >> logs/$M.log; else echo "Gewichte BEHALTEN (Fehlschlag, Analyse): $M" >> logs/$M.log; fi
done
echo "ALLE FERTIG $(date +%T)"
