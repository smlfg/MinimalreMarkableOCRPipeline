"""Synthetische Zeilen mit bekannter GT über den Generator aus SchlangebeißtinSchwanz (nur lesend importiert)."""
import json, random, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "SchlangebeißtinSchwanz"))
import dynamic_writer as W
rng = random.Random(7); out = Path(__file__).parent; rows = []
def eq():
    a, b, c = rng.randint(2, 19), rng.randint(1, 30), rng.randint(1, 9)
    v = rng.choice("xyzab")
    return rng.choice([
        (f"{a}{v}+{b}={a*c+b}", f"{a}{v}+{b}={a*c+b}"),
        (f"{a}{v}={a*c}", f"{a}{v}={a*c}"),
        (f"{v}²+{a}{v}={b}", f"{v}^{{2}}+{a}{v}={b}"),
        (f"{a}·{c}={a*c}", f"{a}\\cdot{c}={a*c}"),
        (f"{a}({v}-{c})={b}", f"{a}({v}-{c})={b}"),
        (f"{a}/{c}+{b}", f"{a}/{c}+{b}"),
        (f"{v}={a*c}/{a}", f"{v}={a*c}/{a}"),
    ])
for i in range(100):
    txt, gt = eq()
    strokes = W.synthesize_handwriting_line(txt, 40, 120, scale=rng.uniform(2.6, 3.6), style="student", seed=i)
    xs = [p[0] for s in strokes for p in s["points"]]; ys = [p[1] for s in strokes for p in s["points"]]
    x0, y0 = min(xs) - 20, min(ys) - 20
    im = Image.new("L", (int(max(xs) - x0 + 20), int(max(ys) - y0 + 20)), 255); d = ImageDraw.Draw(im)
    for s in strokes:
        pts = [(p[0] - x0, p[1] - y0) for p in s["points"]]
        if len(pts) > 1: d.line(pts, fill=0, width=int(s.get("width", 3)), joint="curve")
    p = f"images/s{i:03d}.png"; im.save(out / p); rows.append({"id": f"s{i:03d}", "src": "synth", "png": f"synth/{p}", "gt_latex": gt})
(out / "synth.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows)); print(len(rows))
