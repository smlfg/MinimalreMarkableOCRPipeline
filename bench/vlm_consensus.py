#!/usr/bin/env python3
"""Two-pass Dual-VLM Consensus builder (glm-ocr:q8_0 -> qwen2.5vl:7b) from real .rm pages."""

import argparse, collections, concurrent.futures, hashlib, json, random, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from bench.ollama import OllamaClient  # noqa: E402
from ocr import post, pre              # noqa: E402

VLM_A, VLM_B = "glm-ocr:q8_0", "qwen2.5vl:7b"
PROMPT = "Transcribe the exact handwritten text, numbers, or math formula in this single line image. Output ONLY the text, no markdown, no explanation."


def clean_gt(s: str) -> str:
    s = s.strip()
    if s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    elif s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    return " ".join(s.split())


def is_math_line(gt: str) -> bool:
    has_digit = any(ch.isdigit() for ch in gt)
    has_op = any(ch in "+-*/=^·" for ch in gt)
    non_sp = max(1, sum(not ch.isspace() for ch in gt))
    return has_digit and (has_op or sum(ch.isdigit() for ch in gt) / non_sp >= 0.50)


def _render(task: tuple[Path, Path]) -> Path | None:
    rm_path, png_out = task
    if png_out.is_file():
        return png_out
    with tempfile.TemporaryDirectory() as td:
        svg = Path(td) / "p.svg"
        try:
            subprocess.run(["rmc", "-t", "svg", str(rm_path), "-o", str(svg)], check=True, capture_output=True)
            subprocess.run(["rsvg-convert", "-b", "white", "-z", "2", str(svg), "-o", str(png_out)], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return None
    return png_out


def _run_vlm_pass(
    model: str,
    items: list[tuple[Path, str, str]],
    client: OllamaClient,
    cache: dict[str, str],
    cache_path: Path,
) -> None:
    dirty = 0
    for idx, (lp, _, sha) in enumerate(items, start=1):
        key = f"{sha}:{model}"
        if key not in cache:
            cache[key] = client.query(model, lp, PROMPT)
            dirty += 1
            if dirty % 25 == 0:
                cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if idx % 50 == 0 or idx == len(items):
            print(f"[{model}] {idx}/{len(items)} verarbeitet ({dirty} neu)...", flush=True)
    if dirty:
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=int, default=1000)
    ap.add_argument("--max-per-nb", type=int, default=40)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    corpus_dir = BASE_DIR / "data" / "real_corpus"
    out_dir = BASE_DIR / "data" / "consensus"
    out_dir.mkdir(parents=True, exist_ok=True)
    rend_dir, line_dir = corpus_dir / "rendered", corpus_dir / "lines"
    rend_dir.mkdir(parents=True, exist_ok=True)
    line_dir.mkdir(parents=True, exist_ok=True)

    cache_path = corpus_dir / "consensus_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    old_cache_p = corpus_dir / "vlm_cache.json"
    if old_cache_p.is_file():
        for k, v in json.loads(old_cache_p.read_text(encoding="utf-8")).items():
            cache.setdefault(k, v)

    by_nb = collections.defaultdict(list)
    for line in (corpus_dir / "manifest.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split("\t")
        if p:
            by_nb[p[1]].append((p[0], p[1], corpus_dir / "rm" / p[5]))
    rng = random.Random(args.seed)
    nb_keys = list(by_nb.keys())
    rng.shuffle(nb_keys)
    for k in nb_keys:
        rng.shuffle(by_nb[k])
    ordered = [by_nb[k][i] for i in range(max(len(v) for v in by_nb.values())) for k in nb_keys if i < len(by_nb[k])]

    cands, seen_lp, per_nb = [], set(), collections.Counter()
    for i in range(0, len(ordered), max(1, args.workers)):
        if len(cands) >= args.candidates:
            break
        batch = [x for x in ordered[i : i + max(1, args.workers)] if per_nb[x[1]] < args.max_per_nb]
        if not batch:
            continue
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            pngs = list(pool.map(_render, [(rm_p, rend_dir / f"{pid}.png") for pid, _, rm_p in batch]))
        for (pid, nb, _), page_png in zip(batch, pngs):
            if page_png is None or len(cands) >= args.candidates or per_nb[nb] >= args.max_per_nb:
                continue
            gray = Image.open(page_png).convert("L")
            chunks = pre.split_lines(gray)
            single_cropped = len(chunks) == 1 and chunks[0].width == gray.width
            if single_cropped:
                chunks = [pre.preprocess(gray, {"ink_crop": True})]
            for lidx, chunk in enumerate(chunks, start=1):
                if len(cands) >= args.candidates or per_nb[nb] >= args.max_per_nb:
                    break
                if chunk.width < 80 or not (20 <= chunk.height <= 260) or (not single_cropped and chunk.width >= gray.width):
                    continue
                lp = line_dir / f"{pid}_l{lidx:02d}.png"
                if lp in seen_lp:
                    continue
                if not lp.is_file():
                    chunk.save(lp)
                seen_lp.add(lp)
                per_nb[nb] += 1
                cands.append((lp, nb))

    hashed = [(lp, nb, hashlib.sha256(lp.read_bytes()).hexdigest()) for lp, nb in cands]
    print(f"Pass 1 ({VLM_A}) über {len(hashed)} Kandidaten-Zeilen...", flush=True)
    with OllamaClient() as client:
        _run_vlm_pass(VLM_A, hashed, client, cache, cache_path)
        pass2 = [
            item for item in hashed
            if 3 <= len(a := clean_gt(cache.get(f"{item[2]}:{VLM_A}", ""))) <= 100 and "```" not in a
        ]
        print(f"Pass 2 ({VLM_B}) über {len(pass2)} vorgefilterte Zeilen...", flush=True)
        _run_vlm_pass(VLM_B, pass2, client, cache, cache_path)

    kept_math, kept_text, rejected = [], [], []
    for lp, nb, sha in hashed:
        if f"{sha}:{VLM_B}" not in cache:
            continue
        a, b = clean_gt(cache.get(f"{sha}:{VLM_A}", "")), clean_gt(cache.get(f"{sha}:{VLM_B}", ""))
        agr = post.accuracy(a, b)
        if agr >= 0.90 and 3 <= len(a) <= 100 and "```" not in a and "```" not in b:
            rel = str(lp.relative_to(BASE_DIR / "data"))
            row = (lp.stem, nb, rel, a, agr * 100.0)
            (kept_math if is_math_line(a) else kept_text).append(row)
        else:
            rejected.append((lp.stem, nb, a, b, agr * 100.0))

    text_nbs = list(dict.fromkeys(r[1] for r in kept_text))
    cut = max(1, int(round(len(text_nbs) * 0.6)))
    dev_nbs = set(text_nbs[:cut])
    rows = [(r[0], "real_math", r[1], r[2], r[3], r[4]) for r in kept_math] + [
        (r[0], "real_text_dev" if r[1] in dev_nbs else "real_text_holdout", r[1], r[2], r[3], r[4]) for r in kept_text
    ]

    (out_dir / "manifest.tsv").write_text("id\tbucket\tnotebook\tpng_rel\tgt\tagreement_pct\n" + "".join(
        f"{x[0]}\t{x[1]}\t{x[2]}\t{x[3]}\t{x[4]}\t{x[5]:.1f}\n" for x in rows
    ), encoding="utf-8")
    counts = collections.Counter(x[1] for x in rows)
    print(f"Konsens: {len(rows)}/{len(cands)} behalten ({len(rejected)} verworfen) -> {dict(counts)}")
    for x in rows[:15]:
        print(f"  [{x[1]:17s}] {x[2][:18]:18s} | {x[4]!r} ({x[5]:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
