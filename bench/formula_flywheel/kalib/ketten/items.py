"""Ketten-Kalibrierung (ADR-009): kurze Rechenketten, ~Hälfte mit eingebautem Fehler.

Format nach ProcessBench (QwenLM/ProcessBench, Apache-2.0): steps[0] ist die gedruckte Aufgabe,
steps[1:] schreibt der Owner ab. label = Index des frühesten falschen Schritts, -1 = alles korrekt.
Ein Schritt, der mit "=" beginnt, setzt den vorigen Ausdruck fort (Termumformung).
Nur Formen, die der Validator prüfen kann (v_b: eine Variable, Grad <= 2, rationale Lösungen;
arithmetic: Zahlenterme). Keine Ableitungen, kein ± (Befund Validator-Probe 23.11.).
Eintrag: (id, topic, steps, label, error_kind)
"""
CHAINS = [
    # Lineare Gleichungen (v_b)
    ("K01", "linear", [r"3x+5=20", r"3x=15", r"x=5"], -1, None),
    ("K02", "linear", [r"4x-7=2x+3", r"2x=-4", r"x=-2"], 1, "Vorzeichen beim Seitenwechsel"),
    ("K03", "linear", [r"3(x-2)=2x+1", r"3x-6=2x+1", r"x=7"], -1, None),
    ("K04", "linear", [r"3(x-2)=2x+1", r"3x-2=2x+1", r"x=3"], 1, "Distributivgesetz"),
    ("K05", "linear", [r"0.5x+1=3", r"0.5x=2", r"x=4"], -1, None),
    ("K06", "linear", [r"5x+10=35", r"5x=25", r"x=125"], 2, "Divisionsregel"),
    ("K07", "linear", [r"\frac{x}{2}+3=7", r"\frac{x}{2}=4", r"x=8"], -1, None),
    ("K08", "linear", [r"\frac{x}{3}-1=2", r"\frac{x}{3}=3", r"x=3\cdot3", r"x=6"], 3, "Rechenfehler"),
    # Quadratische Gleichungen (v_b), Endform als Faktorform
    ("K09", "quadratisch", [r"x^{2}+6x=7", r"(x+3)^{2}=16", r"(x-1)(x+7)=0"], -1, None),
    ("K10", "quadratisch", [r"x^{2}+6x=7", r"(x+3)^{2}=10", r"(x+3)^{2}-10=0"], 1, "quadratische Ergänzung"),
    ("K11", "quadratisch", [r"x^{2}+3x=1", r"(x+\frac{3}{2})^{2}=\frac{13}{4}", r"(x+\frac{3}{2})^{2}-\frac{13}{4}=0"], -1, None),
    ("K12", "quadratisch", [r"x^{2}+3x=1", r"(x+\frac{3}{2})^{2}=\frac{18}{13}", r"(x+\frac{3}{2})^{2}-\frac{18}{13}=0"], 1, "quadratische Ergänzung"),
    ("K13", "quadratisch", [r"2x^{2}+3x-2=0", r"x^{2}+\frac{3}{2}x-1=0", r"(x+\frac{3}{4})^{2}=\frac{25}{16}", r"(x-\frac{1}{2})(x+2)=0"], -1, None),
    ("K14", "quadratisch", [r"2x^{2}+3x-2=0", r"x^{2}+\frac{3}{2}x-1=0", r"(x+\frac{3}{4})^{2}=\frac{25}{16}", r"(x-\frac{1}{2})(x-2)=0"], 3, "Vorzeichen in der Faktorform"),
    ("K15", "quadratisch", [r"x^{2}-4=0", r"x^{2}=4", r"(x-2)(x+2)=0"], -1, None),
    ("K16", "quadratisch", [r"x^{2}-9=0", r"x^{2}=9", r"x=3"], 2, "Wurzelziehen: zweite Lösung fehlt"),
    ("K17", "quadratisch", [r"x^{2}-5x+6=0", r"(x-\frac{5}{2})^{2}=\frac{1}{4}", r"(x-2)(x-3)=0"], -1, None),
    ("K18", "quadratisch", [r"x^{2}-5x+6=0", r"(x-\frac{5}{2})^{2}=\frac{1}{4}", r"(x-2)(x+3)=0"], 2, "Vorzeichen in der Faktorform"),
    ("K19", "quadratisch", [r"2x^{2}-1+3x=1", r"2x^{2}+3x=0", r"x(2x+3)=0"], 1, "Vorzeichen beim Seitenwechsel"),
    # Zahlenterme (arithmetic), Fortsetzung mit "="
    ("K20", "bruch", [r"\frac{1}{2}+\frac{1}{3}", r"=\frac{3}{6}+\frac{2}{6}", r"=\frac{5}{6}"], -1, None),
    ("K21", "bruch", [r"\frac{1}{2}+\frac{1}{3}", r"=\frac{2}{5}", r"=0.4"], 1, "Nenner addiert"),
    ("K22", "bruch", [r"\frac{3}{4}\cdot\frac{2}{9}", r"=\frac{6}{36}", r"=\frac{1}{6}"], -1, None),
    ("K23", "bruch", [r"\frac{3}{4}\cdot\frac{2}{9}", r"=\frac{6}{36}", r"=\frac{1}{3}"], 2, "falsch gekürzt"),
    ("K24", "zahl", [r"17\cdot3", r"=3\cdot10+3\cdot7", r"=51"], -1, None),
    ("K25", "zahl", [r"17\cdot3", r"=3\cdot10+3\cdot7", r"=30+21", r"=41"], 3, "Additionsfehler"),
    ("K26", "potenz", [r"2^{3}\cdot2^{2}", r"=2^{5}", r"=32"], -1, None),
    ("K27", "potenz", [r"2^{3}\cdot2^{2}", r"=2^{6}", r"=64"], 1, "Exponenten multipliziert"),
    ("K28", "zahl", [r"(-3)^{2}-4\cdot1\cdot(-2)", r"=-9+8", r"=-1"], 1, "Vorzeichen beim Quadrieren"),
]
