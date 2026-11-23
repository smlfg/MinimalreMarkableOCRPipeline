"""TexTeller (Apache-2.0) über einen Split laufen lassen; schreibt in cache.sqlite (Schlüssel: texteller + Bilddatei-Bytes)."""
import hashlib, json, sqlite3, sys, time
from pathlib import Path
import torch
from texteller import load_model, load_tokenizer, img2latex
HERE = Path(__file__).resolve().parent
DB = sqlite3.connect(HERE / "cache.sqlite", timeout=60)
DB.execute("create table if not exists c(k text primary key, latex text, s real)")
dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
model = load_model(None, use_onnx=False).to(dev); tok = load_tokenizer(None)
print("device", dev, flush=True)
paths = [str(HERE / json.loads(l)["png"]) for s in sys.argv[1:] for l in open(HERE / "data" / f"{s}.jsonl")] if sys.argv[1] != "--files" else sys.argv[2:]
img2latex(model, tok, [paths[0]], device=dev)  # Warm-up
t0 = time.time()
for i, p in enumerate(paths):
    k = hashlib.sha1(b"texteller" + Path(p).read_bytes()).hexdigest()
    if DB.execute("select 1 from c where k=?", (k,)).fetchone(): continue
    a = time.perf_counter(); r = img2latex(model, tok, [p], device=dev)[0]; s = time.perf_counter() - a
    DB.execute("insert or replace into c values(?,?,?)", (k, r.strip().strip("$").strip(), s)); DB.commit()
    if i % 50 == 0: print(i, f"{s:.2f}s", r[:60], flush=True)
print("fertig", len(paths), f"{time.time()-t0:.0f}s")
