#!/usr/bin/env python3
"""claudebench: kleine Web-Oberfläche, die die Minimal-Pipeline beobachtbar macht.

Ablauf (Flywheel): Seite vom Tablet holen (oder PNG hochladen) -> Ground Truth eintippen
-> alle OCR-Varianten laufen lassen -> Abstand zur GT sehen -> Variante/Schreibweise
ändern -> erneut. Jeder Lauf landet in data/claudebench/runs.jsonl.

Start:  python3 bench/claudebench.py   ->  http://127.0.0.1:8790
Nur Glue um ocr/pipeline.py; kein eigener OCR-Code. Tutor/LLM bewusst noch nicht drin.
"""

import hashlib, json, subprocess, sys, tempfile, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from ocr import pipeline  # noqa: E402

OUT = BASE_DIR / "data" / "claudebench"
IMG = OUT / "img"
RUNS = OUT / "runs.jsonl"
PORT = 8790
SSH_HOST = "remarkable-usb"
XOCHITL = "/home/root/.local/share/remarkable/xochitl"

# Feste Varianten, damit Läufe vergleichbar bleiben. Neue Variante = neue Zeile hier.
VARIANTS = {
    "vision_page":      {"engine": "apple_vision", "split_lines": False, "vision_correct": False},
    "vision_page_corr": {"engine": "apple_vision", "split_lines": False, "vision_correct": True},
    "vision_lines":     {"engine": "apple_vision", "split_lines": True,  "vision_correct": False},
    "tess_page":        {"engine": "tesseract_word", "split_lines": False, "psm": "6"},
}


def save_png(data: bytes) -> str:
    pid = hashlib.sha256(data).hexdigest()[:12]
    IMG.mkdir(parents=True, exist_ok=True)
    (IMG / f"{pid}.png").write_bytes(data)
    return pid


def fetch_tablet_page() -> str:
    """Neueste .rm-Seite vom Tablet holen und wie in vlm_consensus rendern (rmc -> svg -> png)."""
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", SSH_HOST]
    newest = subprocess.run(ssh + [f"ls -t {XOCHITL}/*/*.rm | head -1"], capture_output=True, text=True, check=False)
    remote = newest.stdout.strip()
    if newest.returncode != 0 or not remote:
        raise RuntimeError(f"Tablet nicht erreichbar oder keine Seite: {newest.stderr.strip() or 'leer'}")
    with tempfile.TemporaryDirectory() as td:
        rm, svg, png = Path(td, "p.rm"), Path(td, "p.svg"), Path(td, "p.png")
        subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{SSH_HOST}:{remote}", str(rm)], check=True)
        subprocess.run(["rmc", "-t", "svg", str(rm), "-o", str(svg)], check=True, capture_output=True)
        subprocess.run(["rsvg-convert", "-b", "white", "-z", "2", str(svg), "-o", str(png)], check=True, capture_output=True)
        return save_png(png.read_bytes())


def run_all(pid: str, gt: str) -> list[dict]:
    png = IMG / f"{pid}.png"
    rows = []
    for name, cfg in VARIANTS.items():
        res = pipeline.run_detailed(png, cfg)
        ocr = res["final"]
        rows.append({
            "variant": name, "ocr": ocr, "ms": round(res["ms"], 1),
            "acc": round(pipeline.accuracy(gt, ocr), 3) if gt.strip() else None,
            "exact": bool(gt.strip()) and pipeline.norm(gt) == pipeline.norm(ocr),
            "diff": pipeline.diff_tags(pipeline.norm(gt), pipeline.norm(ocr))[:6] if gt.strip() else [],
        })
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "img": pid, "gt": gt,
           "variants": VARIANTS, "results": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rows


def history(n: int = 30) -> list[dict]:
    if not RUNS.is_file():
        return []
    out = []
    for line in RUNS.read_text(encoding="utf-8").splitlines()[-n:]:
        r = json.loads(line)
        best = max(r["results"], key=lambda x: x["acc"] or 0)
        out.append({"ts": r["ts"], "img": r["img"], "gt": r["gt"], "best": best["variant"],
                    "acc": best["acc"], "exact": best["exact"]})
    return out[::-1]


PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>claudebench</title>
<style>
:root{--bg:#fafaf8;--fg:#1c1c1a;--mute:#6b6b66;--line:#ddd;--ok:#1f7a3a;--bad:#b3261e;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--mute:#9a9a94;--line:#333;--ok:#5cc27a;--bad:#ef6b62;--card:#1f1f1e}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px;max-width:1100px}
h1{font-size:20px;margin:0 0 12px}.row{display:flex;gap:16px;flex-wrap:wrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;flex:1;min-width:280px}
img{max-width:100%;border:1px solid var(--line);border-radius:4px;background:#fff}
textarea{width:100%;box-sizing:border-box;font:15px ui-monospace,monospace;min-height:70px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:6px}
button{font:inherit;padding:6px 12px;margin:4px 4px 0 0;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
pre{margin:0;white-space:pre-wrap;font:13px ui-monospace,monospace}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad)}.mute{color:var(--mute)}
</style></head><body>
<h1>claudebench – Minimal-Pipeline beobachten</h1>
<div class="row">
 <div class="card"><b>1 · Tablet-Schrift (RM)</b><br>
  <button onclick="fetchTab()">Neueste Seite vom Tablet holen</button>
  <label><input type="file" accept="image/png,image/jpeg" onchange="upload(this.files[0])"></label>
  <div id="imgbox" class="mute" style="margin-top:8px">noch kein Bild</div></div>
 <div class="card"><b>2 · Ground Truth (so muss es heißen)</b>
  <textarea id="gt" placeholder="z. B. lim_{x->0} (cos^2(x)-1)/x^2"></textarea>
  <button onclick="run()">OCR laufen lassen</button> <span id="st" class="mute"></span></div>
</div>
<div class="card" style="margin-top:16px"><b>3 · OCR-Ergebnis je Variante</b> <span class="mute">· 4 · LLM-Ausgabe: kommt später (Tutor bewusst noch nicht angebunden)</span>
 <table><thead><tr><th>Variante</th><th>OCR</th><th>Acc</th><th>Abweichung zur GT</th><th>ms</th></tr></thead><tbody id="res"></tbody></table></div>
<div class="card" style="margin-top:16px"><b>Flywheel-Verlauf</b> <span class="mute">(beste Variante je Lauf, neueste oben)</span>
 <table><thead><tr><th>Zeit</th><th>Bild</th><th>GT</th><th>beste</th><th>Acc</th></tr></thead><tbody id="hist"></tbody></table></div>
<script>
let img=null;const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function show(id){img=id;$('imgbox').innerHTML='<img src="/img/'+id+'.png?'+Date.now()+'">'}
async function post(u,b,t){const r=await fetch(u,{method:'POST',body:b,headers:{'Content-Type':t||'application/json'}});const j=await r.json();if(!r.ok)throw new Error(j.error);return j}
async function upload(f){if(!f)return;$('st').textContent='lade hoch…';try{show((await post('/upload',f,'application/octet-stream')).id);$('st').textContent=''}catch(e){$('st').textContent=e.message}}
async function fetchTab(){$('st').textContent='hole Seite vom Tablet…';try{show((await post('/fetch','{}')).id);$('st').textContent=''}catch(e){$('st').textContent=e.message}}
async function run(){if(!img){$('st').textContent='erst ein Bild';return}$('st').textContent='OCR läuft…';
 try{const j=await post('/run',JSON.stringify({id:img,gt:$('gt').value}));
 $('res').innerHTML=j.rows.map(r=>`<tr><td>${r.variant}</td><td><pre>${esc(r.ocr)||'<span class=mute>(leer)</span>'}</pre></td><td class="${r.exact?'ok':(r.acc!==null&&r.acc<0.9?'bad':'')}">${r.acc===null?'–':(r.acc*100).toFixed(1)+' %'}${r.exact?' ✓':''}</td><td><pre class=mute>${esc(r.diff.join('\\n'))}</pre></td><td>${r.ms}</td></tr>`).join('');
 $('st').textContent='fertig';hist()}catch(e){$('st').textContent=e.message}}
async function hist(){const h=await (await fetch('/history')).json();
 $('hist').innerHTML=h.map(r=>`<tr><td>${r.ts.slice(5,16).replace('T',' ')}</td><td><a href="/img/${r.img}.png" target=_blank>${r.img.slice(0,6)}</a></td><td><pre>${esc(r.gt)}</pre></td><td>${r.best}</td><td class="${r.exact?'ok':''}">${r.acc===null?'–':(r.acc*100).toFixed(1)+' %'}${r.exact?' ✓':''}</td></tr>`).join('')}
hist();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if ctype == "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html")
        if self.path == "/history":
            return self._send(200, history())
        if self.path.startswith("/img/"):
            name = Path(self.path.split("?")[0]).name
            f = IMG / name
            if name.endswith(".png") and f.is_file():
                return self._send(200, f.read_bytes(), "image/png")
        self._send(404, {"error": "nicht gefunden"})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            if self.path == "/upload":
                return self._send(200, {"id": save_png(body)})
            if self.path == "/fetch":
                return self._send(200, {"id": fetch_tablet_page()})
            if self.path == "/run":
                req = json.loads(body)
                if not (IMG / f"{req['id']}.png").is_file():
                    raise RuntimeError("Bild unbekannt")
                return self._send(200, {"rows": run_all(req["id"], req.get("gt", ""))})
        except Exception as e:  # Fehler sichtbar in der UI statt stiller Abbruch
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        self._send(404, {"error": "nicht gefunden"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"claudebench läuft: http://127.0.0.1:{PORT}  (Läufe -> {RUNS.relative_to(BASE_DIR)})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
