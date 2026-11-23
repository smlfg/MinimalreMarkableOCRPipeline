"""Pixel-basiert: großes Band rendern, von der Zielzeile aus bis zu echten Leerzeilen (>=GAP) wachsen."""
import numpy as np, pymupdf
from PIL import Image
from items import SRC, ITEMS, EXACT
DPI = 200; K = DPI / 72; GAP = int(2.5 * K); MAXG = int(12 * K); PAD = 8
def crop(page, x0, y0, x1, y1, exact=False):
    Y0, Y1 = max(0, y0 - 60), y1 + 60
    pix = page.get_pixmap(dpi=DPI, clip=pymupdf.Rect(x0, Y0, x1, Y1))
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[..., :3].mean(2) < 160
    rows = a.any(1); s, e = int((y0 - Y0) * K), int((y1 - Y0) * K)
    ink = np.where(rows[s:e])[0]
    if len(ink) == 0: raise ValueError("leer")
    top, bot = s + ink[0], s + ink[-1]
    def grow(i, step):
        blank = 0; start = i
        while 0 <= i + step < len(rows) and abs(i - start) < MAXG:
            i += step; blank = blank + 1 if not rows[i] else 0
            if blank >= GAP: return i - step * GAP
        return i - step * blank
    if not exact: top, bot = grow(top, -1), grow(bot, 1)
    sub = a[top:bot + 1]; cols = np.where(sub.any(0))[0]
    img = Image.frombytes("RGB", (pix.w, pix.h), pix.samples if pix.n == 3 else pix.pil_tobytes("png") and pix.samples)
    return Image.fromarray((~a[max(0, top - PAD):bot + PAD, max(0, cols[0] - PAD):cols[-1] + PAD] * 255).astype(np.uint8))
if __name__ == "__main__":
    d = pymupdf.open(SRC)
    for i, (pg, y0, y1, x0, x1, auf, gt) in enumerate(ITEMS, 1):
        crop(d[pg - 1], x0, y0, x1, y1, i in EXACT).save(f"crops/u{i:02d}.png")
    print("ok", len(ITEMS))
