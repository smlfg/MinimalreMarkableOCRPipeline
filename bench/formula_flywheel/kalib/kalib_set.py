"""Kalibrierungsblatt: bekannte GT, der Owner schreibt jede Vorlage rechts daneben ab.
Schwerpunkt: Verwechsler (1/7, z/2, o/0, x/×, ./·, l/1, q/9, S/5, b/6, u/v), Schulmathe-Strukturen."""
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
SET = [
 r"0\,1\,2\,3\,4\,5\,6\,7\,8\,9", r"17+71=88", r"1+7=8", r"z=2z-2", r"x\cdot 2=2x", r"0.5\cdot 10=5",
 r"o_{1}+0=o_{1}", r"q-9=0", r"S=5+5", r"b=6", r"u+v=w", r"l=1+l-1",
 r"\frac{3}{4}+\frac{1}{4}=1", r"\frac{x+1}{x-1}", r"\sqrt{16}=4", r"\sqrt{x^{2}+y^{2}}", r"x^{2}-4=(x-2)(x+2)",
 r"2^{10}=1024", r"(a+b)^{2}=a^{2}+2ab+b^{2}", r"3x+5=20", r"3x=15", r"x=5",
 r"x^{2}+3x=1", r"(x+\frac{3}{2})^{2}=\frac{13}{4}", r"x=-\frac{3}{2}\pm\sqrt{\frac{13}{4}}",
 r"17\cdot 3=3\cdot 10+3\cdot 7=51", r"\frac{1}{2}+\frac{1}{3}=\frac{5}{6}", r"y=mx+b", r"f(x)=2x^{3}-x",
 r"f'(x)=6x^{2}-1", r"\lim_{x\to 0}\frac{\sin x}{x}=1", r"\int_{0}^{1}x\,dx=\frac{1}{2}",
 r"a_{n}=a_{1}+(n-1)d", r"\log_{2}8=3", r"e^{\ln 2}=2", r"\pi r^{2}", r"\alpha+\beta=90",
 r"\Delta x=x_{2}-x_{1}", r"2\leq x\leq 4", r"x\neq 0",
]
here = Path(__file__).parent
(here / "kalib_gt.jsonl").write_text("".join(json.dumps({"nr": i + 1, "gt_latex": s.replace(r"\,", "")}) + "\n" for i, s in enumerate(SET)))
with PdfPages(here / "kalibrierung.pdf") as pdf:
    per = 10
    for p in range(0, len(SET), per):
        fig = plt.figure(figsize=(1404 / 226, 1872 / 226), dpi=226)   # reMarkable-Seitenformat
        fig.text(0.05, 0.965, f"Kalibrierung Seite {p // per + 1}/{(len(SET) + per - 1) // per} – rechts neben jede Vorlage abschreiben", fontsize=6)
        for k, s in enumerate(SET[p:p + per]):
            y = 0.9 - k * 0.088
            fig.text(0.04, y, f"{p + k + 1}", fontsize=7, color="0.4")
            fig.text(0.09, y, "$" + s.replace(r"\\le ", r"\\leq ").replace(r"\\ne ", r"\\neq ") + "$", fontsize=8, color="0.35")
            fig.add_artist(plt.Line2D([0.47, 0.97], [y - 0.025, y - 0.025], color="0.85", lw=0.5))
        fig.add_artist(plt.Line2D([0.45, 0.45], [0.03, 0.94], color="0.85", lw=0.5))
        pdf.savefig(fig); plt.close(fig)
print(len(SET), "Vorlagen ->", here / "kalibrierung.pdf")
