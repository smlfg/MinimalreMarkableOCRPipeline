"""TexTeller CPU texttt/backslash matrix env repair (injected strings, no live model)."""
import pytest

from ocr.coherence import integral_eq_artifact, texttt_artifacts, tt_postprocess, tt_render_artifacts
from ocr.latex import same

DET_PRED = (
    r"\backslash\texttt{det}\backslash\texttt{begin}\{\texttt{pmatrix}\}"
    r"1\&2 \backslash\backslash 3\&4"
    r"\backslash\texttt{end}\{\texttt{pmatrix}\}\texttt{=-}2"
)
DET_GT = r"\det\begin{pmatrix}1&2\\3&4\end{pmatrix}=-2"

VMAT_PRED = (
    r"\backslash\mathtt{begin}\{\mathtt{vmatrix}\}\mathtt{1}\&2"
    r"\backslash\backslash 3 \&4\backslash\mathtt{end}\{\mathtt{vmatrix}\}"
)
VMAT_GT = r"\begin{vmatrix}1&2\\3&4\end{vmatrix}"

FUSED_PM_PRED = (
    r"\backslash\texttt{begin}\{\texttt{pmatrix}\}\texttt{162}\backslash\backslash 3 \texttt{64}"
    r"\backslash\texttt{end}\{\texttt{pmatrix}\}\texttt{=}"
    r"\backslash \texttt{begin}\{\texttt{pmatrix}\}\texttt{162}\backslash\backslash 3 \texttt{65}"
    r"\backslash\texttt{end}\{\texttt{pmatrix}\}"
)
FUSED_PM_GT = (
    r"\begin{pmatrix}1&2\\3&4\end{pmatrix}=\begin{pmatrix}1&2\\3&5\end{pmatrix}"
)

INTEGRAL_PRED = r"\int_{0}^{2}\!3\,dx\,{=6}"
INTEGRAL_GT = r"\int_0^2 3\,dx=6"


def _repair(latex: str) -> str:
    return tt_postprocess(latex)


MBOX_INT_PRED = r"\mbox{\Large$\int$}_{0}^{1}1\,dx=1"
MBOX_INT_GT = r"\int_0^1 1\,dx=1"
MATRIX_BACKSLASH_PRED = r"\begin{pmatrix}1&2\backslash \backslash 3&4\end{pmatrix}"
MATRIX_BACKSLASH_GT = r"\begin{pmatrix}1&2\\3&4\end{pmatrix}"
DET_BRACE_PRED = r"\det\begin{pmatrix}3&1\\2&4\end{pmatrix}{=}10"
DET_BRACE_GT = r"\det\begin{pmatrix}3&1\\2&4\end{pmatrix}=10"


def test_det_pmatrix_tt_garbage_matches_gt():
    rep = _repair(DET_PRED)
    assert same(DET_GT, rep)


def test_vmatrix_mattt_matches_gt():
    rep = _repair(VMAT_PRED)
    assert same(VMAT_GT, rep)


def test_false_student_cos_pi_unchanged():
    raw = r"\cos( \pi)=1"
    assert texttt_artifacts(raw) == raw
    assert integral_eq_artifact(raw) == raw


def test_euler_unchanged():
    raw = r"e^{i\pi}+1=0"
    assert _repair(raw) == raw
    assert same(raw, r"e^{i \pi}+1=0")


def test_fused_texttt_162_still_not_gt():
    """Partial repair only; must not invent matrix & separators from fused digits."""
    rep = _repair(FUSED_PM_PRED)
    assert same(FUSED_PM_GT, rep) is False
    assert "162" in rep


def test_integral_thin_space_eq_artifact():
    rep = _repair(INTEGRAL_PRED)
    assert same(INTEGRAL_GT, rep)


def test_mbox_large_integral_glyph():
    assert same(MBOX_INT_GT, tt_render_artifacts(MBOX_INT_PRED)) or same(MBOX_INT_GT, _repair(MBOX_INT_PRED))


def test_matrix_backslash_spaced_rows():
    rep = _repair(MATRIX_BACKSLASH_PRED)
    assert same(MATRIX_BACKSLASH_GT, rep)


def test_det_brace_eq_artifact():
    rep = _repair(DET_BRACE_PRED)
    assert same(DET_BRACE_GT, rep)


def test_text_sin_to_backslash_sin():
    raw = r"\text{sin}^{2}\left(x\right)+\text{cos}^{2}\left(x\right)=1"
    gt = r"\sin^2(x)+\cos^2(x)=1"
    assert same(gt, _repair(raw))


@pytest.mark.parametrize("a,b", [(r"\cos(\pi)=1", r"\cos(\pi)=1"), (r"e^{i\pi}=1", r"e^{i\pi}=1")])
def test_no_artifact_strings_identity(a, b):
    assert texttt_artifacts(a) == a
    assert same(a, b)