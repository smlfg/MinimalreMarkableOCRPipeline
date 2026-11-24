"""Normalisierungs-Regressionen: TexTeller-Artefakte muessen zu strukturgleichem LaTeX
kollabieren (ADR-008 metrik v2; einseitige Quelle mit der Pipeline)."""
from ocr.latex import normalize, parse, same


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


# --- Matrizen / Robustheit (Pass 4) ---


def test_matrix_env_variants_equal():
    gt = r"\begin{pmatrix}1&2\\3&4\end{pmatrix}"
    for tt in (r"\left(\begin{array}{cc}1&2\\3&4\end{array}\right)",
               r"\left(\begin{matrix}1&2\\3&4\end{matrix}\right)",
               r"\left(\begin{smallmatrix}1&2\\3&4\end{smallmatrix}\right)"):
        assert same(gt, tt)
    assert not same(gt, r"\left(\begin{matrix}9&9\\9&9\end{matrix}\right)")


def test_matrix_determinant_vmatrix():
    # '|' um eine Matrix-Umgebung ist die Determinante, nicht Abs().
    assert same(r"\begin{vmatrix}1&2\\3&4\end{vmatrix}=-2",
                r"\left|\begin{matrix}1&2\\3&4\end{matrix}\right|=-2")


def test_matrix_compound_addition():
    gt = (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}+\begin{pmatrix}5&6\\7&8\end{pmatrix}"
          r"=\begin{pmatrix}6&8\\10&12\end{pmatrix}")
    tt = (r"\left(\begin{smallmatrix}1&2\\3&4\end{smallmatrix}\right)+"
          r"\left(\begin{smallmatrix}5&6\\7&8\end{smallmatrix}\right)="
          r"\left(\begin{smallmatrix}6&8\\10&12\end{smallmatrix}\right)")
    assert same(gt, tt)


def test_vspace_hspace_removed():
    assert normalize(r"\vspace{0.2cm}x") == "x"
    assert normalize(r"\hspace{1em}x") == "x"


def test_mathsf_texttt_textsf_unwrapped():
    assert normalize(r"\mathsf{a}") == "a"
    assert normalize(r"\texttt{12}") == "12"
    assert normalize(r"\textsf{x}") == "x"


def test_parse_handles_newlines_in_matrix():
    raw = "\n\\left(\n\\begin{array}\n{cc}1&2\\\\\n3&4\n\\end{array}\n\\right)"
    assert parse(raw) is not None
    assert same(r"\begin{pmatrix}1&2\\3&4\end{pmatrix}", raw)


def test_scalar_abs_not_changed_to_determinant():
    # '|x|' (Skalar-Betrag) darf NICHT zu vmatrix werden.
    assert r"\begin{vmatrix}" not in normalize(r"\left|x\right|")
