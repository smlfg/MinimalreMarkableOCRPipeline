#!/usr/bin/env python3
"""Unified M3-Max flywheel runner (--mode dual | --mode stress) with strict 1-param Tesseract sweep."""

import os
os.environ["OMP_THREAD_LIMIT"] = "1"

import argparse, collections, concurrent.futures, hashlib, html, json, random, subprocess, sys, tempfile, time
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from bench import synth                 # noqa: E402
from bench.ollama import OllamaClient   # noqa: E402
from ocr import pipeline as ocr_pipeline, pre  # noqa: E402

VLM_PROMPT = "Transcribe all handwritten words, numbers, and math symbols in this single line exactly as written. Output only the text, no explanation."

B1 = {"ink_crop": True, "bold": True, "lang": "deu+eng", "psm": "7"}

VARIANTS = {
    "V0_raw":          ("Base",          {}),
    "B1_bold_deu_p7":  ("Anchor",        B1),
    "T1_no_dawg":      ("Eng:-dawg",     {**B1, "tess_cfg": {"load_system_dawg": "0", "load_freq_dawg": "0"}}),
    "T2_low_dict_pen": ("Eng:pen=0.05",  {**B1, "tess_cfg": {"language_model_penalty_non_dict_word": "0.05", "language_model_penalty_non_freq_dict_word": "0.05"}}),
    "T3_min_linesize": ("Eng:lsize=1.5", {**B1, "tess_cfg": {"textord_min_linesize": "1.5"}}),
    "T4_keep_spaces":  ("Eng:spaces=1",  {**B1, "tess_cfg": {"preserve_interword_spaces": "1"}}),
    "P1_scale_1.5":    ("Pre:scale=1.5", {**B1, "scale": 1.5}),
    "P2_scale_2.0":    ("Pre:scale=2.0", {**B1, "scale": 2.0}),
    "P3_no_bold":      ("Pre:bold=off",  {"ink_crop": True, "bold": False, "lang": "deu+eng", "psm": "7"}),
    "E1_dpi_300":      ("Eng:dpi=300",   {**B1, "dpi": "300"}),
    "E2_psm_6":        ("Eng:psm=6",     {**B1, "psm": "6"}),
    "E3_psm_13":       ("Eng:psm=13",    {**B1, "psm": "13"}),
}


def _render_real_page(task: tuple[Path, Path]) -> Path | None:
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


def prepare_real_corpus(target_lines: int, max_per_nb: int, seed: int, vlm_model: str, workers: int) -> list[tuple[Path, str, str, str]]:
    corpus_dir = BASE_DIR / "data" / "real_corpus"
    manifest = corpus_dir / "manifest.tsv"
    if not manifest.is_file():
        print("Hinweis: data/real_corpus/manifest.tsv fehlt — nutze Fallback data/real_val/")
        manifest_rows = [("01_ocr_p01", "Ocr", str(p)) for p in sorted((BASE_DIR / "data" / "real_val").glob("*.rm"))]
        work_dir = BASE_DIR / "data" / "real_val"
    else:
        lines = manifest.read_text(encoding="utf-8").splitlines()[1:]
        manifest_rows = [(p[0], p[1], str(corpus_dir / "rm" / p[5])) for line in lines if (p := line.split("\t"))]
        work_dir = corpus_dir

    rend_dir, line_dir = work_dir / "rendered", work_dir / "lines"
    rend_dir.mkdir(parents=True, exist_ok=True)
    line_dir.mkdir(parents=True, exist_ok=True)
    cache_path = work_dir / "vlm_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}

    by_nb = collections.defaultdict(list)
    for pid, nb, rm_p in manifest_rows:
        by_nb[nb].append((pid, nb, Path(rm_p)))
    rng = random.Random(seed)
    nb_keys = list(by_nb.keys())
    rng.shuffle(nb_keys)
    for k in nb_keys:
        rng.shuffle(by_nb[k])

    ordered = []
    for i in range(max((len(v) for v in by_nb.values()), default=0)):
        for k in nb_keys:
            if i < len(by_nb[k]):
                ordered.append(by_nb[k][i])

    items, seen_lp, per_nb = [], set(), collections.Counter()
    with OllamaClient() as vlm:
        for cap in (max_per_nb, max_per_nb + 1, max_per_nb + 3):
            for i in range(0, len(ordered), max(1, workers)):
                if len(items) >= target_lines:
                    break
                batch = [x for x in ordered[i : i + max(1, workers)] if per_nb[x[1]] < cap]
                if not batch:
                    continue
                with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
                    pngs = list(pool.map(_render_real_page, [(rm_p, rend_dir / f"{pid}.png") for pid, _, rm_p in batch]))
                for (pid, nb, _), page_png in zip(batch, pngs):
                    if page_png is None or len(items) >= target_lines or per_nb[nb] >= cap:
                        continue
                    gray = Image.open(page_png).convert("L")
                    for lidx, chunk in enumerate(pre.split_lines(gray), start=1):
                        if len(items) >= target_lines or per_nb[nb] >= cap:
                            break
                        if chunk.width < 80 or not (20 <= chunk.height <= 200) or chunk.width >= gray.width:
                            continue
                        lp = line_dir / f"{pid}_l{lidx:02d}.png"
                        if lp in seen_lp:
                            continue
                        if not lp.is_file():
                            chunk.save(lp)
                        key = f"{hashlib.sha256(lp.read_bytes()).hexdigest()}:{vlm_model}"
                        if key not in cache:
                            cache[key] = vlm.query(vlm_model, lp, VLM_PROMPT)
                            cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        target = cache[key].strip()
                        if not target or len(target) > 120 or "```" in target or sum(ch.isalnum() for ch in target) < 3:
                            continue
                        seen_lp.add(lp)
                        per_nb[nb] += 1
                        items.append((lp, target, vlm_model, nb))
                        print(f"Real [{len(items):02d}/{target_lines}] {nb[:20]:20s} | {lp.name} -> {target!r}")
    return items


