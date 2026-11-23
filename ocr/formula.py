"""Formel-Erkennung (ADR-006/007): TexTeller liest, GLM-OCR prüft, Kohärenz-Schicht dahinter.
recognize(png) -> {"latex", "repair", "cost_s", "uncertain", "math_status", "alt"}.
uncertain ist nur OCR-Konfidenz (nicht trusted oder Reparatur, Issue #1); math_status = closed_truth(fixed).
Engines sind injizierbar (Flywheel nutzt Cache)."""
import base64, io, json, re, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

from ocr.coherence import closed_truth, coherent, decimal_comma
from ocr.latex import same

ROOT = Path(__file__).resolve().parents[1]
TT_PY = ROOT / ".venv_tt" / "bin" / "python"
GLM_MODEL = "glm-ocr:q8_0"


def to_height(img: Image.Image, h: int = 128) -> Image.Image:
    """Pre für GLM: Graustufe, feste Höhe, Rand (TexTeller normalisiert selbst)."""
    g = img.convert("L"); w0, h0 = g.size
    g = g.resize((max(1, min(2000, round(w0 * h / h0))), h), Image.LANCZOS)
    return ImageOps.expand(g, border=h // 8, fill=255)


class TexTeller:
    """Live-Engine: ein Dauerprozess in .venv_tt."""
    def __init__(self):
        self.p = subprocess.Popen([str(TT_PY), str(Path(__file__).with_name("texteller_worker.py"))],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        json.loads(self.p.stdout.readline())  # {"ready": ...}

    def __call__(self, path: str):
        self.p.stdin.write(str(path) + "\n"); self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline())
        return r["latex"], r["ms"] / 1000


def glm_live(img: Image.Image):
    """Live-Engine: GLM-OCR über Ollama."""
    import time
    b = io.BytesIO(); img.save(b, format="PNG")
    body = {"model": GLM_MODEL, "prompt": "Formula Recognition:", "images": [base64.b64encode(b.getvalue()).decode()],
            "stream": False, "keep_alive": "30m", "options": {"temperature": 0, "num_predict": 256}}
    t0 = time.perf_counter()
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:11434/api/generate",
                                                                data=json.dumps(body).encode()), timeout=120))["response"]
    return re.sub(r"^\s*\$\$|\$\$\s*$", "", r.strip()).strip(), time.perf_counter() - t0


_POOL = ThreadPoolExecutor(max_workers=2)


def recognize(path, tt, glm=glm_live) -> dict:
    ft = _POOL.submit(tt, str(path))                       # TexTeller und GLM laufen wirklich parallel,
    fg = _POOL.submit(glm, to_height(Image.open(path)))    # daher ist cost_s = max der beiden
    (t, st), (g, sg) = ft.result(), fg.result()
    t = decimal_comma(t)
    fixed, repair, trusted = coherent(t, g)
    uncertain = (not trusted) or (repair is not None)
    return {"latex": fixed, "repair": repair, "cost_s": max(st, sg),
            "uncertain": uncertain, "math_status": closed_truth(fixed),
            "alt": None if trusted else g}


if __name__ == "__main__":
    import sys
    tt = TexTeller()
    for p in sys.argv[1:]:
        print(p, json.dumps(recognize(p, tt), ensure_ascii=False))
