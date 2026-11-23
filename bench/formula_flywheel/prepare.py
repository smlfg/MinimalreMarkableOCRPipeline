"""EINGEFROREN (wie autoresearch/prepare.py). Splits + Bewertung. Die Schleife ändert diese Datei nie.
  python prepare.py build          -> data/{train,dev,test}.jsonl + images/
  evaluate(recognize, split)       -> dict(char, struct, p50, p95, n)
Metriken: char = mittlere Zeichengenauigkeit 1-CER auf normalisiertem LaTeX; struct = sympy_equal-Rate.
test ist Holdout: nur an Meilensteinen, nie für Entscheidungen."""
import hashlib, io, json, re, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
PROJ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJ / "bench"))
import structure_bench as sb
from rapidfuzz.distance import Levenshtein

ALLOWED = {r"\frac", r"\sqrt", r"\lim", r"\to", r"\rightarrow", r"\infty", r"\sin", r"\cos", r"\tan", r"\log", r"\ln", r"\pi",
           r"\cdot", r"\times", r"\div", r"\left", r"\right", r"\pm", r"\le", r"\ge", r"\leq", r"\geq", r"\neq", r"\int",
           r"\alpha", r"\beta", r"\theta", r"\Delta"}

def is_school(gt):
    if not set(re.findall(r"\\[A-Za-z]+", gt)) <= ALLOWED: return False
    rest = re.sub(r"\\[A-Za-z]+", "", gt)
    if re.search(r"[|\[\]&;:!?'\"]|\.\.\.", rest): return False
    if re.search(r"[A-Za-z]{3,}", rest.replace(" ", "")): return False
    return sb.parse(gt) is not None

def join_tokens(toks):
    out = ""
    for t in toks:
        if re.search(r"\\[A-Za-z]+$", out) and t[:1].isalpha(): out += " "
        out += t
    return out

def split_of(key, seen):
    if key in seen: return "train"                      # heute schon angesehen -> kontaminiert
    h = int(hashlib.sha1(key.encode()).hexdigest(), 16) % 100
    return "dev" if h < 15 else "test" if h < 35 else "train"

def build():
    import pyarrow.parquet as pq
    from PIL import Image, ImageOps, ImageStat
    seen = set()
    for src in ["mathwriting_human", "crohme_neeze"]:
        for l in open(PROJ / f"data/external/{src}/manifest_schule.jsonl"):
            seen.add(json.loads(l)["gt_raw" if src == "crohme_neeze" else "gt_latex"])
    (HERE / "images").mkdir(exist_ok=True); out = {s: [] for s in ["train", "dev", "test"]}
    srcs = [("mw", PROJ / "data/external/mathwriting_human/raw/test-0000.parquet", "latex"),
            ("crohme", PROJ / "data/external/crohme_neeze/raw/2014-0000.parquet", "label")]
    for name, p, col in srcs:
        t = pq.read_table(p).to_pylist()
        for i, r in enumerate(t):
            raw = r[col]
            gt = raw
            if name == "crohme":
                toks = raw.split()
                if len(toks) < 5: continue
                gt = join_tokens(toks)
            if not is_school(gt): continue
            im = Image.open(io.BytesIO(r["image"]["bytes"])).convert("L")
            if ImageStat.Stat(im).median[0] < 128: im = ImageOps.invert(im)   # Datensatz-Konvention vereinheitlichen
            rid = f"{name}_{i:05d}"; im.save(HERE / "images" / f"{rid}.png")
            s = split_of(raw, seen)
            out[s].append({"id": rid, "src": name, "png": f"images/{rid}.png", "gt_latex": gt})
    (HERE / "data").mkdir(exist_ok=True)
    for s, rows in out.items():
        (HERE / "data" / f"{s}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(s, len(rows), {k: sum(r["src"] == k for r in rows) for k in ["mw", "crohme"]})

def load(split):
    return [json.loads(l) for l in open(HERE / "data" / f"{split}.jsonl")]

def char_acc(gt, pred):
    return Levenshtein.normalized_similarity(sb.normalize(gt), sb.normalize(pred))

def evaluate(recognize, split="dev", limit=None, log=None):
    rows = load(split)[:limit]; res = []; lat = []
    for r in rows:
        t0 = time.perf_counter(); out = recognize(str(HERE / r["png"])); dt = time.perf_counter() - t0
        if isinstance(out, dict) and "cost_s" in out: dt = out["cost_s"]   # echte Modellzeit aus Cache
        pred = out["latex"] if isinstance(out, dict) else out
        unc = out.get("uncertain", False) if isinstance(out, dict) else False
        s = sb.score(r["gt_latex"], pred)
        res.append({"id": r["id"], "src": r["src"], "pred": pred, "ok": bool(s["sympy_equal"]), "char": char_acc(r["gt_latex"], pred), "unc": unc, "s": dt})
        lat.append(dt)
    if log:
        Path(log).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in res))
    lat.sort(); n = len(res); cert = [x for x in res if not x["unc"]]
    m = {"n": n, "struct": sum(x["ok"] for x in res) / n, "char": sum(x["char"] for x in res) / n,
         "p50": lat[n // 2], "p95": lat[int(n * 0.95) - 1],
         "coverage": len(cert) / n, "prec_certain": sum(x["ok"] for x in cert) / max(len(cert), 1)}
    for src in ["mw", "crohme"]:
        sub = [x for x in res if x["src"] == src]
        if sub: m[f"struct_{src}"] = sum(x["ok"] for x in sub) / len(sub)
    return m

if __name__ == "__main__" and sys.argv[1:] == ["build"]:
    build()
