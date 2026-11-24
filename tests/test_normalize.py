"""Normalisierungs-Regressionen: TexTeller-Artefakte muessen zu strukturgleichem LaTeX
kollabieren (ADR-008 metrik v2; einseitige Quelle mit der Pipeline)."""
from ocr.latex import normalize, same


def test_font_size_commands_removed():
    assert normalize(r"\Large x") == "x"
    assert normalize(r"\mbox{\Large$\int$}x") == r"\intx"


def test_mbox_text_mathrm_unwrapped():
    assert normalize(r"\ln\mbox{($x$)}") == r"\ln(x)"
    assert normalize(r"\text{(}x\text{)}") == "(x)"
    assert normalize(r"\mathrm{d}x") == "dx"


def test_function_name_in_text_wrapper():
    assert normalize(r"\text{sin}(x)") == r"\sin(x)"
    assert normalize(r"\text{cos}(x)") == r"\cos(x)"


def test_single_column_array_unwrapped():
    assert normalize(r"\begin{array}{c}\int x\,dx\end{array}") == r"\intxdx"
    # mehrspaltige Umgebung (Matrix) bleibt erhalten
    assert "array" in normalize(r"\begin{array}{cc}a&b\\c&d\end{array}")


def test_integral_texter_artifact_same():
    assert same(r"\int_{0}^{1}x^{2}\,dx", r"\mbox{\Large$\int$}_{0}^{1}x^{2}\,dx")
    assert same(r"\int\frac{1}{x}\,dx=\ln(x)",
                r"\begin{array}{c}\int\!\!\frac{1}{x}\,dx=\ln\mbox{($x$)}\end{array}")


def test_trig_texter_artifact_same():
    assert same(r"\sin(2x)=2\sin(x)\cos(x)",
                r"\sin\text{(2}x\text{)}=2\text{sin(}x\text{)}\text{cos(}x\text{)}")
