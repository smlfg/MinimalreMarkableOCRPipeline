"""Pass 4: scaled Level 4–5 synthetics (dev + holdout) for live TexTeller CPU."""
from __future__ import annotations

import hashlib
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
    out = [
        (r"\int x\,dx", True, [r"\int x dx", r"\int x \mathrm{d}x"]),
        (r"\int x dx", True, [r"\int x\,dx"]),
        (r"\int x \mathrm{d}x", True, [r"\int x\,dx"]),
        (r"\int t\,dt", True, []),
        (r"\int u\,du", True, []),
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
        (r"\int_0^2 x\,dx=2", True, []),
        (r"\int_0^2 x\,dx=3", False, []),
        (r"\int_0^3 2\,dx=6", True, []),
        (r"\int_0^1 e^x\,dx=e-1", True, []),
        (r"\int_0^1 e^x\,dx=e", False, []),
        (r"\int_0^{\pi/2} \cos x\,dx=1", True, []),
        (r"\int_0^{\pi/2} \cos x\,dx=0", False, []),
        (r"\int_1^e \frac{1}{x}\,dx=1", True, []),
        (r"\int_1^e \frac{1}{x}\,dx=0", False, []),
        (r"\int_0^1 x^2\,dx=\frac{1}{3}", True, []),
        (r"\int_0^1 x^3\,dx=\frac{1}{4}", True, []),
    ]
    rng.shuffle(out)
    return out


