#!/usr/bin/env python3
"""HTML/SVG renderer for the Live <1s Fast-OCR Arena (SSE & static export)."""

import collections, json


def sample_indices(real_rows: list[list[str]], cap_per_bucket: int = 20) -> list[int]:
    counts: collections.Counter[str] = collections.Counter()
    chosen: list[int] = []
    for i, r in enumerate(real_rows):
        if counts[r[1]] < cap_per_bucket:
            counts[r[1]] += 1
            chosen.append(i)
    return chosen


def build_html(state: dict, static_mode: bool) -> str:
    img_prefix = "../" if static_mode else "/data/"
    sse_js = "" if static_mode else """
    const es = new EventSource('/events');
    es.onmessage = (e) => render(JSON.parse(e.data));
    """
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Live &lt;1s Fast-OCR Arena</title>
<style>
  body{{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:20px}}
  h1{{margin:0 0 6px 0;font-size:22px}} .sub{{color:#94a3b8;font-size:13px;margin-bottom:14px}}
  .bar-bg{{background:#1e293b;border-radius:8px;height:14px;overflow:hidden;margin-bottom:18px;border:1px solid #334155}}
  .bar{{background:#38bdf8;height:100%;transition:width .25s}}
  .grid{{display:grid;grid-template-columns:460px 1fr;gap:18px;align-items:start;margin-bottom:22px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th,td{{padding:7px 9px;border-bottom:1px solid #334155;text-align:left}} th{{color:#94a3b8}}
  .ok{{color:#4ade80;font-weight:700}} .slow{{color:#f87171;font-weight:700}}
  .img-cell img{{height:42px;background:#fff;padding:3px;border-radius:4px}}
  @media(max-width:1050px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Live &lt;1s Fast-OCR Arena</h1>
<div class="sub" id="status">Lade...</div>
<div class="bar-bg"><div class="bar" id="pbar" style="width:0%"></div></div>
<div class="grid">
  <div class="card"><h3 style="margin-top:0">Pareto: Accuracy vs. Latency (&lt;1000 ms)</h3><div class="sub" style="margin-bottom:6px"><span style="color:#4ade80">● AppleVision</span> · <span style="color:#38bdf8">● Tesseract</span> · <span style="color:#f59e0b">● RapidOCR</span></div><svg id="pareto" viewBox="0 0 430 260" width="100%"></svg></div>
  <div class="card"><h3 style="margin-top:0">Leaderboard</h3><table><thead><tr><th>Variante</th><th>Engine</th><th>Math</th><th>Dev</th><th>Holdout</th><th>Real All</th><th>Synth</th><th>ms/Zeile</th><th>Gate</th></tr></thead><tbody id="lb"></tbody></table></div>
</div>
<div class="card"><h3 style="margin-top:0">Echte Konsens-Zeilen (max. 60): Apple Vision vs. Tesseract vs. RapidOCR</h3>
<table><thead><tr><th>Bucket / Notizbuch</th><th>Bild</th><th>Konsens GT</th><th>Bester Apple Vision</th><th>Bester Tesseract</th><th>Bester RapidOCR</th></tr></thead><tbody id="samples"></tbody></table></div>
<script>
const PREFIX = {json.dumps(img_prefix)};
const COLORS = {{Tesseract:'#38bdf8', AppleVision:'#4ade80', RapidOCR:'#f59e0b'}};
function esc(s){{return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}}
function render(st){{
  document.getElementById('status').textContent = st.status;
  document.getElementById('pbar').style.width = (100*st.done/Math.max(1,st.total)).toFixed(0)+'%';
  const rows = [...st.results].sort((a,b)=>b.real_all-a.real_all);
  document.getElementById('lb').innerHTML = rows.map(r=>`<tr><td><strong>${{esc(r.name)}}</strong></td><td>${{esc(r.family)}}</td><td>${{r.math.toFixed(1)}}%</td><td>${{r.dev.toFixed(1)}}%</td><td><strong>${{r.hold.toFixed(1)}}%</strong></td><td><strong>${{r.real_all.toFixed(1)}}%</strong></td><td>${{r.synth.toFixed(1)}}%</td><td>${{r.ms.toFixed(0)}} ms</td><td class="${{r.gate==='OK'?'ok':'slow'}}">${{r.gate}}</td></tr>`).join('');
  let svg = '<rect x="42" y="12" width="372" height="214" fill="#0b1220" stroke="#334155"/>';
  const maxX = Math.max(400, ...rows.map(r=>r.ms*1.1), 1020);
  const gx = 42 + 372 * Math.min(1, 1000/maxX);
  svg += `<line x1="${{gx}}" y1="12" x2="${{gx}}" y2="226" stroke="#ef4444" stroke-dasharray="4,4"/><text x="${{gx-36}}" y="26" fill="#f87171" font-size="10">1000ms</text>`;
  for(const p of [0,25,50,75,100]){{ const y=226-214*(p/100); svg += `<text x="6" y="${{y+4}}" fill="#94a3b8" font-size="10">${{p}}%</text><line x1="42" y1="${{y}}" x2="414" y2="${{y}}" stroke="#1e293b"/>`; }}
  for(const r of rows){{
    const x = 42 + 372*Math.min(1, r.ms/maxX), y = 226 - 214*(r.real_all/100);
    const col = COLORS[r.family] || '#cbd5e1';
    svg += `<circle cx="${{x}}" cy="${{y}}" r="5" fill="${{col}}"/><text x="${{x+7}}" y="${{y+3}}" fill="${{col}}" font-size="9">${{esc(r.name)}}</text>`;
  }}
  document.getElementById('pareto').innerHTML = svg;
  document.getElementById('samples').innerHTML = (st.samples||[]).map(s=>`<tr><td><strong>${{esc(s.bucket)}}</strong><br><small style="color:#94a3b8">${{esc(s.nb)}}</small></td><td class="img-cell"><img loading="lazy" src="${{PREFIX}}${{esc(s.png_rel)}}"></td><td><code>${{esc(s.gt)}}</code></td><td><code>${{esc(s.vis_pred||'')}}</code> <small>(${{(s.vis_acc||0).toFixed(0)}}%)</small></td><td><code>${{esc(s.tess_pred||'')}}</code> <small>(${{(s.tess_acc||0).toFixed(0)}}%)</small></td><td><code>${{esc(s.w2_pred||'')}}</code> <small>(${{(s.w2_acc||0).toFixed(0)}}%)</small></td></tr>`).join('');
}}
render({json.dumps(state)});
{sse_js}
</script></body></html>"""