def gate_label(vname: str, d_synth: float, d_dev: float, d_hold: float) -> str:
    if vname == "V0_raw":
        return "BASE"
    if vname == "B1_bold_deu_p7":
        return "ANCHOR"
    if d_dev > 0.3 and d_hold < -0.3:
        return "OVERFIT"
    if d_synth > 0.5 and (d_dev + d_hold) / 2 < -0.5:
        return "OVERFIT"
    if d_hold > 0.2 and d_dev >= -0.5:
        return "KEEP"
    if d_dev > 0.3 and d_hold >= 0.0:
        return "KEEP"
    return "DISCARD"


def _eval_cached(task: tuple[Path, str, int, str, dict]) -> tuple[str, int, bool, bool, list[str]]:
    png_path, cid, level, gt, cfg = task
    res = ocr_pipeline.run_detailed(png_path, cfg)
    gn = ocr_pipeline.norm(gt)
    pr, pf = ocr_pipeline.norm(res["raw"]), ocr_pipeline.norm(res["final"])
    return cid, level, gn == pr, gn == pf, [] if gn == pf else ocr_pipeline.diff_tags(gn, pf)


def _eval_real_line(task: tuple[Path, str, dict]) -> tuple[str, str, float, float]:
    lp, tgt, cfg = task
    res = ocr_pipeline.run_detailed(lp, cfg)
    return res["raw"], res["final"], ocr_pipeline.accuracy(tgt, res["raw"]) * 100.0, ocr_pipeline.accuracy(tgt, res["final"]) * 100.0


def _eval_stress(task: tuple[str, int, int, int, int, str, str]) -> dict:
    vname, idx, level, rm_seed, x0, draw_txt, gt = task
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "p.png"
        synth.render_rm_png(draw_txt, png, x0=x0, seed=rm_seed)
        pred = ocr_pipeline.run(png, VARIANTS[vname][1])
        gn, pn = ocr_pipeline.norm(gt), ocr_pipeline.norm(pred)
        ok = gn == pn
        return {
            "idx": idx, "level": level, "rm_seed": rm_seed, "gt": gt, "pred": pred, "ok": ok,
            "tags": [] if ok else ocr_pipeline.diff_tags(gn, pn), "png": b"" if ok else png.read_bytes(),
        }


