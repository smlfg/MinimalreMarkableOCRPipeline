"""Self-contained synthetic math line dataset (matplotlib mathtext, no sibling-repo handwriting)."""
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

Spec = tuple[str, str, bool, str]  # template_id, gt_latex, math_correct, family


def _build_specs(rng: random.Random) -> list[Spec]:
    """Return 60 unique (template_id, gt_latex, math_correct, family) rows."""
    out: list[Spec] = []
    n = 0

    def add(latex: str, ok: bool, family: str) -> None:
        nonlocal n
        n += 1
        out.append((f"T{n:03d}", latex, ok, family))

    for a in (2, 3, 5):
        b = rng.randint(3, 9)
        add(rf"\frac{{{a}}}{{{b}}}", True, "frac")
    for a in (2, 3, 4, 5):
        e = rng.randint(2, 4)
        add(rf"{a}^{{{e}}}", True, "power")
        add(rf"{a}^{{{e}}}={a**e}", True, "power")
        add(rf"{a}^{{{e}}}={a**e + 1}", False, "power")
    for a, b in ((7, 5), (8, 3), (9, 6), (11, 4)):
        add(rf"{a}+{b}={a+b}", True, "add")
        add(rf"{a}+{b}={a+b+1}", False, "add")
    for a in (4, 9, 16, 25):
        r = int(a**0.5)
        add(rf"\sqrt{{{a}}}={r}", True, "sqrt")
    for a, b, c in ((3, 4, 12), (5, 6, 30), (2, 7, 14)):
        add(rf"{a}\cdot{b}={c}", True, "cdot")
    add(r"0.5+0.5=1", True, "decimal")
    add(r"0.5\cdot 2=1", True, "decimal")
    add(r"3^{2}\cdot3^{3}=3^{5}", True, "power_mul")
    add(r"3^{2}\cdot3^{3}=35", False, "power_mul")
    add(r"2^{3}\cdot2^{2}=2^{5}", True, "power_mul")
    add(r"2^{3}\cdot2^{2}=25", False, "power_mul")
    add(r"\frac{1}{2}+\frac{1}{3}=\frac{5}{6}", True, "frac_eq")
    add(r"\frac{1}{2}+\frac{1}{3}=\frac{2}{5}", False, "frac_eq")
    for a, b, c in ((2, 3, 5), (4, 1, 3), (6, 2, 4)):
        add(rf"({a}+{b})\cdot2={c}", (a + b) * 2 == c, "paren")
    while len(out) < 60:
        a, b = rng.randint(2, 11), rng.randint(2, 9)
        add(rf"{a}-{b}={a-b}", True, "sub")
    return out[:60]


def _stratified_split(specs: list[Spec], n_train: int, n_dev: int, seed: int) -> dict[str, str]:
    """Per-family ~2/3 train, 1/3 dev; then reconcile to exact n_train / n_dev."""
    total = n_train + n_dev
    by_fam: dict[str, list[Spec]] = defaultdict(list)
    for spec in specs:
        by_fam[spec[3]].append(spec)
    split_rng = random.Random(seed)
    train: list[Spec] = []
    dev: list[Spec] = []
    for fam in sorted(by_fam.keys()):
        items = list(by_fam[fam])
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
    assign: dict[str, str] = {}
    for spec in train:
        assign[spec[0]] = "train"
    for spec in dev:
        assign[spec[0]] = "dev"
    assert len(train) == n_train and len(dev) == n_dev
    assert len(assign) == len(specs)
    return assign


def _render(latex: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(min(12, max(4, len(latex) * 0.15)), 1.2), dpi=120)
    fig.patch.set_facecolor("white")
    fig.text(0.02, 0.5, f"${latex}$", fontsize=14, va="center", ha="left")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


def main() -> None:
    seed = CFG["seed"]
    rng = random.Random(seed)
    specs = _build_specs(rng)
    n_train, n_dev = CFG["n_train"], CFG["n_dev"]
    assign = _stratified_split(specs, n_train, n_dev, seed)
    rows = []
    for tid, latex, mc, family in specs:
        split = assign[tid]
        rid = f"{split}_{tid}"
        rel = f"images/{rid}.png"
        _render(latex, ROOT / rel)
        rows.append({
            "id": rid,
            "split": split,
            "template_id": tid,
            "family": family,
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