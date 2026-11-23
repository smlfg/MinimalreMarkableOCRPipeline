"""Ketten-Kalibrierungsblatt (ADR-009). reMarkable 1404x1872.
Je Kette: gedruckte Aufgabe, darunter je Schritt links die Vorlage (grau), rechts die Schreibfläche.
Ausgabe: PDF nach data/kalib/ (gitignored), ketten_gt.jsonl hier (versioniert)."""
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

from items import CHAINS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                       # MinimalreMarkableOCRPipeline
PDF = ROOT / "data" / "kalib" / "Kalibrierung-Ketten.pdf"
W, H, M = 1404, 1872, 70
TOP, ROW, BOTTOM = 100, 106, 30
SPLIT = 660                                  # links Vorlage, rechts schreiben (x in Seitenpixeln)
ROWS = (H - TOP - BOTTOM) // ROW
F = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
FT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)


def tex(latex: str, size: int = 15) -> Image.Image:
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${latex}$", fontsize=size)
    buf = io.BytesIO()
    fig.savefig(buf, dpi=226, bbox_inches="tight", pad_inches=0.02, transparent=False)
    plt.close(fig)
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def paste(pg, im, x, y, maxw, maxh, grey):
    s = min(1.0, maxw / im.size[0], maxh / im.size[1])
    im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    if grey:
        im = im.point(lambda v: 255 - int((255 - v) * 0.55))
    pg.paste(im, (x, y + (maxh - im.size[1]) // 2))


pages, gt, rows_used, pg, d = [], [], ROWS, None, None
for cid, topic, steps, label, kind in CHAINS:
    need = len(steps)
    if rows_used + need > ROWS:
        pg = Image.new("L", (W, H), 255); d = ImageDraw.Draw(pg); pages.append(pg); rows_used = 0
    top = TOP + rows_used * ROW
    d.text((M, top + 8), f"{cid}  Aufgabe:", font=F, fill=60)
    paste(pg, tex(steps[0]), M + 190, top, W - 2 * M - 190, ROW - 30, grey=False)
    slots = []
    for k in range(1, len(steps)):
        y = top + k * ROW
        paste(pg, tex(steps[k]), M, y + 10, SPLIT - M - 30, ROW - 34, grey=True)
        d.line([(SPLIT + 20, y + ROW - 16), (W - M, y + ROW - 16)], fill=200, width=2)
        slots.append({"step": k, "page": len(pages) - 1, "slot_y": [y + 4, y + ROW - 16], "x_min": SPLIT})
    d.line([(M, top + need * ROW - 4), (W - M, top + need * ROW - 4)], fill=230, width=1)
    rows_used += need
    gt.append({"id": cid, "topic": topic, "steps": steps, "label": label, "error_kind": kind, "slots": slots})

for i, pg in enumerate(pages):
    ImageDraw.Draw(pg).text((M, 40), f"Kalibrierung Ketten · Seite {i + 1}/{len(pages)} · jeden grauen Schritt rechts genau so abschreiben", font=FT, fill=0)
PDF.parent.mkdir(parents=True, exist_ok=True)
rgb = [p.convert("RGB") for p in pages]
rgb[0].save(PDF, save_all=True, append_images=rgb[1:], resolution=226)
(HERE / "ketten_gt.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gt))
pages[0].resize((W // 2, H // 2)).save(HERE / "preview_p1.png")
err = sum(r["label"] != -1 for r in gt)
pos = {k: sum(r["label"] == k for r in gt) for k in (1, 2, 3)}
print(f"{len(gt)} Ketten, {len(pages)} Seiten, {sum(len(r['slots']) for r in gt)} Schreib-Slots, "
      f"mit Fehler {err} ({err / len(gt):.0%}), Fehlerschritt {pos}")
