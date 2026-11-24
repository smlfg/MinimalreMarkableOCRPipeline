#!/bin/bash
# Reproduzierbarer Lauf: je Modell Smoke (5 Bilder own_probe) -> alle eingefrorenen Splits -> Gewichte löschen (Platte knapp).
# Splits: own_probe, own_ketten, dev, synth, synth_hard.  'test' wird NIE angefasst.
# Aufruf: bash run_all.sh <model_key> [<model_key> ...]
cd "$(dirname "$0")"; PY=../../.venv_mb/bin/python
for M in "$@"; do
  echo "##### $M $(date +%T)"
  $PY -I mb_run.py --model $M --split own_probe --limit 5 --tag smoke >> logs/$M.log 2>&1 || echo "SMOKE FEHLGESCHLAGEN $M" | tee -a logs/$M.log
  for S in own_probe own_ketten dev synth synth_hard; do
    $PY -I mb_run.py --model $M --split $S >> logs/$M.log 2>&1 || echo "LAUF FEHLGESCHLAGEN $M $S" | tee -a logs/$M.log
  done
  if [ "${KEEP_WEIGHTS:-0}" != "1" ]; then
    R=$($PY -I -c "import json,sys;print(next(m['repo'] for m in json.load(open('MODEL_REGISTRY.json'))['models'] if m['key']=='$M').replace('/','--'))")
    rm -rf "hf_cache/hub/models--$R" hf_cache/hub/blobs hf_cache/hub/.locks hf_cache/xet/*/chunk-cache; echo "Gewichte entfernt (inkl. geteilter Blobs): $R" >> logs/$M.log
  fi
done
echo "ALLE FERTIG $(date +%T)"
