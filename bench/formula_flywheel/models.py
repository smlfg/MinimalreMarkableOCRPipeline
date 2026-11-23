"""Modellaufrufe mit Cache (latex + echte Sekunden). Teil der eingefrorenen Infrastruktur."""
import base64, hashlib, io, json, re, sqlite3, time, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
DB = sqlite3.connect(HERE / "cache.sqlite", check_same_thread=False)
DB.execute("create table if not exists c(k text primary key, latex text, s real)")
PROMPTS = {"glm-ocr:q8_0": "Formula Recognition:"}
GENERIC = "Transcribe the handwritten math expression in this image into LaTeX. Output only the LaTeX, no $ signs, no explanation."

def png_bytes(img):
    b = io.BytesIO(); img.convert("RGB" if img.mode != "L" else "L").save(b, format="PNG"); return b.getvalue()

def clean(r):
    r = re.sub(r"```(latex)?", "", r).strip()
    return re.sub(r"^\s*\${1,2}|\${1,2}\s*$|^\\\[|\\\]$", "", r).strip()

def ask(model, img, prompt=None):
    data = png_bytes(img); prompt = prompt or PROMPTS.get(model, GENERIC)
    k = hashlib.sha1(model.encode() + prompt.encode() + data).hexdigest()
    row = DB.execute("select latex,s from c where k=?", (k,)).fetchone()
    if row: return row[0], row[1]
    body = {"model": model, "prompt": prompt, "images": [base64.b64encode(data).decode()], "stream": False, "think": False,
            "keep_alive": "30m", "options": {"temperature": 0, "num_predict": 256}}
    t0 = time.perf_counter()
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(body).encode()), timeout=300))["response"]
    s = time.perf_counter() - t0; latex = clean(r)
    DB.execute("insert or replace into c values(?,?,?)", (k, latex, s)); DB.commit()
    return latex, s

def tt(path):
    """TexTeller-Ergebnis aus dem Cache (befüllt durch tt_run.py in eigener venv)."""
    k = hashlib.sha1(b"texteller" + Path(path).read_bytes()).hexdigest()
    row = DB.execute("select latex,s from c where k=?", (k,)).fetchone()
    if row is None: raise KeyError(f"texteller nicht im Cache: {path}")
    return re.sub(r"^\\\[|\\\]$", "", row[0].strip()).strip(), row[1]
