"""Level 4–5 synthetic formula lines: integrals, matrices, trig, special (matplotlib mathtext)."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())

Spec = tuple[str, str, bool, str, list[str]]  # id stub, gt_latex, math_correct, bucket, variants


def _integral_specs(rng: random.Random) -> list[tuple[str, bool, list[str]]]:
    """(gt_latex, math_correct, variants)."""
    out = [
        (r"\int x\,dx", True, [r"\int x dx", r"\int x \mathrm{d}x"]),
        (r"\int x dx", True, [r"\int x\,dx"]),
        (r"\int x \mathrm{d}x", True, [r"\int x\,dx"]),
        (r"\int t\,dt", True, []),
        (r"\int_0^1 x\,dx=\frac{1}{2}", True, []),
        (r"\int_0^1 x\,dx=1", False, []),
        (r"\int_0^1 1\,dx=1", True, []),
        (r"\int_0^1 1\,dx=0", False, []),
        (r"\int_1^2 x\,dx=\frac{3}{2}", True, []),
        (r"\int_1^2 x\,dx=1", False, []),
        (r"\int_a^b f(x)\,dx", True, []),
        (r"\int_0^{\pi} \sin x\,dx=2", True, []),
        (r"\int_0^{\pi} \sin x\,dx=0", False, []),
        (r"\int_{-1}^1 x^2\,dx=\frac{2}{3}", True, []),
        (r"\int_{-1}^1 x^2\,dx=1", False, []),
        (r"\int_0^2 3\,dx=7", False, []),
        (r"\int_0^2 3\,dx=6", True, []),
        (r"\int_0^1 2x\,dx=1", True, []),
    ]
    rng.shuffle(out)
    return out


def _matrix_specs(rng: random.Random) -> list[tuple[str, bool, list[str]]]:
    """Prefer scalar \\det checks and bare matrix displays — SymPy matrix chains often not closed_truth-able."""
    out = [
        (r"\begin{pmatrix}1&0\\0&1\end{pmatrix}", True, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}", True, []),
        (r"\begin{bmatrix}1&2\\3&4\end{bmatrix}", True, []),
        (r"\begin{vmatrix}1&2\\3&4\end{vmatrix}", True, []),
        (r"\begin{pmatrix}-1&2\\3&0\end{pmatrix}", True, []),
        (r"\begin{bmatrix}1&0\\0&1\end{bmatrix}", True, []),
        (
            r"\begin{pmatrix}1&2\\3&4\end{pmatrix}=\begin{pmatrix}1&2\\3&5\end{pmatrix}",
            False,
            [],
        ),
        (
            r"\begin{pmatrix}2&0\\0&1\end{pmatrix}=\begin{pmatrix}1&0\\0&1\end{pmatrix}",
            False,
            [],
        ),
        (
            r"\begin{vmatrix}2&0\\0&3\end{pmatrix}=\begin{vmatrix}6&0\\0&6\end{vmatrix}",
            False,
            [],
        ),
        (r"\det\begin{pmatrix}1&2\\3&4\end{pmatrix}=-2", True, []),
        (r"\det\begin{pmatrix}1&2\\3&4\end{pmatrix}=2", False, []),
        (r"\det\begin{pmatrix}2&0\\0&3\end{pmatrix}=6", True, []),
        (r"\det\begin{pmatrix}2&0\\0&3\end{pmatrix}=5", False, []),
        (r"\begin{pmatrix}1\\2\end{pmatrix}+\begin{pmatrix}3\\4\end{pmatrix}=\begin{pmatrix}5\\5\end{pmatrix}", False, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}\cdot\begin{pmatrix}1\\0\end{pmatrix}=\begin{pmatrix}2\\3\end{pmatrix}", False, []),
        (r"\begin{pmatrix}0&1\\1&0\end{pmatrix}^2=\begin{pmatrix}1&0\\0&1\end{pmatrix}", True, []),
        (r"\begin{pmatrix}0&1\\1&0\end{pmatrix}^2=\begin{pmatrix}0&1\\1&0\end{pmatrix}", False, []),
    ]
    rng.shuffle(out)
    return out


def _trig_specs(rng: random.Random) -> list[tuple[str, bool, list[str]]]:
    out = [
        (r"\cos x", True, [r"\cos(x)"]),
        (r"\cos(x)", True, [r"\cos x"]),
        (r"\sin x", True, [r"\sin(x)"]),
        (r"\sin(x)", True, [r"\sin x"]),
        (r"\tan(\frac{\pi}{4})=1", True, []),
        (r"\cos(\pi)=-1", True, []),
        (r"\cos(\pi)=1", False, []),
        (r"\sin(\frac{\pi}{2})=1", True, []),
        (r"\sin(\frac{\pi}{2})=0", False, []),
        (r"\cos(0)=1", True, []),
        (r"\cos(0)=0", False, []),
        (r"\sin^2(x)+\cos^2(x)=1", True, [r"\sin^{2}(x)+\cos^{2}(x)=1"]),
        (r"\sin^{2}(x)+\cos^{2}(x)=1", True, [r"\sin^2(x)+\cos^2(x)=1"]),
        (r"\sin^2(x)=1-\cos^2(x)", True, []),
        (r"\tan x=\frac{\sin x}{\cos x}", True, []),
        (r"\cos(2x)=2\cos^2(x)-1", True, []),
        (r"\sin(\pi)=0", True, []),
        (r"\sin(\pi)=1", False, []),
    ]
    rng.shuffle(out)
    return out


def _special_specs(rng: random.Random) -> list[tuple[str, bool, list[str]]]:
    out = [
        (r"e^{i\pi}+1=0", True, []),
        (r"e^{i\pi}=1", False, []),
        (r"\pi r^2", True, []),
        (r"i^2=-1", True, [r"\mathrm{i}^2=-1"]),
        (r"\mathrm{i}^2=-1", True, [r"i^2=-1"]),
        (r"e^{1}=e", True, [r"\mathrm{e}^{1}=\mathrm{e}"]),
        (r"\pi=4", False, []),
        (r"e=3", False, []),
        (r"i=1", False, []),
        (r"e^{i\pi}=-1", True, []),
        (r"e^{0}=1", True, []),
        (r"e^{0}=0", False, []),
        (r"\pi^2>9", True, []),
        (r"\pi^2=9", False, []),
        (r"e\cdot e=e^2", True, []),
        (r"e\cdot e=e^3", False, []),
        (r"2i+3i=5i", True, []),
        (r"2i+3i=6i", False, []),
    ]
    rng.shuffle(out)
    return out


def _build_specs(rng: random.Random, target: int) -> list[Spec]:
    pools = {
        "integral": _integral_specs(rng),
        "matrix": _matrix_specs(rng),
        "trig": _trig_specs(rng),
        "special": _special_specs(rng),
    }
    per_bucket = target // len(pools)
    remainder = target % len(pools)
    want = {b: per_bucket + (1 if i < remainder else 0) for i, b in enumerate(pools)}

    out: list[Spec] = []
    seen_latex: set[str] = set()
    n = 0
    for bucket in pools:
        added = 0
        for latex, mc, variants in pools[bucket]:
            if added >= want[bucket]:
                break
            if latex in seen_latex:
                continue
            seen_latex.add(latex)
            n += 1
            out.append((f"L45_{n:03d}", latex, mc, bucket, variants))
            added += 1
        if added < want[bucket]:
            raise RuntimeError(f"bucket {bucket}: need {want[bucket]}, got {added}")

    assert len({s[1] for s in out}) == len(out) == target
    # Every bucket has at least one false student equation
    by_bucket: dict[str, list[Spec]] = defaultdict(list)
    for s in out:
        by_bucket[s[3]].append(s)
    for b, items in by_bucket.items():
        if not any(not x[2] for x in items):
            raise RuntimeError(f"bucket {b} has no math_correct=False rows")
    return out


def _stratified_split(specs: list[Spec], n_train: int, n_dev: int, seed: int) -> dict[str, str]:
    total = n_train + n_dev
    by_bucket: dict[str, list[Spec]] = defaultdict(list)
    for spec in specs:
        by_bucket[spec[3]].append(spec)
    split_rng = random.Random(seed)
    train: list[Spec] = []
    dev: list[Spec] = []
    for bucket in sorted(by_bucket.keys()):
        items = list(by_bucket[bucket])
        split_rng.shuffle(items)
        n = len(items)
        n_dev_f = round(n * n_dev / total)
        if n >= 2 and n_dev_f == 0:
            n_dev_f = 1
        if n_dev_f >= n:
            n_dev_f = n - 1 if n > 1 else 0
        train.extend(items[: n - n_dev_f])
        dev.extend(items[n - n_dev_f :])
    while len(train) > n_train:
        dev.append(train.pop())
    while len(train) < n_train and dev:
        train.append(dev.pop(split_rng.randrange(len(dev))))
    overlap = {s[1] for s in train} & {s[1] for s in dev}
    assert not overlap, f"train/dev gt_latex overlap: {overlap}"
    assign = {spec[0]: "train" for spec in train} | {spec[0]: "dev" for spec in dev}
    assert len(train) == n_train and len(dev) == n_dev
    return assign


def _render_mathtext(latex: str, path: Path) -> bool:
    try:
        fig = plt.figure(figsize=(min(14, max(4, len(latex) * 0.11)), 1.25), dpi=120)
        fig.patch.set_facecolor("white")
        fig.text(0.02, 0.5, f"${latex}$", fontsize=13, va="center", ha="left")
        fig.savefig(path, bbox_inches="tight", pad_inches=0.08, facecolor="white")
        plt.close(fig)
        return True
    except Exception:
        plt.close("all")
        return False


def _render_text(latex: str, path: Path) -> None:
    """Fallback when mathtext cannot parse (e.g. \\begin{pmatrix})."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(min(14, max(5, len(latex) * 0.07)), 1.1), dpi=120)
    fig.patch.set_facecolor("white")
    fig.text(0.02, 0.5, latex, fontsize=11, va="center", ha="left", family="monospace")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)


def _render(latex: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _render_mathtext(latex, path):
        _render_text(latex, path)


def main() -> None:
    seed = CFG["seed"]
    n_train, n_dev = CFG["n_train"], CFG["n_dev"]
    rng = random.Random(seed)
    specs = _build_specs(rng, n_train + n_dev)
    assign = _stratified_split(specs, n_train, n_dev, seed)
    rows = []
    for tid, latex, mc, bucket, variants in specs:
        split = assign[tid]
        rid = f"{split}_{tid}"
        rel = f"images/{rid}.png"
        _render(latex, ROOT / rel)
        row = {
            "id": rid,
            "split": split,
            "template_id": tid,
            "bucket": bucket,
            "gt_latex": latex,
            "math_correct": mc,
            "png": rel,
        }
        if variants:
            row["variants"] = variants
        rows.append(row)
    for split in ("train", "dev"):
        part = [r for r in rows if r["split"] == split]
        (ROOT / f"{split}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part)
        )
    print(f"wrote {len(rows)} lines ({n_train} train, {n_dev} dev)")


if __name__ == "__main__":
    main()