def _matrix_specs(rng: random.Random) -> list[tuple[str, bool, list[str]]]:
    out = [
        (r"\begin{pmatrix}1&0\\0&1\end{pmatrix}", True, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}", True, []),
        (r"\begin{bmatrix}1&2\\3&4\end{bmatrix}", True, []),
        (r"\begin{vmatrix}1&2\\3&4\end{vmatrix}", True, []),
        (r"\begin{pmatrix}-1&2\\3&0\end{pmatrix}", True, []),
        (r"\begin{bmatrix}1&0\\0&1\end{bmatrix}", True, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}=\begin{pmatrix}1&2\\3&5\end{pmatrix}", False, []),
        (r"\begin{pmatrix}2&0\\0&1\end{pmatrix}=\begin{pmatrix}1&0\\0&1\end{pmatrix}", False, []),
        (r"\begin{vmatrix}2&0\\0&3\end{vmatrix}=\begin{vmatrix}6&0\\0&6\end{vmatrix}", False, []),
        (r"\det\begin{pmatrix}1&2\\3&4\end{pmatrix}=-2", True, []),
        (r"\det\begin{pmatrix}1&2\\3&4\end{pmatrix}=2", False, []),
        (r"\det\begin{pmatrix}2&0\\0&3\end{pmatrix}=6", True, []),
        (r"\det\begin{pmatrix}2&0\\0&3\end{pmatrix}=5", False, []),
        (r"\begin{pmatrix}1\\2\end{pmatrix}+\begin{pmatrix}3\\4\end{pmatrix}=\begin{pmatrix}5\\5\end{pmatrix}", False, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}\cdot\begin{pmatrix}1\\0\end{pmatrix}=\begin{pmatrix}2\\3\end{pmatrix}", False, []),
        (r"\begin{pmatrix}0&1\\1&0\end{pmatrix}^2=\begin{pmatrix}1&0\\0&1\end{pmatrix}", True, []),
        (r"\begin{pmatrix}0&1\\1&0\end{pmatrix}^2=\begin{pmatrix}0&1\\1&0\end{pmatrix}", False, []),
        (r"\begin{pmatrix}1&2&3\\4&5&6\end{pmatrix}", True, []),
        (r"\begin{bmatrix}1&2&3\\4&5&6\\7&8&9\end{bmatrix}", True, []),
        (r"\begin{vmatrix}a&b\\c&d\end{vmatrix}", True, []),
        (r"\det\begin{pmatrix}3&1\\2&4\end{pmatrix}=10", True, []),
        (r"\det\begin{pmatrix}3&1\\2&4\end{pmatrix}=11", False, []),
        (r"\begin{pmatrix}1&0&0\\0&2&0\\0&0&3\end{pmatrix}", True, []),
        (r"\operatorname{det}\begin{pmatrix}1&2\\3&4\end{pmatrix}=-2", True, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}+\begin{pmatrix}0&0\\0&0\end{pmatrix}=\begin{pmatrix}1&2\\3&4\end{pmatrix}", True, []),
        (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}+\begin{pmatrix}0&0\\0&0\end{pmatrix}=\begin{pmatrix}2&2\\3&4\end{pmatrix}", False, []),
        (r"\begin{bmatrix}2&1\\1&2\end{bmatrix}", True, []),
        (r"\det\begin{vmatrix}2&0\\0&3\end{vmatrix}=6", True, []),
        (r"\det\begin{vmatrix}2&0\\0&3\end{vmatrix}=5", False, []),
        (r"\begin{pmatrix}x&1\\0&x\end{pmatrix}", True, []),
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
        (r"\tan(0)=0", True, []),
        (r"\tan(0)=1", False, []),
        (r"\sec x=\frac{1}{\cos x}", True, []),
        (r"\cot x=\frac{\cos x}{\sin x}", True, []),
        (r"\sin(2x)=2\sin x\cos x", True, []),
        (r"\cos^2(x)-\sin^2(x)=\cos(2x)", True, []),
        (r"\sin(\frac{\pi}{6})=\frac{1}{2}", True, []),
        (r"\sin(\frac{\pi}{6})=\frac{\sqrt{3}}{2}", False, []),
        (r"\cos(\frac{\pi}{3})=\frac{1}{2}", True, []),
        (r"\cos(\frac{\pi}{3})=0", False, []),
        (r"\tan(\pi)=0", True, []),
        (r"\tan(\pi)=1", False, []),
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
        (r"\lim_{x\to 0}\frac{\sin x}{x}=1", True, []),
        (r"\lim_{x\to 0}\frac{\sin x}{x}=0", False, []),
        (r"\sum_{k=1}^{n} k=\frac{n(n+1)}{2}", True, []),
        (r"\sum_{k=1}^{n} k=n^2", False, []),
        (r"\infty+\infty=\infty", True, []),
        (r"\infty\cdot 0=1", False, []),
        (r"\alpha+\beta=\gamma", True, []),
        (r"\theta=90^\circ", True, []),
        (r"\theta=90^\circ=100^\circ", False, []),
        (r"\phi=\frac{1+\sqrt{5}}{2}", True, []),
        (r"\phi=2", False, []),
        (r"Re(z)+Im(z)=z", True, []),
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
            out.append((f"L45L_{n:03d}", latex, mc, bucket, variants))
            added += 1
        if added < want[bucket]:
            raise RuntimeError(f"bucket {bucket}: need {want[bucket]}, got {added}")
    assert len({s[1] for s in out}) == len(out) == target
    by_bucket: dict[str, list[Spec]] = defaultdict(list)
    for s in out:
        by_bucket[s[3]].append(s)
    for b, items in by_bucket.items():
        if not any(not x[2] for x in items):
            raise RuntimeError(f"bucket {b} has no math_correct=False rows")
    return out


def _stratified_split(
    specs: list[Spec], n_dev: int, n_holdout: int, seed: int
) -> dict[str, str]:
    total = n_dev + n_holdout
    by_bucket: dict[str, list[Spec]] = defaultdict(list)
    for spec in specs:
        by_bucket[spec[3]].append(spec)
    split_rng = random.Random(seed)
    dev: list[Spec] = []
    holdout: list[Spec] = []
    for bucket in sorted(by_bucket.keys()):
        items = list(by_bucket[bucket])
        split_rng.shuffle(items)
        n = len(items)
        n_ho_f = round(n * n_holdout / total)
        if n >= 2 and n_ho_f == 0:
            n_ho_f = 1
        if n_ho_f >= n:
            n_ho_f = n - 1 if n > 1 else 0
        holdout.extend(items[:n_ho_f])
        dev.extend(items[n_ho_f:])
    while len(dev) > n_dev:
        holdout.append(dev.pop())
    while len(dev) < n_dev and holdout:
        dev.append(holdout.pop(split_rng.randrange(len(holdout))))
    overlap = {s[1] for s in dev} & {s[1] for s in holdout}
    assert not overlap, f"dev/holdout gt_latex overlap: {overlap}"
    assign = {spec[0]: "dev" for spec in dev} | {spec[0]: "holdout" for spec in holdout}
    assert len(dev) == n_dev and len(holdout) == n_holdout
    return assign


def _pad_jitter(row_id: str, base: float) -> float:
    if not CFG.get("render_variation"):
        return base
    h = int(hashlib.sha256(row_id.encode()).hexdigest()[:8], 16)
    return base + (h % 7) * 0.01 - 0.03


def _render_mathtext(latex: str, path: Path, pad: float = 0.08) -> bool:
    try:
        w = min(16, max(4, len(latex) * 0.1))
        h = 1.35 if "\\begin" in latex else 1.25
        dpi = 132 if "\\begin" in latex else 120
        fig = plt.figure(figsize=(w, h), dpi=dpi)
        fig.patch.set_facecolor("white")
        fig.text(0.02, 0.5, f"${latex}$", fontsize=13, va="center", ha="left")
        fig.savefig(path, bbox_inches="tight", pad_inches=pad, facecolor="white")
        plt.close(fig)
        return True
    except Exception:
        plt.close("all")
        return False


def _render_text(latex: str, path: Path, pad: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(min(14, max(5, len(latex) * 0.07)), 1.1), dpi=120)
    fig.patch.set_facecolor("white")
    fig.text(0.02, 0.5, latex, fontsize=11, va="center", ha="left", family="monospace")
    fig.savefig(path, bbox_inches="tight", pad_inches=pad, facecolor="white")
    plt.close(fig)


def _render(latex: str, path: Path, row_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base_pad = 0.12 if "\\begin" in latex else 0.08
    pad = max(0.04, _pad_jitter(row_id, base_pad))
    if not _render_mathtext(latex, path, pad):
        _render_text(latex, path, pad)


def main() -> None:
    seed = CFG["seed"]
    n_dev, n_holdout = CFG["n_dev"], CFG["n_holdout"]
    rng = random.Random(seed)
    specs = _build_specs(rng, n_dev + n_holdout)
    assign = _stratified_split(specs, n_dev, n_holdout, seed)
    rows = []
    for tid, latex, mc, bucket, variants in specs:
        split = assign[tid]
        rid = f"{split}_{tid}"
        rel = f"images/{rid}.png"
        _render(latex, ROOT / rel, rid)
        row = {
            "id": rid,
            "split": split,
            "template_id": tid,
            "bucket": bucket,
            "gt_latex": latex,
            "math_correct": mc,
            "png": rel,
            "synthetic_rendered": True,
        }
        if variants:
            row["variants"] = variants
        rows.append(row)
    for split in ("dev", "holdout"):
        part = [r for r in rows if r["split"] == split]
        (ROOT / f"{split}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part)
        )
    print(f"wrote {len(rows)} lines ({n_dev} dev, {n_holdout} holdout)")


if __name__ == "__main__":
    main()