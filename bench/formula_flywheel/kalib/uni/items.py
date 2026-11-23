"""Uni-Kalibrierung: Rechenschritte aus klausur_aki_ss26_lsg.pdf (Prof. Jahnke, HHN 174021).
Eintrag: (seite, y0, y1, x0, x1, aufgabe, gt_latex). Koordinaten in PDF-Punkten."""
SRC = "/Users/samuelfleig/Projects/02_STUDIUM/1.Semester-AKI-HNH/Mathematik (174021)/174021 Mathematik/Klausuren/klausur_aki_ss26_lsg.pdf"
ITEMS = [
 (2, 264, 300, 170, 455, "A1a Komplexe Zahlen", r"\frac{|z_{1}|^{2}}{z_{1}+z_{2}}=\frac{(-1)^{2}+3^{2}}{-1+3i+i+2}=\frac{10}{1+4i}=\frac{10(1-4i)}{(1+4i)(1-4i)}"),
 (2, 300, 333, 210, 400, "A1a Komplexe Zahlen", r"=\frac{10-40i}{1-16i^{2}}=\frac{10-40i}{17}=\frac{10}{17}-\frac{40}{17}i"),
 (2, 358, 380, 110, 333, "A1b Mitternachtsformel", r"z_{1,2}=1\pm\sqrt{-4+1}=1\pm\sqrt{-3}=1\pm i\sqrt{3}"),
 (2, 414, 438, 205, 300, "A1b Polardarstellung", r"r=\sqrt{1+3}=2"),
 (2, 407, 438, 300, 420, "A1b Polardarstellung", r"\varphi=\arctan(\sqrt{3})=\frac{\pi}{3}"),
 (2, 449, 471, 248, 298, "A1b Polardarstellung", r"z_{1}=2e^{i\frac{\pi}{3}}"),
 (3, 272, 316, 160, 495, "A2 Vektoren Winkel", r"\cos(\alpha)=\frac{\vec{a}\cdot\vec{b}}{|\vec{a}||\vec{b}|}=\frac{2+0+1}{\sqrt{1+0+1}\sqrt{4+4+1}}=\frac{3}{\sqrt{2}\cdot3}=\frac{1}{\sqrt{2}}=\frac{\sqrt{2}}{2}"),
 (3, 366, 408, 238, 415, "A2 Vektorprodukt", r"\vec{a}\times\vec{b}=\begin{pmatrix}1\\0\\1\end{pmatrix}\times\begin{pmatrix}2\\-2\\1\end{pmatrix}=\begin{pmatrix}2\\1\\-2\end{pmatrix}"),
 (3, 520, 547, 270, 380, "A2 Dreiecksfläche", r"A_{\Delta}=\frac{1}{2}|\vec{a}\times\vec{b}|=\frac{3}{2}"),
 (4, 238, 256, 330, 530, "A3a Determinante (Sarrus)", r"=0+2+a-4a-0-3=-3a-1"),
 (4, 420, 438, 150, 470, "A3a Rückwärtseinsetzen", r"x_{3}=1,\quad x_{2}=2+2=4,\quad x_{1}=9+1-8=2"),
 (4, 647, 661, 140, 400, "A3b Determinante", r"=-(-3+0+0-2-0-0)=5"),
 (4, 674, 702, 200, 420, "A3b Cramersche Regel", r"x_{2}=\frac{\det(A_{2})}{\det(A)}=-\frac{5}{3}"),
 (5, 438, 474, 190, 470, "A4a Lineare Abbildung", r"M=M_{s}\cdot M_{p}=\begin{pmatrix}2&0\\0&2\end{pmatrix}\cdot\begin{pmatrix}\frac{1}{2}&\frac{1}{2}\\\frac{1}{2}&\frac{1}{2}\end{pmatrix}=\begin{pmatrix}1&1\\1&1\end{pmatrix}"),
 (5, 519, 541, 331, 560, "A4b Char. Polynom", r"=(1-\lambda)(-2-\lambda)+2=\lambda^{2}+\lambda=\lambda(\lambda+1)"),
 (6, 324, 340, 150, 345, "A5a Mengen", r"M_{1}\cap M_{2}=\{1,3\}"),
 (6, 406, 426, 110, 420, "A5b Exponentialgleichung", r"e^{2x^{2}-1}\cdot e^{3x}=e\implies e^{2x^{2}-1+3x}=e"),
 (6, 440, 453, 140, 440, "A5b Exponentialgleichung", r"\implies2x^{2}-1+3x=1\implies2x^{2}+3x-2=0"),
 (6, 460, 484, 140, 560, "A5b pq-Formel", r"\implies x^{2}+\frac{3}{2}x-1=0\implies x_{1,2}=-\frac{3}{4}\pm\sqrt{1+\frac{9}{16}}=-\frac{3}{4}\pm\frac{5}{4}"),
 (6, 575, 588, 110, 460, "A5b Probe", r"x_{2}=-2:\quad e^{8-1}\cdot e^{-6}=e^{7-6}=e^{1}=e"),
 (7, 202, 230, 150, 520, "A6a Ableitungen", r"f'(x)=\frac{2x+3}{x^{2}+3x+1},\quad f''(x)=\frac{2(x^{2}+3x+1)-(2x+3)^{2}}{(x^{2}+3x+1)^{2}}"),
 (7, 268, 292, 140, 480, "A6a Taylor einsetzen", r"f(0)=\ln(1)=0,\quad f'(0)=\frac{3}{1}=3,\quad f''(0)=\frac{2-9}{1^{2}}=-7"),
 (7, 318, 360, 205, 440, "A6a Taylorpolynom", r"T_{2}(x)=\sum_{k=0}^{2}\frac{f^{(k)}(0)}{k!}x^{k}=0+3x-\frac{7}{2}x^{2}"),
 (7, 403, 430, 130, 440, "A6b Quotientenregel", r"f'(x)=\frac{xe^{x}-e^{x}}{x^{2}}=\frac{e^{x}(x-1)}{x^{2}}"),
 (7, 432, 459, 130, 520, "A6b Zweite Ableitung", r"f''(x)=\frac{(e^{x}(x-1)+e^{x})x^{2}-2xe^{x}(x-1)}{x^{4}}=\frac{e^{x}(x^{2}-2x+2)}{x^{3}}"),
 (7, 482, 512, 150, 460, "A6b Nullstelle", r"0=\frac{e^{x}(x-1)}{x^{2}}\iff x=1"),
 (7, 552, 572, 200, 420, "A6b Extremum", r"f''(1)=\frac{e(1-2+2)}{1}=e>0"),
 (9, 384, 402, 120, 500, "A7 Nullstellen", r"\sin(\pi x)=0\iff\pi x=\pi\text{ bzw. }2\pi\iff x_{1}=1,\ x_{2}=2"),
 (9, 438, 482, 110, 500, "A7 Integral", r"A=\int_{1}^{2}1-\frac{1}{x^{2}}-\sin(\pi x)\,dx=\left[x+\frac{1}{x}+\frac{1}{\pi}\cos(\pi x)\right]_{1}^{2}"),
 (9, 491, 510, 140, 560, "A7 Flächeninhalt", r"=2+\frac{1}{2}+\frac{1}{\pi}\cos(2\pi)-(1+1+\frac{1}{\pi}\cos(\pi))=\frac{1}{2}+\frac{1}{\pi}+\frac{1}{\pi}=\frac{1}{2}+\frac{2}{\pi}"),
]

EXACT = {12, 15, 18, 19, 20, 24, 25, 30}  # eng gesetzte Zeilen: kein Wachstum über das Band hinaus
