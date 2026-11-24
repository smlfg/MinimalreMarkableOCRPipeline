"""Pass 9: multi-task multiline pages (markers, gaps, wraps, student errors)."""
from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())

# (name, steps, extra_gap_after_index or None, chains split indices)
PAGES: list[tuple[str, list[tuple[str, bool]], int | None, list[slice] | None]] = [
    (
        "tight_two_calcs",
        [
            (r"x+1=2", True),
            (r"x=1", True),
            (r"y+2=5", True),
            (r"y=3", True),
        ],
        None,
        [slice(0, 2), slice(2, 4)],
    ),
    (
        "markers_ab",
        [
            (r"a)\ 3a+6=12", True),
            (r"a=2", True),
            (r"b)\ 2b-1=7", True),
            (r"b=4", True),
        ],
        1,
        [slice(0, 2), slice(2, 4)],
    ),
    (
        "markers_num",
        [
            (r"1)\ n+3=8", True),
            (r"n=5", True),
            (r"2.\ m-2=1", True),
            (r"m=3", True),
        ],
        1,
        [slice(0, 2), slice(2, 4)],
    ),
    (
        "large_gap_pair",
        [
            (r"2x+4=10", True),
            (r"x=3", True),
            (r"5t-5=15", True),
            (r"t=4", True),
        ],
        1,
        [slice(0, 2), slice(2, 4)],
    ),
    (
        "trailing_wrap",
        [
            (r"\frac{1}{4}+\frac{1}{4}+", True),
            (r"\frac{2}{4}", True),
            (r"=\frac{1}{2}", True),
        ],
        None,
        None,
    ),
    (
        "student_wrong",
        [
            (r"(6+2)\cdot2=", True),
            (r"4", False),
        ],
        None,
        None,
    ),
    (
        "anti_domino",
        [
            (r"2(x+1)=8", True),
            (r"2x+2=8", True),
            (r"x=3", True),
        ],
        None,
        None,
    ),
    (
        "triple_stack",
        [
            (r"u^{2}=9", True),
            (r"u=3", True),
            (r"v^{2}=16", True),
            (r"v=4", True),
        ],
        None,
        [slice(0, 2), slice(2, 4)],
    ),
    (
        "mixed_wrap_marker",
        [
            (r"3+5=", True),
            (r"8", True),
            (r"1)\ c+d=5", True),
            (r"c=2", True),
        ],
        1,
        [slice(0, 2), slice(2, 4)],
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
    for i, (name, steps, extra_after, chain_slices) in enumerate(PAGES[: CFG["n_pages"]]):
        pid = f"MMT_{i+1:02d}"
        y = 40
        line_rows = []
        chain_ids: list[str] = []
        latexes = []
        ys = []
        for j, (latex, math_ok) in enumerate(steps):
            if extra_after is not None and j == extra_after + 1:
                y += 130
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
            chain_ids.append(lid)
            ys.append(y)
            latexes.append(latex)
            y += lh + gap
        page_rel = f"pages/{pid}.png"
        _render_page(ROOT / page_rel, latexes, ys, lh)
        if chain_slices:
            chains_gt = [chain_ids[sl] for sl in chain_slices]
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
        rng.randint(0, 9)
    out = ROOT / "pages.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {len(rows)} pages -> {out}")


if __name__ == "__main__":
    main()