#!/usr/bin/env python3
"""Unified M3-Max flywheel runner (--mode dual | --mode stress)."""

import os
os.environ["OMP_THREAD_LIMIT"] = "1"

import argparse, base64, collections, concurrent.futures, hashlib, html, json, random, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from bench import synth                 # noqa: E402
from ocr import pipeline as ocr_pipeline  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/generate"
VLM_PROMPT = "Transcribe all numbers, letters, and math symbols in this single handwritten line exactly as written. Output only the text, no explanation."

VARIANTS = {
    "V0_baseline": {},
    "V1a_pre_crop": {"ink_crop": True},
    "V1b_pre_crop_bold": {"ink_crop": True, "bold": True},
    "V2a_minusfix": {"fix_minus_bug": True},
    "V2b_wl_minusfix": {"use_whitelist": True, "fix_minus_bug": True},
    "V4_crop_bold_minusfix": {"ink_crop": True, "bold": True, "fix_minus_bug": True},
    "V5_crop_bold_wl_geom": {"ink_crop": True, "bold": True, "fix_minus_bug": True, "use_whitelist": True, "geom_sup_rescue": True},
}


def query_vlm(model: str, png_path: Path) -> str:
    payload = json.dumps({
        "model": model, "prompt": VLM_PROMPT, "stream": False, "options": {"temperature": 0},
        "images": [base64.b64encode(png_path.read_bytes()).decode("ascii")],
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return (json.loads(resp.read().decode("utf-8")).get("response") or "").strip()


def prepare_real_val(real_dir: Path, vlm_model: str) -> list[tuple[Path, str, str]]:
    rend_dir, line_dir = real_dir / "rendered", real_dir / "lines"
    rend_dir.mkdir(parents=True, exist_ok=True)
    line_dir.mkdir(parents=True, exist_ok=True)
    cache_path = real_dir / "vlm_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}

    for rm in sorted(real_dir.glob("*.rm")):
        svg, png = rend_dir / f"{rm.stem}.svg", rend_dir / f"{rm.stem}.png"
        subprocess.run(["rmc", "-t", "svg", str(rm), "-o", str(svg)], check=True, capture_output=True)
        subprocess.run(["rsvg-convert", "-b", "white", "-z", "2", str(svg), "-o", str(png)], check=True, capture_output=True)
        for idx, chunk in enumerate(ocr_pipeline.split_lines(Image.open(png).convert("L")), start=1):
            chunk.save(line_dir / f"{rm.stem}_line{idx:02d}.png")

    items = []
    for lp in sorted(line_dir.glob("*.png")):
        gt_file = lp.with_suffix(".gt.txt")
        if gt_file.is_file():
            target, src = gt_file.read_text(encoding="utf-8").strip(), "human"
        else:
            key = f"{hashlib.sha256(lp.read_bytes()).hexdigest()}:{vlm_model}"
            if key not in cache:
                cache[key] = query_vlm(vlm_model, lp)
                cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            target, src = cache[key], vlm_model
        print(f"Real Val | {lp.name} [{src}] -> {target!r}")
        items.append((lp, target, src))
    return items


def gate_label(d_synth: float, d_real: float, is_base: bool) -> str:
    if is_base:
        return "BASELINE"
    if d_synth > 0 and d_real >= 0:
        return "KEEP"
    if d_real > 0 and d_synth >= -1.0:
        return "REAL_WIN"
    if d_synth > 0 and d_real < 0:
        return "OVERFIT"
    return "DISCARD"


def _eval_cached(task: tuple[Path, str, int, str, dict]) -> tuple[str, int, bool, list[str]]:
    png_path, cid, level, gt, cfg = task
    pred = ocr_pipeline.run(png_path, cfg)
    gn, pn = ocr_pipeline.norm(gt), ocr_pipeline.norm(pred)
    ok = gn == pn
    return cid, level, ok, [] if ok else ocr_pipeline.diff_tags(gn, pn)


def _eval_stress(task: tuple[str, int, int, int, int, str, str]) -> dict:
    vname, idx, level, rm_seed, x0, draw_txt, gt = task
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "p.png"
        synth.render_rm_png(draw_txt, png, x0=x0, seed=rm_seed)
        pred = ocr_pipeline.run(png, VARIANTS[vname])
        gn, pn = ocr_pipeline.norm(gt), ocr_pipeline.norm(pred)
        ok = gn == pn
        return {
            "idx": idx, "level": level, "rm_seed": rm_seed, "gt": gt, "pred": pred, "ok": ok,
            "tags": [] if ok else ocr_pipeline.diff_tags(gn, pn), "png": b"" if ok else png.read_bytes(),
        }


def run_dual(args: argparse.Namespace) -> Path:
    real_items = prepare_real_val(BASE_DIR / "data" / "real_val", args.vlm)
    bench_dir = BASE_DIR / "data" / f"bench_s{args.seed}_n{args.n}"
    out_dir = BASE_DIR / "data" / "dual"
    out_dir.mkdir(parents=True, exist_ok=True)
    synth_rows = synth.ensure_dataset(bench_dir, args.n, args.seed, args.workers)
    print()

    results, base_ok, base_synth, base_real = [], {}, None, None
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for vname, cfg in VARIANTS.items():
            t0 = time.perf_counter()
            tasks = [(bench_dir / f"{cid}.png", cid, lvl, gt, cfg) for cid, lvl, _, gt in synth_rows]
            ok_map, lvl_ok, lvl_n, errs = {}, {1: 0, 2: 0, 3: 0, 4: 0}, {1: 0, 2: 0, 3: 0, 4: 0}, collections.Counter()
            for cid, lvl, ok, tags in pool.map(_eval_cached, tasks, chunksize=16):
                ok_map[cid], lvl_n[lvl] = ok, lvl_n[lvl] + 1
                if ok:
                    lvl_ok[lvl] += 1
                else:
                    errs.update(tags)
            elapsed = time.perf_counter() - t0
            synth_pct = 100.0 * sum(ok_map.values()) / len(synth_rows)
            real_preds = [(lp, tgt, src, ocr_pipeline.run(lp, cfg)) for lp, tgt, src in real_items]
            real_accs = [ocr_pipeline.real_accuracy(tgt, pred) * 100.0 for _, tgt, _, pred in real_preds]
            real_acc = sum(real_accs) / max(1, len(real_accs))
            if not base_ok:
                base_ok, base_synth, base_real = ok_map, synth_pct, real_acc
            fixed = sum(1 for cid in ok_map if not base_ok[cid] and ok_map[cid])
            regr = sum(1 for cid in ok_map if base_ok[cid] and not ok_map[cid])
            d_synth, d_real = synth_pct - base_synth, real_acc - base_real
            gate = gate_label(d_synth, d_real, vname == "V0_baseline")
            lp = [100 * lvl_ok[l] / max(1, lvl_n[l]) for l in (1, 2, 3, 4)]
            top3 = ", ".join(f"{t} ({c}x)" for t, c in errs.most_common(3)) or "none"
            print(f"{vname:22s} | Synth={synth_pct:5.1f}% ({d_synth:+5.1f}pp +{fixed}/-{regr}) | L1={lp[0]:.1f} L2={lp[1]:.1f} L3={lp[2]:.1f} L4={lp[3]:.1f} | Real={real_acc:5.1f}% ({d_real:+5.1f}pp) | {gate:8s} | {elapsed:.1f}s")
            results.append({"name": vname, "synth_pct": synth_pct, "d_synth": d_synth, "fixed": fixed, "regr": regr, "lp": lp,
                            "real_acc": real_acc, "d_real": d_real, "gate": gate, "elapsed": elapsed, "top3": top3, "real_preds": real_preds, "real_accs": real_accs})

    (out_dir / "dual_results.tsv").write_text(
        "variant\tsynth_pct\td_synth\tfixed\tregressed\tL1\tL2\tL3\tL4\treal_acc\td_real\tgate\tsec\ttop3\n"
        + "".join(f"{r['name']}\t{r['synth_pct']:.1f}\t{r['d_synth']:+.1f}\t{r['fixed']}\t{r['regr']}\t{r['lp'][0]:.1f}\t{r['lp'][1]:.1f}\t{r['lp'][2]:.1f}\t{r['lp'][3]:.1f}\t{r['real_acc']:.1f}\t{r['d_real']:+.1f}\t{r['gate']}\t{r['elapsed']:.1f}\t{r['top3']}\n" for r in results),
        encoding="utf-8",
    )
    best, base = max(results, key=lambda r: (round(r["real_acc"], 6), round(r["synth_pct"], 6))), results[0]
    lb = "".join(
        f"<tr><td><strong>{html.escape(r['name'])}</strong></td><td>{r['synth_pct']:.1f}%</td><td>{r['d_synth']:+.1f}pp (+{r['fixed']}/-{r['regr']})</td>"
        f"<td>{r['lp'][0]:.0f}/{r['lp'][1]:.0f}/{r['lp'][2]:.0f}/{r['lp'][3]:.0f}%</td><td><strong>{r['real_acc']:.1f}%</strong></td><td>{r['d_real']:+.1f}pp</td>"
        f"<td class='{r['gate'].lower()}'>{r['gate']}</td><td>{r['elapsed']:.1f}s</td><td><code>{html.escape(r['top3'])}</code></td></tr>"
        for r in results
    )
    cards = "".join(
        f"<tr><td>{html.escape(lp.name)}</td><td><img src='../real_val/lines/{html.escape(lp.name)}'></td><td><code>{html.escape(tgt)}</code></td>"
        f"<td><code>{html.escape(base['real_preds'][i][3])}</code> <small>({base['real_accs'][i]:.1f}%)</small></td>"
        f"<td><code>{html.escape(best['real_preds'][i][3])}</code> <small>({best['real_accs'][i]:.1f}%)</small></td></tr>"
        for i, (lp, tgt, _, _) in enumerate(best["real_preds"])
    )
    html_path = out_dir / "dual_report.html"
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Dual CPU+GPU OCR Flywheel</title>"
        "<style>body{font-family:sans-serif;background:#111;color:#eee;padding:20px}table{border-collapse:collapse;width:100%;margin-bottom:22px}"
        "th,td{border:1px solid #333;padding:7px 10px;text-align:left}img{height:44px;background:#fff;padding:3px}small{color:#94a3b8}"
        ".keep,.real_win{color:#4ade80;font-weight:700}.overfit{color:#f59e0b;font-weight:700}.discard{color:#f87171}</style>"
        f"<h1>Dual-Track Flywheel: CPU Synth (n={args.n}) + Real (.rm, VLM={html.escape(args.vlm)})</h1>"
        f"<table><tr><th>Variante</th><th>Synth</th><th>Δ Synth</th><th>L1/L2/L3/L4</th><th>Real Acc</th><th>Δ Real</th><th>Gate</th><th>Zeit</th><th>Top 3 Fehler</th></tr>{lb}</table>"
        f"<h2>Echte Handschrift-Zeilen: V0 vs. {html.escape(best['name'])}</h2><table><tr><th>Zeile</th><th>Bild</th><th>VLM Target</th><th>V0</th><th>{html.escape(best['name'])}</th></tr>{cards}</table>",
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

    def write_stress_html(total: int, passed: int, lvl_ok: dict, lvl_n: dict, errs: collections.Counter, fails: list[dict], cps: float) -> Path:
        lvl_cells = "".join(f"<td>L{l}: {lvl_ok[l]}/{lvl_n[l]} ({100*lvl_ok[l]/max(1,lvl_n[l]):.1f}%)</td>" for l in (1, 2, 3, 4))
        err_rows = "".join(f"<tr><td><code>{html.escape(t)}</code></td><td>{c}</td></tr>" for t, c in errs.most_common(10))
        fail_rows = "".join(f"<tr><td>#{f['idx']}</td><td>L{f['level']}</td><td><img src='fails/{html.escape(f['img'])}'></td><td><code>{html.escape(f['gt'])}</code></td><td><code>{html.escape(f['pred'])}</code></td></tr>" for f in fails)
        p = out_dir / "stress.html"
        p.write_text(
            "<!doctype html><meta charset='utf-8'><title>Stress OCR</title><style>body{font-family:sans-serif;background:#111;color:#eee;padding:20px}"
            "table{border-collapse:collapse;width:100%;margin-bottom:20px}th,td{border:1px solid #333;padding:6px 10px;text-align:left}img{height:52px;background:#fff;padding:2px}</style>"
            f"<h1>Stress Test — <code>{html.escape(args.variant)}</code></h1><p><strong>{passed}/{total} ({100*passed/max(1,total):.1f}%)</strong> | {cps:.1f} cases/s</p>"
            f"<table><tr>{lvl_cells}</tr></table><table><tr><th>Diff</th><th>Count</th></tr>{err_rows or '<tr><td colspan=2>0 Fehler!</td></tr>'}</table>"
            f"<table><tr><th>#</th><th>Lvl</th><th>Bild</th><th>GT</th><th>OCR</th></tr>{fail_rows}</table>",
            encoding="utf-8",
        )
        return p

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
                write_stress_html(total, passed, lvl_ok, lvl_n, errs, fails, cps)
        except KeyboardInterrupt:
            print("\nGestoppt per Ctrl+C — Zwischenstand gespeichert.")
    cps = total / max(0.01, time.perf_counter() - t0)
    html_path = write_stress_html(total, passed, lvl_ok, lvl_n, errs, fails, cps)
    lp = [100 * lvl_ok[l] / max(1, lvl_n[l]) for l in (1, 2, 3, 4)]
    tsv = out_dir / "runs_stress.tsv"
    if not tsv.is_file():
        tsv.write_text("strategy\tn\tpassed\tpct\tL1\tL2\tL3\tL4\tcps\ttop_error\n", encoding="utf-8")
    with tsv.open("a", encoding="utf-8") as fh:
        fh.write(f"{args.variant}\t{total}\t{passed}\t{100*passed/max(1,total):.1f}\t{lp[0]:.1f}\t{lp[1]:.1f}\t{lp[2]:.1f}\t{lp[3]:.1f}\t{cps:.1f}\t{errs.most_common(1)[0][0] if errs else 'none'}\n")
    print(f"Fertig: {passed}/{total} ({100*passed/max(1,total):.1f}%) | HTML: {html_path}")
    return html_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dual", "stress"], default="dual")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--vlm", default="glm-ocr:q8_0")
    ap.add_argument("--variant", default="V5_crop_bold_wl_geom", choices=list(VARIANTS))
    ap.add_argument("--forever", action="store_true")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    out_html = run_dual(args) if args.mode == "dual" else run_stress(args)
    if args.open:
        subprocess.run(["open", str(out_html)], check=False)
