"""Simple Website für die Ouroboros-v3-Kampagne (nur stdlib, localhost).

Zeigt bei jedem Refresh den aktuellen Stand: Level-Übersicht, Batch-Tabelle,
Fehltreffer-Galerie (GT vs OCR mit Bild) und Beispiele für sichere Treffer.

Aufruf: .venv_structure/bin/python bench/synth/campaign_v3/webview.py
URL:    http://127.0.0.1:8791
"""
from __future__ import annotations

import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PNG_ROOT = HERE / "png"
PORT = 8791


def read_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open(encoding="utf-8")]


def read_tsv():
    p = HERE / "RESULTS.tsv"
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    head, rows = lines[0].split("\t"), []
    for l in lines[1:]:
        rows.append(dict(zip(head, l.split("\t"))))
    return rows


def esc(s):
    return html.escape(str(s))


def fmt(v, nd=3):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "&mdash;"


def level_summary(rows):
    agg = {}
    for r in rows:
        lv = r["stufe"]
        a = agg.setdefault(lv, {"n": 0, "f1": [], "struct": [], "char": [], "cov": []})
        a["n"] += int(r["n"])
        for key, dst in (("F1_strict", "f1"), ("struct", "struct"), ("char", "char"), ("coverage", "cov")):
            if r.get(key, ""):
                a[dst].append(float(r[key]))
    out = []
    for lv in sorted(agg):
        a = agg[lv]
        m = lambda xs: sum(xs) / len(xs) if xs else None
        out.append((lv, a["n"],
                    m(a["f1"]) or m(a["struct"]) or 0.0,
                    "F1" if a["f1"] else "struct",
                    m(a["char"]) or 0.0, m(a["cov"]) or 0.0))
    return out


def bar(v):
    color = "#3fbf6f" if v >= 0.95 else ("#e8b93c" if v >= 0.75 else "#d9534f")
    return (f'<div style="background:#222;width:180px;height:12px;border-radius:6px">'
            f'<div style="background:{color};width:{v*100:.0f}%;height:12px;border-radius:6px"></div></div>'
            f'<span style="font-size:12px;color:#888">{v:.3f}</span>')


def chain_miss_block(bno, runs):
    miss = runs.get("misses", [])
    if not miss:
        return ""
    gt = {c["id"]: c for c in read_jsonl(HERE / "all_gt.jsonl")}
    rowsmap = {(r["chain_id"], r["step"]): r for r in read_jsonl(HERE / "all_rows.jsonl")}
    out = []
    for m in miss:
        c = gt.get(m["id"])
        if not c:
            continue
        lines = [f'<b>{esc(m["id"])}</b> <span class="tag">{esc(c["topic"])}</span> '
                 f'label={m["label"]} pred={esc(m["pred"])} <span class="stage">{esc(m.get("stage", ""))}</span>']
        lines.append('<table class="mini">')
        for k, s in enumerate(c["steps"]):
            rd = m.get("read", ["?"] * len(c["steps"]))[k] if m.get("read") else ""
            hit = "" if k == 0 else ("✓" if rd and rd == s else "✗")
            img = ""
            r = rowsmap.get((m["id"], k))
            if k >= 1 and r:
                img = (f'<img loading="lazy" src="/png?path=slots/{esc(r["png"].split("/")[-1])}" '
                       f'style="max-height:52px;background:#fff;border:1px solid #444">')
            lines.append(f'<tr><td><code>s{k}</code></td><td><code>{esc(s)}</code></td>'
                         f'<td><code>{esc(rd)}</code> <b>{hit}</b></td><td>{img}</td></tr>')
        lines.append("</table>")
        out.append("<div class='miss'>" + "<br>".join(lines) + "</div>")
    return f"<h3>Batch {bno} — {len(miss)} Fehltreffer</div>" + "".join(out)


def formula_block(bno, runs, only_miss=True):
    res = read_jsonl(HERE / f"batch_{bno:02d}" / "results_formula.jsonl")
    if not res:
        return ""
    pick = [r for r in res if not r["struct"]]
    if not pick:
        return f"<h3>Batch {bno} — 0 daneben</h3>"
    return f"<h3>Batch {bno} — {len(pick)} daneben</h3>" + "".join(formula_card(r) for r in pick[:12])


def formula_card(r):
    f = next((x for x in read_jsonl(HERE / "formulas.jsonl") if x["id"] == r["id"]), None)
    if not f:
        return ""
    png = f["png"].split("/")[-1]
    return (f'<div class="miss"><b>{esc(r["id"])}</b> <span class="tag">{esc(r["topic"])}</span> '
            f'unsicher={"ja" if r.get("unc") else "nein"} parse={"ja" if r.get("parse_ok") else "nein"}'
            f'<br><img loading="lazy" src="/png?path=lines/{esc(png)}" '
            f'style="max-height:70px;background:#fff;border:1px solid #444"> '
            f'<table class="mini"><tr><td>GT</td><td><code>{esc(f["gt_latex"])}</code></td></tr>'
            f'<tr><td>OCR</td><td><code>{esc(r["pred"])}</code></td></tr></table></div>')


