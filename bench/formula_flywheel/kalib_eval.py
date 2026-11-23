"""Eigene Schrift messen: Striche vom Tablet -> Slot je Vorlage -> PNG -> pipeline -> Score gegen bekannte GT.
Aufruf: python kalib_eval.py probe|uni|ketten   (holt Seiten frisch per scp)"""
import json, subprocess, sys
from pathlib import Path
import rmscene
from rmscene import scene_items as si
from PIL import Image, ImageDraw
HERE = Path(__file__).resolve().parent; FW = HERE
DOCS = {"probe": "8b8cfaa5-f013-462d-8391-9228906287f5", "uni": "406f242e-4844-4a85-a4d4-4ed2ca5f0db7",
        "ketten": "8a5fc918-e5db-43e1-973f-4235c3ef3008"}  # Kalibrierung-Ketten.pdf, frisch hochgeladen (ADR-009)
XO = "/home/root/.local/share/remarkable/xochitl"
PROJ = Path(__file__).resolve().parent / "kalib"  # versionierte GT der Kalibrierungsblätter

def slots(sheet):
    """[(nr, seite, y_oben, y_unten, gt)] in Seitenpixeln; bei ketten ist nr = (kette, schritt)."""
    if sheet == "ketten":
        out = []
        for c in map(json.loads, open(PROJ / "ketten" / "ketten_gt.jsonl")):
            for sl in c["slots"]:
                out.append(((c["id"], sl["step"]), sl["page"], sl["slot_y"][0], sl["slot_y"][1], c["steps"][sl["step"]]))
        # Bänder nach oben öffnen: hohe Zeichen (Exponent, Bruchzähler) sitzen in echter
        # Handschrift über der Bandgrenze (K01/K11) und wurden sonst beim Rendern abgeschnitten.
        # Öffnung nur bis 4 px unter den Slot davor, Erstslot einer Seite bis y=120.
        out.sort(key=lambda r: (r[2], r[3]))
        opened, prev = [], {}
        for nr, p, ya, yb, gt in out:
            ya2 = max((prev[p][1] + 4) if p in prev else 120, ya - 90)
            opened.append((nr, p, ya2, yb, gt)); prev[p] = (ya2, yb)
        return opened
    if sheet == "probe":
        gt = [json.loads(l) for l in open(PROJ / "kalib_gt.jsonl")]
        out = []
        for r in gt:
            i = r["nr"] - 1; p, k = divmod(i, 10)
            yb = (1 - (0.9 - k * 0.088 - 0.025)) * 1872          # Unterstrich
            out.append((r["nr"], p, yb - 150, yb + 15, r["gt_latex"]))
        return out
    gt = [json.loads(l) for l in open(PROJ / "uni" / "kalib_uni_gt.jsonl")]
    return [(r["nr"], (r["nr"] - 1) // 5, r["slot_y"][0] - 40, r["slot_y"][1] + 5, r["gt_latex"]) for r in gt]

def _n_pages(d):
    r = subprocess.run(["ssh", "remarkable-usb", f"ls {XO}/{d}/ 2>/dev/null | grep -c '\\.rm$'"], capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def fetch(sheet):
    d = DOCS[sheet]
    if d is None:
        sys.exit(f"{sheet}: Dokument-ID fehlt in DOCS (Blatt erst aufs Tablet laden)")
    if isinstance(d, list):
        d = max(d, key=_n_pages)
    out = HERE / "own" / sheet; out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["scp", "-q", f"remarkable-usb:{XO}/{d}.content", str(out)], check=True)
    subprocess.run(f"scp -q 'remarkable-usb:{XO}/{d}/*.rm' {out}/ 2>/dev/null", shell=True)
    c = json.load(open(out / f"{d}.content"))
    pages = c["cPages"]["pages"] if "cPages" in c else c["pages"]
    pages = [p["id"] if isinstance(p, dict) else p for p in pages]
    return [(out / f"{p}.rm") for p in pages]

def strokes(rm):
    if not rm.exists(): return []
    with open(rm, "rb") as f: tree = rmscene.read_tree(f)
    return [[(p.x + 702, p.y) for p in it.points] for it in tree.walk() if isinstance(it, si.Line) and len(it.points) > 1]

def render(strs, pad=20):
    xs = [x for s in strs for x, _ in s]; ys = [y for s in strs for _, y in s]
    x0, y0 = min(xs) - pad, min(ys) - pad
    im = Image.new("L", (int(max(xs) - x0 + pad), int(max(ys) - y0 + pad)), 255); d = ImageDraw.Draw(im)
    for s in strs: d.line([(x - x0, y - y0) for x, y in s], fill=0, width=4, joint="curve")
    return im

if __name__ == "__main__":
    sheet = sys.argv[1]; rms = fetch(sheet); S = slots(sheet)
    per_page = {i: strokes(rm) for i, rm in enumerate(rms)}
    rows = []; (HERE / "own" / sheet / "png").mkdir(exist_ok=True)
    for nr, p, ya, yb, gt in S:
        sel = [s for s in per_page.get(p, []) if ya <= sum(y for _, y in s) / len(s) <= yb and (sheet != "probe" or sum(x for x, _ in s) / len(s) > 560) and (sheet != "ketten" or sum(x for x, _ in s) / len(s) > 660)]
        if not sel: continue
        name = f"{sheet}_{nr[0]}_s{nr[1]}" if sheet == "ketten" else f"{sheet}_{nr:02d}"
        png = HERE / "own" / sheet / "png" / f"{name}.png"; render(sel).save(png)
        row = {"id": name, "src": sheet, "png": str(png.relative_to(FW)), "gt_latex": gt}
        if sheet == "ketten":
            row.update(chain_id=nr[0], step=nr[1])
        rows.append(row)
    (FW / "data" / f"own_{sheet}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(sheet, "beschriebene Slots:", len(rows), "von", len(S))