def run_dual(args: argparse.Namespace) -> Path:
    real_items = prepare_real_corpus(args.real_lines, args.max_per_nb, args.seed, args.vlm, args.workers)
    bench_dir = BASE_DIR / "data" / f"bench_s{args.seed}_n{args.n}"
    out_dir = BASE_DIR / "data" / "dual"
    out_dir.mkdir(parents=True, exist_ok=True)
    synth_rows = synth.ensure_dataset(bench_dir, args.n, args.seed, args.workers)

    seen_nbs = list(dict.fromkeys(x[3] for x in real_items))
    cut_nb = max(1, int(round(len(seen_nbs) * 0.6)))
    dev_nbs = set(seen_nbs[:cut_nb])
    is_dev = [x[3] in dev_nbs for x in real_items]
    n_dev, n_hold = sum(is_dev), len(is_dev) - sum(is_dev)
    print(f"\nDual Sweep: Synth n={len(synth_rows)} | Real={len(real_items)} Zeilen across {len(seen_nbs)} Notizbücher (Dev={n_dev} / Holdout={n_hold})\n")

    raw_rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for vname, (stage, cfg) in VARIANTS.items():
            t0 = time.perf_counter()
            s_res = list(pool.map(_eval_cached, [(bench_dir / f"{cid}.png", cid, lvl, gt, cfg) for cid, lvl, _, gt in synth_rows], chunksize=16))
            r_res = list(pool.map(_eval_real_line, [(lp, tgt, cfg) for lp, tgt, _, _ in real_items]))
            elapsed = time.perf_counter() - t0
            synth_pct = 100.0 * sum(r[3] for r in s_res) / len(s_res)
            dev_accs = [r[3] for r, d in zip(r_res, is_dev) if d]
            hold_accs = [r[3] for r, d in zip(r_res, is_dev) if not d]
            dev_pct = sum(dev_accs) / max(1, len(dev_accs))
            hold_pct = sum(hold_accs) / max(1, len(hold_accs))
            all_pct = sum(r[3] for r in r_res) / max(1, len(r_res))
            raw_rows.append({"name": vname, "stage": stage, "synth": synth_pct, "dev": dev_pct, "hold": hold_pct, "all": all_pct, "elapsed": elapsed, "r_res": r_res})

    b1 = next(r for r in raw_rows if r["name"] == "B1_bold_deu_p7")
    results = []
    for r in raw_rows:
        d_synth, d_dev, d_hold, d_all = r["synth"] - b1["synth"], r["dev"] - b1["dev"], r["hold"] - b1["hold"], r["all"] - b1["all"]
        gate = gate_label(r["name"], d_synth, d_dev, d_hold)
        print(f"{r['name']:16s} [{r['stage']:13s}] | Synth={r['synth']:5.1f}% | Dev={r['dev']:5.1f}% | Hold={r['hold']:5.1f}% | Real={r['all']:5.1f}% ({d_all:+5.1f}pp vs B1) | {gate:7s} | {r['elapsed']:.1f}s")
        results.append({**r, "d_synth": d_synth, "d_dev": d_dev, "d_hold": d_hold, "d_all": d_all, "gate": gate})

    (out_dir / "dual_results.tsv").write_text(
        "variant\tstage\tsynth_pct\treal_dev\treal_holdout\treal_all\td_vs_b1\tgate\tsec\n"
        + "".join(f"{r['name']}\t{r['stage']}\t{r['synth']:.1f}\t{r['dev']:.1f}\t{r['hold']:.1f}\t{r['all']:.1f}\t{r['d_all']:+.1f}\t{r['gate']}\t{r['elapsed']:.1f}\n" for r in results),
        encoding="utf-8",
    )
    best = max(results, key=lambda r: (round(r["hold"], 6), round(r["all"], 6)))
    lb = "".join(
        f"<tr><td><strong>{html.escape(r['name'])}</strong></td><td><code>{html.escape(r['stage'])}</code></td>"
        f"<td>{r['synth']:.1f}%</td><td>{r['dev']:.1f}%</td><td><strong>{r['hold']:.1f}%</strong></td>"
        f"<td><strong>{r['all']:.1f}%</strong></td><td>{r['d_all']:+.1f}pp</td>"
        f"<td class='{r['gate'].lower()}'>{r['gate']}</td><td>{r['elapsed']:.1f}s</td></tr>"
        for r in results
    )
    cards = "".join(
        f"<tr><td><strong>{html.escape(nb)}</strong><br><small>{'DEV' if is_dev[i] else 'HOLDOUT'} · {html.escape(lp.name)}</small></td>"
        f"<td><img src='{html.escape(os.path.relpath(lp, out_dir))}'></td><td><code>{html.escape(tgt)}</code></td>"
        f"<td><code>{html.escape(raw_rows[0]['r_res'][i][1])}</code> <small>({raw_rows[0]['r_res'][i][3]:.1f}%)</small></td>"
        f"<td><code>{html.escape(best['r_res'][i][1])}</code> <small>({best['r_res'][i][3]:.1f}%)</small></td></tr>"
        for i, (lp, tgt, _, nb) in enumerate(real_items[:25])
    )
    html_path = out_dir / "dual_report.html"
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Tesseract Handwriting Ceiling</title>"
        "<style>body{font-family:sans-serif;background:#111;color:#eee;padding:20px}table{border-collapse:collapse;width:100%;margin-bottom:22px}"
        "th,td{border:1px solid #333;padding:7px 10px;text-align:left}img{height:44px;background:#fff;padding:3px}small{color:#94a3b8}"
        ".keep{color:#4ade80;font-weight:700}.anchor{color:#38bdf8;font-weight:700}.overfit{color:#f59e0b;font-weight:700}.discard{color:#f87171}</style>"
        f"<h1>Tesseract Ceiling Sweep ({len(real_items)} Zeilen aus {len(seen_nbs)} Notizbüchern | Dev={n_dev} / Holdout={n_hold})</h1>"
        f"<table><tr><th>Variante</th><th>Parameter</th><th>Synth %</th><th>Real Dev</th><th>Real Holdout</th><th>Real Gesamt</th><th>Δ vs B1</th><th>Gate</th><th>Zeit</th></tr>{lb}</table>"
        f"<h2>Samples: V0_raw vs. {html.escape(best['name'])}</h2>"
        f"<table><tr><th>Notizbuch</th><th>Bild</th><th>VLM Target</th><th>V0_raw</th><th>{html.escape(best['name'])}</th></tr>{cards}</table>",
        encoding="utf-8",
    )
    print(f"\nTSV:  {out_dir / 'dual_results.tsv'}\nHTML: {html_path}")
    return html_path


