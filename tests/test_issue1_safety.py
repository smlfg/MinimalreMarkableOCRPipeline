"""Issue #1 (https://github.com/smlfg/MinimalreMarkableOCRPipeline/issues/1): OCR-Unsicherheit
von mathematischer Wahrheit trennen; Reparaturen nie als sicher ausgeben.

Regressionstests mit injizierten TT/GLM-Ausgaben (keine laufenden Modelle)."""
from PIL import Image

from ocr.coherence import coherent
from ocr.formula import recognize


def _png(tmp_path):
    p = tmp_path / "x.png"
    Image.new("L", (60, 30), 255).save(p)
    return str(p)


def _tt(reading):
    return lambda path: (reading, 0.1)


def _glm(reading):
    return lambda img: (reading, 0.1)


# --- coherent() (reine Logik, kein Bild) ---


def test_coherent_false_but_consistent_is_trusted():
    # Beide Engines lesen uebereinstimmend "7+5=13" -> keine Reparatur, trusted (OCR-sicher),
    # obwohl die Rechnung falsch ist. Die Falschheit gehoert in math_status, nicht in uncertain.
    latex, repair, trusted = coherent("7+5=13", "7+5=13")
    assert latex == "7+5=13"
    assert repair is None
    assert trusted is True


def test_coherent_repair_is_never_trusted():
    # Verwechslungspaar 2->z, von der Zweitmeinung (GLM liest "za") korroboriert:
    # die Reparatur "2a -> za" darf NICHT trusted=True liefern (ADR-007).
    latex, repair, trusted = coherent("2a", "za")
    assert latex == "za"
    assert repair == "2a -> za"
    assert trusted is False


def test_coherent_second_none_not_truth_driven():
    # Ohne Zweitmeinung darf closed_truth NICHT ueber trusted entscheiden (Issue #1).
    assert coherent("7+5=12", None)[2] is False   # wahr
    assert coherent("7+5=13", None)[2] is False   # falsch


# --- recognize() (injizierte Engines) ---


def test_false_but_consistent_ocr_certain_math_false(tmp_path):
    out = recognize(_png(tmp_path), _tt("7+5=13"), _glm("7+5=13"))
    assert out["latex"] == "7+5=13"
    assert out["uncertain"] is False       # OCR ist sich sicher
    assert out["math_status"] is False     # die Rechnung ist falsch
    assert out["repair"] is None


def test_engines_disagree_uncertain_even_if_alt_true(tmp_path):
    # 7+5=13 (falsch) vs 7+5=12 (wahr): uneinig -> unsicher, die wahre Alternative wird NICHT
    # still zur Primaerlesart gemacht.
    out = recognize(_png(tmp_path), _tt("7+5=13"), _glm("7+5=12"))
    assert out["latex"] == "7+5=13"        # Primaerlesart bleibt erhalten
    assert out["uncertain"] is True
    assert out["alt"] == "7+5=12"          # Zweitmeinung als Alternative dokumentiert
    assert out["math_status"] is False     # Rechenwahrheit getrennt, beeinflusst uncertain nicht


def test_repair_implies_uncertain_even_if_corroborated(tmp_path):
    out = recognize(_png(tmp_path), _tt("2a"), _glm("za"))
    assert out["repair"] == "2a -> za"
    assert out["uncertain"] is True        # Reparatur ist immer unsicher (ADR-007)
    assert out["latex"] == "za"


def test_false_student_solution_not_silently_corrected(tmp_path):
    # "7+5=13" darf durch kein Verwechslungspaar zu etwas Wahrem umgedichtet werden:
    # es bleibt unveraendert und (bei Einigkeit) OCR-sicher, aber math_status=False.
    out = recognize(_png(tmp_path), _tt("7+5=13"), _glm("7+5=13"))
    assert out["latex"] == "7+5=13"
    assert out["repair"] is None
    assert out["math_status"] is False
    assert out["uncertain"] is False


def test_correct_equation_math_status_true(tmp_path):
    out = recognize(_png(tmp_path), _tt("7+5=12"), _glm("7+5=12"))
    assert out["latex"] == "7+5=12"
    assert out["uncertain"] is False
    assert out["math_status"] is True
