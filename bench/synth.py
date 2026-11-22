#!/usr/bin/env python3
"""Virtual-Pen curriculum & cached .rm -> .png dataset factory."""

import concurrent.futures, random, subprocess, sys, tempfile, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR.parent / "SchlangebeißtinSchwanz"))
import rm_canvas  # noqa: E402

CASES = [
    (1, "L1_01_four", "4", "4"),
    (1, "L1_02_digits", "1 2 3 4 5", "1 2 3 4 5"),
    (2, "L2_01_alnum", "3x", "3x"),
    (3, "L3_01_ops", "2x + 3 = 11", "2x + 3 = 11"),
    (4, "L4_01_power", "4\u00b2", "4^2"),
    (4, "L4_02_power_expr", "x\u00b2 + 3\u00b2 = 10", "x^2 + 3^2 = 10"),
]


def make_case(idx: int, rng: random.Random) -> tuple[int, int, int, int, str, str]:
    level = (idx % 4) + 1
    rm_seed, x0 = rng.randint(1, 999999), rng.randint(240, 420)
    if level == 1:
        s = " ".join(str(rng.randint(1, 999)) for _ in range(rng.randint(1, 3)))
        return idx, level, rm_seed, x0, s, s
    if level == 2:
        s = f"{rng.randint(2, 9)}{rng.choice('abxyz')}"
        return idx, level, rm_seed, x0, s, s
    if level == 3:
        s = f"{rng.randint(2, 9)}{rng.choice('abxyz')} {rng.choice('+-')} {rng.randint(1, 20)} = {rng.randint(1, 50)}"
        return idx, level, rm_seed, x0, s, s
    if rng.random() < 0.5:
        b = rng.randint(2, 9)
        return idx, level, rm_seed, x0, f"{b}\u00b2", f"{b}^2"
    v, c, rhs = rng.choice("abxyz"), rng.randint(2, 9), rng.randint(5, 99)
    return idx, level, rm_seed, x0, f"{v}\u00b2 + {c}\u00b2 = {rhs}", f"{v}^2 + {c}^2 = {rhs}"


def render_rm_png(
    draw_txt: str, png_out: Path, *, x0: int = 320, seed: int = 42, keep_rm_svg: bool = False
) -> tuple[int, int]:
    if keep_rm_svg:
        rm, svg = png_out.with_suffix(".rm"), png_out.with_suffix(".svg")
        rm_canvas.write_new_student_page([draw_txt], rm, x0=x0, seed=seed)
        subprocess.run(["rmc", "-t", "svg", str(rm), "-o", str(svg)], check=True, capture_output=True)
        subprocess.run(["rsvg-convert", "-b", "white", "-z", "2", str(svg), "-o", str(png_out)], check=True, capture_output=True)
        return rm.stat().st_size, png_out.stat().st_size
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        rm, svg = td_p / "p.rm", td_p / "p.svg"
        rm_canvas.write_new_student_page([draw_txt], rm, x0=x0, seed=seed)
        subprocess.run(["rmc", "-t", "svg", str(rm), "-o", str(svg)], check=True, capture_output=True)
        subprocess.run(["rsvg-convert", "-b", "white", "-z", "2", str(svg), "-o", str(png_out)], check=True, capture_output=True)
        return rm.stat().st_size, png_out.stat().st_size


def _render_task(task: tuple[Path, int, int, int, int, str, str]) -> tuple[str, int, int, str]:
    bench_dir, idx, level, rm_seed, x0, draw_txt, gt = task
    cid = f"case_{idx:05d}_L{level}"
    render_rm_png(draw_txt, bench_dir / f"{cid}.png", x0=x0, seed=rm_seed)
    return cid, level, rm_seed, gt


def ensure_dataset(bench_dir: Path, n: int, seed: int, workers: int) -> list[tuple[str, int, int, str]]:
    manifest = bench_dir / "manifest.tsv"
    if manifest.is_file():
        lines = manifest.read_text(encoding="utf-8").splitlines()
        if len(lines) == n + 1:
            return [(p[0], int(p[1]), int(p[2]), p[3]) for line in lines[1:] if (p := line.split("\t"))]
    bench_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    tasks = [(bench_dir, *make_case(i, rng)) for i in range(n)]
    print(f"Erzeuge eingefrorenes Dataset ({n} Seiten, seed={seed}) mit {workers} Workern...")
    t0 = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(_render_task, tasks, chunksize=8))
    manifest.write_text("id\tlevel\trm_seed\tgt\n" + "".join(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\n" for r in rows), encoding="utf-8")
    print(f"Dataset bereit in {time.perf_counter() - t0:.1f}s -> {bench_dir}\n")
    return rows


if __name__ == "__main__":
    out_dir = BASE_DIR / "data" / "synth"
    out_dir.mkdir(parents=True, exist_ok=True)
    for level, name, draw_text, gt_text in CASES:
        png = out_dir / f"{name}.png"
        rm_b, png_b = render_rm_png(draw_text, png, keep_rm_svg=True)
        out_dir.joinpath(f"{name}.gt.txt").write_text(gt_text + "\n", encoding="utf-8")
        print(f"L{level} | {name} | rm={rm_b}B | png={png_b}B | GT: {gt_text}")