def page():
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8")) if (HERE / "plan.json").exists() else {}
    erzeugt = plan.get("erzeugt", {})
    glm_mode = plan.get("messung", {}).get("glm", "an")
    rows = read_tsv()
    summ = level_summary(rows)
    done = len(rows)

    head = f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>Ouroboros v3 — Kampagne</title><style>
body{{background:#14161a;color:#e6e6e6;font:14px/1.45 -apple-system,sans-serif;margin:24px}}
h1{{font-size:21px;margin-bottom:2px}} h3{{font-size:15px;margin:18px 0 6px;color:#9fd}}
a{{color:#7cc}} code{{background:#1e2228;padding:1px 5px;border-radius:4px;font-size:12.5px}}
table{{border-collapse:collapse;margin:6px 0}}
td,th{{border:1px solid #2c313a;padding:4px 9px;font-size:13px}}
.miss{{background:#1b1e24;border:1px solid #2c313a;border-radius:8px;padding:10px;margin:8px 0;max-width:900px}}
.tag{{background:#274;border-radius:5px;padding:1px 7px;font-size:11px}} .stage{{color:#e8b93c;font-size:12px}}
.mini td{{font-size:12px;padding:2px 6px}} .kpi{{display:inline-block;margin-right:26px}}
.kpi b{{font-size:19px;color:#9fd}} .sub{{color:#777;font-size:12px}}
</style></head><body>
<h1>Ouroboros v3 — 1000 synthetische Ketten, live</h1>
<div class="sub">seed {plan.get("seed","?")} · glyph Σ={plan.get("glyph_sigma","?")} · glm={glm_mode} ·
{erzeugt.get("ketten","?")} Ketten / {erzeugt.get("slots","?")} Slots / {erzeugt.get("formeln","?")} Formelzeilen / {erzeugt.get("seiten","?")} Seiten ·
Seed-{erzeugt.get("dauer_s","?")}&nbsp;s Erzeugung, 0 verworfen · auto-refresh 30&nbsp;s</div>
<hr>"""

    k = f"""<h2>Stand ({time.strftime('%H:%M:%S')}) — {done}/21 Batches gemessen</h2>"""
    for lv, n, v, kind, char, cov in summ:
        k += (f'<div style="display:flex;gap:14px;align-items:center;margin:5px 0">'
              f'<b style="width:26px">{lv}</b><span class="sub" style="width:150px">n={n} Ketten/Zeilen</span>'
              f'{bar(v)}<span class="sub">{kind}</span>'
              f'<span class="sub">char {char:.3f} · sicher {cov:.2f}</span></div>')
    if not summ:
        k += "<p>Noch keine Messungen.</p>"

    t = "<h2>Batches</h2><table><tr><th>Zeit</th><th>#</th><th>Stufe</th><th>Art</th><th>n</th><th>F1/struct</th><th>char</th><th>sicher</th><th>prec</th></tr>"
    for r in rows:
        t += (f"<tr><td class='sub'>{esc(r['zeit'])}</td><td>{esc(r['batch'])}</td><td>{esc(r['stufe'])}</td>"
              f"<td>{esc(r['art'])}</td><td>{esc(r['n'])}</td><td><b>{fmt(r['F1_strict'] or r['struct'])}</b></td>"
              f"<td>{fmt(r['char'],2)}</td><td>{fmt(r['coverage'],2)}</td><td>{fmt(r['prec_certain'])}</td></tr>")
    t += "</table>"

    gal = "<h2>Fehltreffer (GT vs OCR, mit Bild)</h2>"
    for bno in range(1, 22):
        runs_p = HERE / "runs" / f"batch_{bno:02d}.json"
        if not runs_p.exists():
            continue
        runs = json.loads(runs_p.read_text(encoding="utf-8"))
        if runs["art"] == "kette":
            gal += chain_miss_block(bno, runs)
        else:
            gal += formula_block(bno, runs)

    return head + k + t + gal + "</body></html>"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            body = page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path == "/png":
            rel = parse_qs(u.query).get("path", [""])[0]
            p = (PNG_ROOT / rel).resolve()
            if not str(p).startswith(str(PNG_ROOT.resolve())) or not p.exists():
                self.send_error(404)
                return
            body = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


if __name__ == "__main__":
    print(f"Ouroboros v3 unter http://127.0.0.1:{PORT} (Strg+C beendet)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
