"""Self-contained synthetic math line dataset (matplotlib mathtext, no sibling-repo handwriting)."""
from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())


def _build_specs(rng: random.Random) -> list[tuple[str, str, bool]]:
    """Return (template_id, gt_latex, math_correct) — 60 unique structures."""
    out: list[tuple[str, str, bool]] = []
    n = 0

    def add(latex: str, ok: bool) -> None:
        nonlocal n
        n += 1
        out.append((f"T{n:03d}", latex, ok))

    for a in (2, 3, 5):
        b = rng.randint(3, 9)
        add(rf"\frac{{{a}}}{{{b}}}", True)
    for a in (2, 3, 4, 5):
        e = rng.randint(2, 4)
        add(rf"{a}^{{{e}}}", True)
        add(rf"{a}^{{{e}}}={a**e}", True)
        add(rf"{a}^{{{e}}}={a**e + 1}", False)
    for a, b in ((7, 5), (8, 3), (9, 6), (11, 4)):
        add(rf"{a}+{b}={a+b}", True)
        add(rf"{a}+{b}={a+b+1}", False)
    for a in (4, 9, 16, 25):
        r = int(a**0.5)
        add(rf"\sqrt{{{a}}}={r}", True)
    for a, b, c in ((3, 4, 12), (5, 6, 30), (2, 7, 14)):
        add(rf"{a}\cdot{b}={c}", True)
    add(r"0.5+0.5=1", True)
    add(r"0.5\cdot 2=1", True)
    add(r"3^{2}\cdot3^{3}=3^{5}", True)
    add(r"3^{2}\cdot3^{3}=35", False)
    add(r"2^{3}\cdot2^{2}=2^{5}", True)
    add(r"2^{3}\cdot2^{2}=25", False)
    add(r"\frac{1}{2}+\frac{1}{3}=\frac{5}{6}", True)
    add(r"\frac{1}{2}+\frac{1}{3}=\frac{2}{5}", False)
    for a, b, c in ((2, 3, 5), (4, 1, 3), (6, 2, 4)):
        add(rf"({a}+{b})\cdot2={c}", (a + b) * 2 == c)
    while len(out) < 60:
        a, b = rng.randint(2, 11), rng.randint(2, 9)
        add(rf"{a}-{b}={a-b}", True)
    return out[:60]


def _render(latex: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(min(12, max(4, len(latex) * 0.15)), 1.2), dpi=120)
    fig.patch.set_facecolor("white")
    fig.text(0.02, 0.5, f"${latex}$", fontsize=14, va="center", ha="left")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


def main() -> None:
    rng = random.Random(CFG["seed"])
    specs = _build_specs(rng)
    n_train, n_dev = CFG["n_train"], CFG["n_dev"]
    rows = []
    for i, (tid, latex, mc) in enumerate(specs):
        split = "train" if i < n_train else "dev"
        rid = f"{split}_{tid}"
        rel = f"images/{rid}.png"
        _render(latex, ROOT / rel)
        rows.append({
            "id": rid,
            "split": split,
            "template_id": tid,
            "gt_latex": latex,
            "math_correct": mc,
            "png": rel,
        })
    for split in ("train", "dev"):
        part = [r for r in rows if r["split"] == split]
        (ROOT / f"{split}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part))
    print(f"wrote {len(rows)} lines ({n_train} train, {n_dev} dev)")


if __name__ == "__main__":
    main()