"""Synthetic multi-line calculation pages for Pass 5 E2E (fixed seed)."""
from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())

# Each page: list of (latex, y_order) steps; False = intentional student error preserved in GT
PAGES: list[tuple[str, list[tuple[str, bool]]]] = [
    (
        "cube_expand",
        [
            (r"(x+y)^3", True),
            (r"=x^3+3x^2y+3xy^2+y^3", True),
        ],
    ),
    (
        "frac_add",
        [
            (r"\frac{1}{2}+\frac{1}{3}", True),
            (r"=\frac{3}{6}+\frac{2}{6}", True),
            (r"=\frac{5}{6}", True),
        ],
    ),
    (
        "trailing_ops",
        [
            (r"2+3=", True),
            (r"5", True),
        ],
    ),
    (
        "k25_style",
        [
            (r"17\cdot3", True),
            (r"3\cdot10+3\cdot7", True),
            (r"30+21", True),
            (r"41", False),
        ],
    ),
    (
        "linear_ok",
        [
            (r"3x+5=20", True),
            (r"3x=15", True),
            (r"x=5", True),
        ],
    ),
    (
        "linear_err",
        [
            (r"4x-7=2x+3", True),
            (r"2x=-4", True),
            (r"x=-2", True),
        ],
    ),
    (
        "two_on_page",
        [
            (r"5x+10=35", True),
            (r"5x=25", True),
            (r"x=5", True),
            (r"2^{3}\cdot2^{2}", True),
            (r"=2^{5}", True),
            (r"=32", True),
        ],
    ),
    (
        "power_chain",
        [
            (r"2^{3}\cdot2^{2}", True),
            (r"=2^{5}", True),
            (r"=32", True),
        ],
    ),
    (
        "power_err",
        [
            (r"2^{3}\cdot2^{2}", True),
            (r"=2^{6}", False),
            (r"=64", False),
        ],
    ),
    (
        "quad_steps",
        [
            (r"x^{2}-4=0", True),
            (r"x^{2}=4", True),
            (r"(x-2)(x+2)=0", True),
        ],
    ),
    (
        "decimal_chain",
        [
            (r"0.5x+1=3", True),
            (r"0.5x=2", True),
            (r"x=4", True),
        ],
    ),
    (
        "anti_domino_uncertain",
        [
            (r"3(x-2)=2x+1", True),
            (r"3x-2=2x+1", True),
            (r"x=3", True),
        ],
    ),
]


def _render_line(latex: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(min(12, max(4, len(latex) * 0.09)), 1.0), dpi=120)
    fig.patch.set_facecolor("white")
    fig.text(0.02, 0.5, f"${latex}$", fontsize=13, va="center", ha="left")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)


def _render_page(path: Path, lines: list[str], ys: list[int], lh: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1400, max(ys) + lh + 40
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_facecolor("white")
    for latex, y in zip(lines, ys):
        fig.text(0.05, 1 - (y + lh / 2) / h, f"${latex}$", fontsize=14, va="center", ha="left")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def main() -> None:
    rng = random.Random(CFG["seed"])
    lh = CFG["line_height_px"]
    gap = CFG["line_gap_px"]
    x0 = CFG["x_start"]
    rows = []
    for i, (name, steps) in enumerate(PAGES[: CFG["n_pages"]]):
        pid = f"ML_{i+1:02d}"
        y = 40
        line_rows = []
        ys = []
        latexes = []
        chain_ids = []
        for j, (latex, math_ok) in enumerate(steps):
            if name == "two_on_page" and j == 3:
                y += 130  # separate exercises on one page (anti-domino gap)
            lid = f"{pid}_l{j+1}"
            rel = f"lines/{pid}_l{j+1}.png"
            _render_line(latex, ROOT / rel)
            line_rows.append(
                {
                    "id": lid,
                    "latex_gt": latex,
                    "png": rel,
                    "y": y,
                    "h": lh,
                    "x": x0,
                    "math_correct": math_ok,
                }
            )
            ys.append(y)
            latexes.append(latex)
            chain_ids.append(lid)
            y += lh + gap
        page_rel = f"pages/{pid}.png"
        _render_page(ROOT / page_rel, latexes, ys, lh)
        # two_on_page is two chains on one page
        if name == "two_on_page":
            chains_gt = [chain_ids[:3], chain_ids[3:]]
        else:
            chains_gt = [chain_ids]
        rows.append(
            {
                "id": pid,
                "name": name,
                "page_png": page_rel,
                "lines": line_rows,
                "chains_gt": chains_gt,
                "seed": CFG["seed"],
                "student_error_preserved": any(not s[1] for s in steps),
            }
        )
        rng.randint(0, 9)  # consume for stable extend hook
    out = ROOT / "pages.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {len(rows)} pages -> {out}")


if __name__ == "__main__":
    main()