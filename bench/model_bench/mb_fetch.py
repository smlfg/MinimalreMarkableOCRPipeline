"""Lädt die gepinnten Gewichte eines Modells vorab (parallel zu laufenden Benchmarks). Wartet, bis genug Platte frei ist.
  python mb_fetch.py <model_key>   -> hf_cache/<key>/ und Marker hf_cache/<key>/.done"""
import json, shutil, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
cfg = next(m for m in json.load(open(HERE / "MODEL_REGISTRY.json"))["models"] if m["key"] == sys.argv[1])
d = HERE / "hf_cache" / cfg["key"]; d.mkdir(parents=True, exist_ok=True)
have = lambda: sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e9
while shutil.disk_usage(HERE).free / 1e9 < (cfg["weights_gb"] - have()) + 3.0:    # 3 GB Reserve
    print(f"{cfg['key']}: warte auf Platz", flush=True); time.sleep(60)
import os
from huggingface_hub import snapshot_download
for attempt in range(1, 7):      # Xet-CAS-Fehler/Hänger: ab Versuch 2 ohne Xet (normaler HTTP-Download, resumierbar)
    try:
        if attempt > 1: os.environ["HF_HUB_DISABLE_XET"] = "1"
        snapshot_download(cfg["repo"], revision=cfg["revision"], allow_patterns=cfg["allow"], cache_dir=d, etag_timeout=30); break
    except Exception as e:
        print(f"{cfg['key']}: Versuch {attempt} fehlgeschlagen: {type(e).__name__}: {str(e)[:120]}", flush=True); time.sleep(10)
else: sys.exit(1)
(d / ".done").write_text("ok"); print(f"{cfg['key']}: geladen {have():.2f} GB", flush=True)
