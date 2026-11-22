#!/usr/bin/env python3
"""Live <1000ms Fast-OCR Arena orchestrator (SSE Browser UI + --once static HTML)."""

import os
os.environ["OMP_THREAD_LIMIT"] = "1"

import argparse, concurrent.futures, http.server, json, mimetypes, queue, subprocess, sys, threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from bench import arena_ui, ocr_runners, synth  # noqa: E402

PORT = 8787


def run_arena(args: argparse.Namespace, state: dict, lock: threading.Lock, subs: list[queue.Queue]) -> None:
    def publish(msg: str | None = None) -> None:
        with lock:
            if msg is not None:
                state["status"] = msg
            snap = json.loads(json.dumps(state))
        for q in list(subs):
            q.put(snap)
        out_dir = BASE_DIR / "data" / "arena"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "arena_latest.html").write_text(arena_ui.build_html(snap, static_mode=True), encoding="utf-8")

    cons_lines = (BASE_DIR / "data" / "consensus" / "manifest.tsv").read_text(encoding="utf-8").splitlines()[1:]
    real_rows = [p for line in cons_lines if (p := line.split("\t"))]
    synth_rows = synth.ensure_dataset(BASE_DIR / "data" / f"bench_s{args.seed}_n{args.synth_n}", args.synth_n, args.seed, args.workers)
    variants = ocr_runners.active_variants()
    with lock:
        state["total"] = len(variants)

    first_png = BASE_DIR / "data" / real_rows[0][3]
    real_paths = [BASE_DIR / "data" / r[3] for r in real_rows]
    synth_paths = [BASE_DIR / "data" / f"bench_s{args.seed}_n{args.synth_n}" / f"{cid}.png" for cid, _, _, _ in synth_rows]
    sample_idxs = arena_ui.sample_indices(real_rows, cap_per_bucket=20)
    persistent = ocr_runners.open_persistent_workers(variants, first_png)

    publish(f"Starte {len(variants)} schnelle Varianten auf {len(real_rows)} Konsens-Zeilen + {len(synth_rows)} Synth...")
    best: dict[str, dict] = {}
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for idx, (vname, (family, cfg)) in enumerate(variants.items(), start=1):
                publish(f"Läuft [{idx}/{len(variants)}]: {vname} ({family})...")
                row, r_res = ocr_runners.evaluate_variant(
                    pool, vname, family, cfg, real_rows, real_paths, synth_rows, synth_paths, persistent, first_png
                )
                if family not in best or row["real_all"] > best[family]["real_all"]:
                    best[family] = {**row, "preds": r_res}
                print(
                    f"{vname:18s} [{family:11s}] | Math={row['math']:5.1f}% | Dev={row['dev']:5.1f}% | "
                    f"Hold={row['hold']:5.1f}% | Real={row['real_all']:5.1f}% | Synth={row['synth']:5.1f}% | "
                    f"{row['ms']:5.0f}ms | {row['gate']}"
                )
                with lock:
                    state["done"] = idx
                    state["results"].append(row)
                    empty = [(r[1], "", 0.0, 0.0) for r in real_rows]
                    tp = best["Tesseract"]["preds"] if "Tesseract" in best else empty
                    vp = best["AppleVision"]["preds"] if "AppleVision" in best else empty
                    rp = best["RapidOCR"]["preds"] if "RapidOCR" in best else empty
                    state["samples"] = [
                        {"bucket": real_rows[i][1], "nb": real_rows[i][2], "png_rel": real_rows[i][3], "gt": real_rows[i][4],
                         "vis_pred": vp[i][1], "vis_acc": vp[i][2],
                         "tess_pred": tp[i][1], "tess_acc": tp[i][2],
                         "w2_pred": rp[i][1], "w2_acc": rp[i][2]}
                        for i in sample_idxs
                    ]
                publish()
    finally:
        for w in persistent.values():
            w.close()

    (BASE_DIR / "data" / "arena" / "arena_results.tsv").write_text(
        "variant\tfamily\treal_math\treal_dev\treal_holdout\treal_all\tsynth_pct\tms\tgate\n"
        + "".join(f"{r['name']}\t{r['family']}\t{r['math']:.1f}\t{r['dev']:.1f}\t{r['hold']:.1f}\t{r['real_all']:.1f}\t{r['synth']:.1f}\t{r['ms']:.1f}\t{r['gate']}\n" for r in state["results"]),
        encoding="utf-8",
    )
    publish(f"Fertig ({len(variants)}/{len(variants)}) — Bericht gespeichert unter data/arena/arena_latest.html")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Einmal ausführen, HTML/TSV speichern, beenden")
    ap.add_argument("--synth-n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    state = {"status": "Initialisiere...", "done": 0, "total": len(ocr_runners.VARIANTS), "results": [], "samples": []}
    lock, subs = threading.Lock(), []
    if args.once:
        run_arena(args, state, lock, subs)
        return 0

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                with lock:
                    snap = json.loads(json.dumps(state))
                body = arena_ui.build_html(snap, static_mode=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)
            elif self.path == "/events":
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache"); self.end_headers()
                q: queue.Queue = queue.Queue()
                subs.append(q)
                try:
                    with lock:
                        self.wfile.write(f"data: {json.dumps(state)}\n\n".encode("utf-8")); self.wfile.flush()
                    while True:
                        snap = q.get(timeout=30)
                        self.wfile.write(f"data: {json.dumps(snap)}\n\n".encode("utf-8")); self.wfile.flush()
                except Exception:
                    pass
                finally:
                    if q in subs:
                        subs.remove(q)
            elif self.path.startswith("/data/"):
                fp = (BASE_DIR / self.path.lstrip("/")).resolve()
                if str(fp).startswith(str((BASE_DIR / "data").resolve())) and fp.is_file():
                    self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(fp.name)[0] or "application/octet-stream"); self.end_headers(); self.wfile.write(fp.read_bytes())
                else:
                    self.send_error(404)
            else:
                self.send_error(404)
        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=run_arena, args=(args, state, lock, subs), daemon=True).start()
    print(f"Live Arena: http://127.0.0.1:{PORT} (Ctrl+C zum Beenden)")
    subprocess.run(["open", f"http://127.0.0.1:{PORT}"], check=False)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nLive Arena beendet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
