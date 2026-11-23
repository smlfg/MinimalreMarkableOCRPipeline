"""Uni-Kalibrierungsblatt: Original-Ausschnitt + Quelle oben, Schreibfläche darunter. reMarkable 1404x1872."""
import json
from PIL import Image, ImageDraw, ImageFont
from items import SRC, ITEMS
W, H, M = 1404, 1872, 70; PER = 5; SLOT = (H - 150) // PER
F = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24); FT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
pages = []; gt = []
for p0 in range(0, len(ITEMS), PER):
    pg = Image.new("L", (W, H), 255); d = ImageDraw.Draw(pg)
    d.text((M, 40), f"Kalibrierung Uni-Mathe · Seite {p0 // PER + 1}/{(len(ITEMS) + PER - 1) // PER} · unter jede Vorlage genau so abschreiben", font=FT, fill=0)
    for k in range(PER):
        i = p0 + k
        if i >= len(ITEMS): break
        pgnr, y0, y1, x0, x1, auf, g = ITEMS[i]; n = i + 1
        top = 110 + k * SLOT
        d.text((M, top), f"{n}  ·  Klausur SS26 Lösung, S. {pgnr}, {auf}", font=F, fill=90)
        im = Image.open(f"crops/u{n:02d}.png").convert("L")
        s = min(1.0, (W - 2 * M) / im.size[0], 120 / im.size[1]); im = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.LANCZOS)
        im = im.point(lambda v: 255 - int((255 - v) * 0.55))  # grau, damit die eigene Schrift dominiert
        pg.paste(im, (M, top + 34))
        d.line([(M, top + SLOT - 14), (W - M, top + SLOT - 14)], fill=200, width=2)
        gt.append({"nr": n, "gt_latex": g, "quelle": f"klausur_aki_ss26_lsg.pdf S.{pgnr}", "aufgabe": auf, "slot_y": [top + 34 + im.size[1] + 6, top + SLOT - 14]})
    pages.append(pg.convert("RGB"))
pages[0].save("Kalibrierung-Uni-SS26.pdf", save_all=True, append_images=pages[1:], resolution=226)
open("kalib_uni_gt.jsonl", "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gt))
pages[2].resize((W // 2, H // 2)).save("preview_p3.png"); print(len(pages), "Seiten,", len(gt), "Vorlagen")
