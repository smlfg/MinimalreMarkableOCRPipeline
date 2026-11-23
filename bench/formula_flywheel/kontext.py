"""Kontext-Check: Kandidaten je Zeile (4 Modelle) + SymPy-Konsistenz innerhalb und zwischen Zeilen."""
from pathlib import Path
import sys, re, json
from PIL import Image
import models as M
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import structure_bench as sb, sympy
L = str(Path(__file__).resolve().parents[2] / "data" / "real_corpus" / "lines") + "/"
LINES = sys.argv[1:]
MODELS = ["glm-ocr:q8_0", "lfm3-vl:latest", "gemma4:26b", "qwen3.6:35b-a3b-8k"]

def segments(tex):
    tex = re.sub(r"\\(quad|qquad)|\|.*$", "", tex)            # Umformungsnotiz "| -3/2" abtrennen
    tex = tex.replace("+-", "\\pm").replace("\\pm", "+")       # ± vereinfachend als +
    parts = [p for p in re.split(r"(?<![<>!])=", tex) if p.strip()]
    out = []
    for p in parts:
        e = sb.parse(p)
        if e is None: return None
        out.append(e)
    return out

def intra_ok(segs):  # Gleichheitskette a = b = c: nur prüfbar, wenn keine Variable vorkommt
    if not segs or len(segs) < 2: return None
    if any(s.free_symbols for s in segs): return None
    try: return all(sympy.simplify(segs[0] - s) == 0 for s in segs[1:])
    except Exception: return None

def solset(segs):
    if not segs or len(segs) != 2: return None
    x = sympy.Symbol("x")
    try: return sympy.solveset(sympy.Eq(segs[0], segs[1]), x, sympy.S.Reals) if x in (segs[0]-segs[1]).free_symbols else None
    except Exception: return None

cands = {}
for ln in LINES:
    img = Image.open(L + ln)
    cands[ln] = [M.ask(m, M.to_h(img, 128))[0] for m in MODELS]
for ln in LINES:
    print("==", ln)
    for m, c in zip(MODELS, cands[ln]):
        s = segments(c); print(f"   {m[:6]:6} intra={str(intra_ok(s)):5} sol={str(solset(s))[:40]:40} | {c[:70]}")
