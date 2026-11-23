#!/usr/bin/env python3
"""TexTeller als Dauerprozess (läuft in .venv_tt): je Zeile ein PNG-Pfad auf stdin -> eine JSON-Zeile {latex, ms}.
Gleiches Muster wie vision_ocr --batch: Modell einmal laden, dann pro Formel ~0,2 s auf MPS."""
import json, re, sys, time

import torch
from texteller import img2latex, load_model, load_tokenizer

dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
model = load_model(None, use_onnx=False).to(dev)
tok = load_tokenizer(None)
print(json.dumps({"ready": str(dev)}), flush=True)
for line in sys.stdin:
    path = line.strip()
    if not path:
        continue
    t0 = time.perf_counter()
    try:
        r = img2latex(model, tok, [path], device=dev)[0]
        out = {"latex": re.sub(r"^\\\[|\\\]$", "", r.strip().strip("$").strip()).strip()}
    except Exception as e:  # ein kaputtes Bild darf den Prozess nicht beenden
        out = {"latex": "", "error": str(e)}
    out["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    print(json.dumps(out), flush=True)