def run_stress(args: argparse.Namespace) -> Path:
    out_dir = BASE_DIR / "data" / "stress"
    fail_dir = out_dir / "fails"
    fail_dir.mkdir(parents=True, exist_ok=True)
    for old in fail_dir.glob("*.png"):
        old.unlink()
    rng, lvl_ok, lvl_n = random.Random(args.seed), {1: 0, 2: 0, 3: 0, 4: 0}, {1: 0, 2: 0, 3: 0, 4: 0}
    errs, fails, total, passed, idx, t0 = collections.Counter(), [], 0, 0, 0, time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        try:
            while args.forever or idx < args.n:
                batch_n = 25 if args.forever else min(25, args.n - idx)
                batch = [(args.variant, *synth.make_case(idx + j, rng)) for j in range(batch_n)]
                idx += batch_n
                for res in pool.map(_eval_stress, batch):
                    total, lvl_n[res["level"]] = total + 1, lvl_n[res["level"]] + 1
                    if res["ok"]:
                        passed, lvl_ok[res["level"]] = passed + 1, lvl_ok[res["level"]] + 1
                    else:
                        errs.update(res["tags"])
                        if len(fails) < 30:
                            name = f"fail_{res['idx']:05d}_L{res['level']}.png"
                            (fail_dir / name).write_bytes(res["png"])
                            fails.append({**res, "img": name})
                cps = total / max(0.01, time.perf_counter() - t0)
                print(f"[{total}] {passed}/{total} ({100*passed/total:5.1f}%) | {cps:4.1f} cases/s | top={errs.most_common(1)}")
        except KeyboardInterrupt:
            print("\nGestoppt per Ctrl+C.")
    html_path = out_dir / "stress.html"
    fail_rows = "".join(f"<tr><td>#{f['idx']}</td><td>L{f['level']}</td><td><img src='fails/{html.escape(f['img'])}'></td><td><code>{html.escape(f['gt'])}</code></td><td><code>{html.escape(f['pred'])}</code></td></tr>" for f in fails)
    err_rows = "".join(f"<tr><td><code>{html.escape(t)}</code></td><td>{c}</td></tr>" for t, c in errs.most_common(10))
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Stress OCR</title><style>body{font-family:sans-serif;background:#111;color:#eee;padding:20px}"
        "table{border-collapse:collapse;width:100%;margin-bottom:20px}th,td{border:1px solid #333;padding:6px 10px;text-align:left}img{height:52px;background:#fff;padding:2px}</style>"
        f"<h1>Stress — {html.escape(args.variant)}: {passed}/{total} ({100*passed/max(1,total):.1f}%)</h1>"
        f"<table><tr><th>Diff</th><th>Count</th></tr>{err_rows}</table><table><tr><th>#</th><th>Lvl</th><th>Bild</th><th>GT</th><th>OCR</th></tr>{fail_rows}</table>",
        encoding="utf-8",
    )
    print(f"Fertig: {passed}/{total} ({100*passed/max(1,total):.1f}%) | HTML: {html_path}")
    return html_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dual", "stress"], default="dual")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--real-lines", type=int, default=40)
    ap.add_argument("--max-per-nb", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--vlm", default="glm-ocr:q8_0")
    ap.add_argument("--variant", default="B1_bold_deu_p7", choices=list(VARIANTS))
    ap.add_argument("--forever", action="store_true")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    out_html = run_dual(args) if args.mode == "dual" else run_stress(args)
    if args.open:
        subprocess.run(["open", str(out_html)], check=False)
