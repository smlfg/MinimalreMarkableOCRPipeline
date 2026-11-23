"""Dynamische Strich-Synthese (Catmull-Rom-Spline + organische Verformung + Druckkurve)
und dynamische 2D-Freiraum-Platzierung (`FreeGrid`) für Student und Tutor.

Kein starres Stempeln und keine festen Offset-Koordinaten mehr:
1. Jedes Zeichen wird bei jedem Schreiben mit eigener affiner Scherung, nichtlinearer
   Wellen-Deformation, individuellem Buchstaben-Scale/Rotation, Catmull-Rom-Kurvenglättung
   und realistischem Stiftdruck-Profil (Aufsetzen -> Druck -> Abheben) neu als Unikat erzeugt.
2. `FreeGrid` belegt alle vorhandenen `.rm`-Striche (Student + Tutor) in einem 2D-Gitter und
   sucht dynamisch einen kollisionsfreien Platz (rechts neben der Zeile, darunter, oder mit
   automatischem Verbindungs-Pfeil).
"""
from __future__ import annotations

import math
import random

import font as F

DOC_WIDTH = 1620
DOC_HEIGHT = 2160
CLEARANCE_PX = 14.0


def _catmull_rom_chain(pts: list[tuple[float, float]], samples_per_seg: int = 5) -> list[tuple[float, float]]:
    """Glättet eine Kontrollpunkt-Kette durch eine Catmull-Rom-Spline in eine flüssige Stiftkurve."""
    if len(pts) <= 2:
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 3.0))
            return [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
        return list(pts)

    padded = [pts[0]] + list(pts) + [pts[-1]]
    out: list[tuple[float, float]] = []
    for i in range(len(padded) - 3):
        p0, p1, p2, p3 = padded[i], padded[i + 1], padded[i + 2], padded[i + 3]
        seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        steps = max(2, min(samples_per_seg, int(seg_len / 2.2) + 1))
        for s in range(steps):
            t = s / steps
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2.0 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2.0 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1])
    return out


def _pressure_profile(n: int, rng: random.Random, base: float = 0.65) -> list[float]:
    """Erzeugt einen realistischen Stiftdruck-Verlauf vom Aufsetzen bis zum Abheben."""
    if n <= 1:
        return [round(base, 3)]
    peak_pos = rng.uniform(0.35, 0.65)
    amp = rng.uniform(0.22, 0.34)
    out = []
    for i in range(n):
        u = i / (n - 1)
        envelope = math.sin(math.pi * (u ** (0.8 / max(0.2, peak_pos))))
        p = max(0.18, min(0.96, base - 0.15 + amp * envelope + rng.gauss(0.0, 0.02)))
        out.append(round(p, 3))
    return out


def synthesize_handwriting_line(
    text: str,
    x0: float,
    baseline: float,
    *,
    scale: float = 3.2,
    color: str = "black",
    width: float = 3.2,
    author: str = "student",
    style: str = "student",
    seed: int | None = None,
) -> list[dict]:
    """Generiert eine Textzeile dynamisch als organische Stift-Striche.

    - `style="student"`: Stärkere Handschrift-Dynamik (Baseline-Drift/Slope, Buchstaben-Neigung,
      organische Kurven-Verformung, variabler Abstand).
    - `style="tutor"`: Ruhigere, gut lesbare Lehrer-Handschrift, aber ebenfalls jeder Buchstabe
      dynamisch per Spline, leichtem Schwung und echter Druckkurve gezeichnet.
    """
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    is_student = style == "student"

    # Globale Zeilen-Dynamik (Slope + sanfte Welle über die Zeile)
    slope = rng.uniform(-0.018, 0.028) if is_student else rng.uniform(-0.006, 0.008)
    wave_amp = scale * (rng.uniform(0.35, 0.85) if is_student else rng.uniform(0.12, 0.30))
    wave_freq = rng.uniform(0.006, 0.014)
    wave_phase = rng.uniform(0.0, math.tau)
    base_slant = rng.uniform(0.05, 0.19) if is_student else rng.uniform(0.02, 0.09)

    strokes: list[dict] = []
    pen_x = x0

    for idx, ch in enumerate(text):
        adv, polys = F.glyph(ch)
        if not polys:
            pen_x += (adv + rng.uniform(1.6, 2.8)) * scale
            continue

        # Lokale Buchstaben-Transformation (jedes Zeichen ein Unikat)
        sx = scale * (rng.uniform(0.90, 1.12) if is_student else rng.uniform(0.95, 1.06))
        sy = scale * (rng.uniform(0.90, 1.12) if is_student else rng.uniform(0.95, 1.06))
        char_slant = base_slant + (rng.uniform(-0.06, 0.06) if is_student else rng.uniform(-0.025, 0.025))
        theta = rng.uniform(-0.055, 0.055) if is_student else rng.uniform(-0.02, 0.02)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        char_dy = rng.gauss(0.0, scale * (0.28 if is_student else 0.12))

        for poly in polys:
            ctrl_pts: list[tuple[float, float]] = []
            n_poly = len(poly)
            for k, (gx, gy) in enumerate(poly):
                # Kontrollpunkt-Jitter (an Endpunkten etwas stärker für natürlichen Schwung)
                jit_scale = 0.28 if is_student else 0.14
                if k in (0, n_poly - 1):
                    jit_scale *= 1.25
                jx = gx + rng.gauss(0.0, jit_scale)
                jy = gy + rng.gauss(0.0, jit_scale)

                # Rotation + Scherung im lokalen Zeichenraum
                rx = jx * cos_t - jy * sin_t + char_slant * jy
                ry = jx * sin_t + jy * cos_t

                px = pen_x + rx * sx
                dx_from_start = px - x0
                line_drift = dx_from_start * slope + wave_amp * math.sin(dx_from_start * wave_freq + wave_phase)
                py = baseline + line_drift + char_dy - ry * sy
                ctrl_pts.append((px, py))

            smooth_pts = _catmull_rom_chain(ctrl_pts, samples_per_seg=5 if is_student else 4)
            pressures = _pressure_profile(len(smooth_pts), rng, base=0.72 if is_student else 0.68)
            stroke_w = round(width * rng.uniform(0.92, 1.08), 2)

            strokes.append({
                "points": [
                    [round(px, 2), round(py, 2), pr]
                    for (px, py), pr in zip(smooth_pts, pressures)
                ],
                "color": color,
                "width": stroke_w,
                "author": author,
                "char_index": idx,
                "char": ch,
            })

        tracking = rng.uniform(1.5, 2.7) if is_student else rng.uniform(1.8, 2.3)
        pen_x += (adv + tracking) * scale

    return strokes


def measure_text_width(text: str, scale: float, tracking: float = 2.1) -> float:
    if not text:
        return 0.0
    return sum((F.advance(ch) + tracking) for ch in text) * scale


def wrap_text_to_width(text: str, max_width_px: float, scale: float) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = w if not cur else f"{cur} {w}"
        if measure_text_width(cand, scale) <= max_width_px or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def synthesize_multiline_block(
    lines: list[str],
    x0: float,
    top_y: float,
    *,
    scale: float = 2.6,
    color: str = "red",
    width: float = 3.0,
    author: str = "tutor",
    style: str = "tutor",
    seed: int | None = None,
) -> tuple[list[dict], list[float]]:
    """Zeichnet einen mehrzeiligen dynamischen Textblock und gibt `(strokes, bbox)` zurück."""
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    line_h = F.CAP * 1.48 * scale
    all_strokes: list[dict] = []
    for i, line in enumerate(lines):
        baseline = top_y + F.CAP * scale + i * line_h
        st = synthesize_handwriting_line(
            line,
            x0=x0 + rng.uniform(-4.0, 4.0),
            baseline=baseline,
            scale=scale,
            color=color,
            width=width,
            author=author,
            style=style,
            seed=rng.randint(1, 10_000_000),
        )
        all_strokes.extend(st)
    xs = [p[0] for s in all_strokes for p in s["points"]]
    ys = [p[1] for s in all_strokes for p in s["points"]]
    bb = [min(xs), min(ys), max(xs), max(ys)] if xs else [x0, top_y, x0 + 10, top_y + 10]
    return all_strokes, [round(v, 1) for v in bb]


def dynamic_underline(bbox: list[float], *, color: str = "red", width: float = 3.5, seed: int | None = None) -> list[dict]:
    """Zeichnet eine handgezogene, leicht geschwungene Unterstreichung unter `bbox`."""
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    x0, _, x1, y1 = bbox
    y_base = y1 + rng.uniform(9.0, 14.0)
    ctrl = [
        (x0 + rng.uniform(-6.0, 4.0), y_base + rng.uniform(-2.5, 2.5)),
        ((2 * x0 + x1) / 3.0, y_base + rng.uniform(-3.5, 3.5)),
        ((x0 + 2 * x1) / 3.0, y_base + rng.uniform(-3.5, 3.5)),
        (x1 + rng.uniform(-4.0, 8.0), y_base + rng.uniform(-2.5, 2.5)),
    ]
    pts = _catmull_rom_chain(ctrl, samples_per_seg=8)
    press = _pressure_profile(len(pts), rng, base=0.75)
    return [{
        "points": [[round(x, 2), round(y, 2), pr] for (x, y), pr in zip(pts, press)],
        "color": color,
        "width": width,
        "author": "tutor",
    }]


def dynamic_tick(bbox: list[float], existing_strokes: list[dict], *, color: str = "green", width: float = 4.0, seed: int | None = None) -> list[dict]:
    """Zeichnet einen handgezogenen grünen Haken an eine freie Stelle neben der Zeilen-Box."""
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    x0, y0, x1, y1 = bbox
    size = max(30.0, min(58.0, (y1 - y0) * 0.46))
    grid = FreeGrid(existing_strokes)
    cy = (y0 + y1) / 2.0

    # Suche dynamisch rechts oder links der Zeile nach freiem Platz für den Haken
    chosen_cx = x1 + 28.0
    for dx in (26.0, 48.0, 72.0, -size - 28.0):
        cand_x = (x1 + dx) if dx > 0 else (x0 + dx)
        if grid.is_free(cand_x - 4, cy - size * 0.5, cand_x + size + 4, cy + size * 0.5):
            chosen_cx = cand_x
            break

    ctrl = [
        (chosen_cx + rng.uniform(-2, 2), cy + size * 0.05 + rng.uniform(-2, 2)),
        (chosen_cx + size * 0.32 + rng.uniform(-2, 2), cy + size * 0.42 + rng.uniform(-2, 2)),
        (chosen_cx + size * 0.98 + rng.uniform(-3, 3), cy - size * 0.46 + rng.uniform(-3, 3)),
    ]
    pts = _catmull_rom_chain(ctrl, samples_per_seg=6)
    press = _pressure_profile(len(pts), rng, base=0.78)
    return [{
        "points": [[round(x, 2), round(y, 2), pr] for (x, y), pr in zip(pts, press)],
        "color": color,
        "width": width,
        "author": "tutor",
    }]


def dynamic_arrow(start: tuple[float, float], end: tuple[float, float], *, color: str = "red", width: float = 3.0, seed: int | None = None) -> list[dict]:
    """Zeichnet einen leicht gebogenen handgezeichneten Pfeil von der Notiz zur Ziel-Box."""
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    (sx, sy), (ex, ey) = start, end
    mx = (sx + ex) / 2.0 + rng.uniform(-18.0, 18.0)
    my = (sy + ey) / 2.0 - rng.uniform(8.0, 24.0)
    shaft = _catmull_rom_chain([(sx, sy), (mx, my), (ex, ey)], samples_per_seg=6)
    ang = math.atan2(ey - my, ex - mx)
    head_len = 17.0
    left = (ex - head_len * math.cos(ang - 0.48), ey - head_len * math.sin(ang - 0.48))
    right = (ex - head_len * math.cos(ang + 0.48), ey - head_len * math.sin(ang + 0.48))
    head = _catmull_rom_chain([left, (ex, ey), right], samples_per_seg=4)
    return [
        {
            "points": [[round(x, 2), round(y, 2), 0.72] for x, y in shaft],
            "color": color,
            "width": width,
            "author": "tutor",
        },
        {
            "points": [[round(x, 2), round(y, 2), 0.75] for x, y in head],
            "color": color,
            "width": width,
            "author": "tutor",
        },
    ]


class FreeGrid:
    """2D-Belegungskarte aller existierenden Striche auf dem Blatt zur kollisionsfreien Platzierung."""

    def __init__(self, strokes: list[dict], *, width: int = DOC_WIDTH, height: int = 3600, cell: int = 12, pad: float = CLEARANCE_PX) -> None:
        self.cell = cell
        ys = [p[1] for s in strokes for p in s.get("points") or ()]
        max_y = int(max(ys, default=height)) + 600
        self.w = width
        self.h = max(height, max_y)
        self.cols = self.w // cell + 1
        self.rows = self.h // cell + 1
        self.blocked = [[False] * self.cols for _ in range(self.rows)]
        r = int(math.ceil(pad / cell))
        for s in strokes:
            pts = s.get("points") or ()
            for p in pts:
                c0 = int(float(p[0]) // cell)
                r0 = int(float(p[1]) // cell)
                for rr in range(max(0, r0 - r), min(self.rows, r0 + r + 1)):
                    row = self.blocked[rr]
                    for cc in range(max(0, c0 - r), min(self.cols, c0 + r + 1)):
                        row[cc] = True

    def is_free(self, x0: float, y0: float, x1: float, y1: float, margin: float = 24.0) -> bool:
        if x0 < margin or y0 < margin or x1 > self.w - margin or y1 > self.h - margin:
            return False
        c = self.cell
        r_start = max(0, int(y0 // c))
        r_end = min(self.rows - 1, int(y1 // c))
        c_start = max(0, int(x0 // c))
        c_end = min(self.cols - 1, int(x1 // c))
        for rr in range(r_start, r_end + 1):
            row = self.blocked[rr]
            for cc in range(c_start, c_end + 1):
                if row[cc]:
                    return False
        return True


def place_tutor_note_dynamically(
    note_text: str,
    anchor_box: list[float],
    existing_strokes: list[dict],
    *,
    color: str = "red",
    seed: int | None = None,
) -> dict:
    """Sucht auf dem Blatt dynamisch einen freien Platz für die Tutor-Notiz (Rechter Rand -> Unterhalb -> Freier Scan).

    Wenn die Notiz weiter entfernt platziert werden muss, wird automatisch ein Verbindungs-Pfeil
    zur `anchor_box` gezeichnet.
    """
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    grid = FreeGrid(existing_strokes)
    ax0, ay0, ax1, ay1 = anchor_box

    candidates: list[tuple[str, float, float, float, float]] = []
    # 1. Kandidat: Rechts neben der Schüler-Zeile in der Randspalte (falls breit genug)
    right_x = ax1 + 48.0
    right_w = DOC_WIDTH - 45.0 - right_x
    if right_w >= 340.0:
        for dy in (0.0, -24.0, 28.0, 56.0):
            candidates.append(("right_margin", right_x, max(30.0, ay0 + dy), right_w, 2.45))

    # 2. Kandidat: Direkt unterhalb der Schüler-Zeile auf freier Höhe
    below_x = max(140.0, min(ax0, 420.0))
    below_w = DOC_WIDTH - 60.0 - below_x
    for dy in (32.0, 58.0, 88.0, 120.0, 160.0):
        candidates.append(("below_anchor", below_x, ay1 + dy, below_w, 2.65))

    # 3. Fallback: Freier Scan weiter unten auf dem Blatt
    for y_scan in range(int(ay1 + 180), int(ay1 + 700), 55):
        for x_scan in (180.0, 320.0, 480.0):
            candidates.append(("free_scan", x_scan, float(y_scan), DOC_WIDTH - 70.0 - x_scan, 2.5))

    for spot_kind, x0, top_y, max_w, scale in candidates:
        lines = wrap_text_to_width(note_text, max_w, scale)
        est_w = max(measure_text_width(line, scale) for line in lines) + 16.0
        est_h = len(lines) * (F.CAP * 1.48 * scale) + 12.0
        if grid.is_free(x0, top_y, x0 + est_w, top_y + est_h):
            strokes, bb = synthesize_multiline_block(
                lines,
                x0=x0,
                top_y=top_y,
                scale=scale,
                color=color,
                width=3.0,
                author="tutor",
                style="tutor",
                seed=rng.randint(1, 10_000_000),
            )
            # Wenn die Notiz weiter weg liegt (> 115 px Abstand), zeichne einen Pfeil zur Zeile
            dist_y = max(0.0, bb[1] - ay1, ay0 - bb[3])
            if spot_kind == "free_scan" or dist_y > 115.0:
                start_pt = ((bb[0] + bb[2]) / 2.0, bb[1] - 6.0)
                end_pt = (min(max(start_pt[0], ax0 + 20.0), ax1 - 20.0), ay1 + 12.0)
                strokes.extend(dynamic_arrow(start_pt, end_pt, color=color, seed=rng.randint(1, 10_000_000)))
            return {
                "strokes": strokes,
                "bbox": bb,
                "spot_kind": spot_kind,
                "wrapped_lines": lines,
            }

    # Notfall-Platzierung ganz unten unter aller bestehenden Tinte
    all_ys = [p[1] for s in existing_strokes for p in s.get("points") or ()]
    bottom_y = max(all_ys, default=ay1) + 65.0
    lines = wrap_text_to_width(note_text, DOC_WIDTH - 260.0, 2.6)
    strokes, bb = synthesize_multiline_block(
        lines, x0=200.0, top_y=bottom_y, scale=2.6, color=color, author="tutor", style="tutor", seed=seed
    )
    return {"strokes": strokes, "bbox": bb, "spot_kind": "bottom_fallback", "wrapped_lines": lines}


def place_student_line_dynamically(
    eq_text: str,
    existing_strokes: list[dict],
    *,
    seed: int | None = None,
) -> dict:
    """Sucht auf dem Blatt dynamisch unter den bisherigen Zeilen einen freien Platz für die nächste Schüler-Gleichung."""
    rng = random.Random(seed if seed is not None else random.randrange(1, 10_000_000))
    grid = FreeGrid(existing_strokes)

    student_strokes = [s for s in existing_strokes if s.get("author") == "student" and s.get("points")]
    if student_strokes:
        s_xs = [p[0] for s in student_strokes for p in s["points"]]
        avg_left = max(180.0, min(480.0, min(s_xs) + rng.uniform(-18.0, 24.0)))
    else:
        avg_left = 320.0 + rng.uniform(-20.0, 25.0)

    all_ys = [p[1] for s in existing_strokes for p in s.get("points") or ()]
    start_y = max(all_ys, default=200.0) + rng.uniform(55.0, 80.0)
    scale = round(rng.uniform(3.3, 3.65), 2)
    est_w = measure_text_width(eq_text, scale) + 25.0
    est_h = F.CAP * scale * 1.4

    chosen_x, chosen_y = avg_left, start_y
    for dy in range(0, 500, 28):
        cand_y = start_y + dy
        for dx in (0.0, -35.0, 35.0, -70.0):
            cand_x = max(120.0, min(DOC_WIDTH - est_w - 40.0, avg_left + dx))
            if grid.is_free(cand_x, cand_y, cand_x + est_w, cand_y + est_h):
                chosen_x, chosen_y = cand_x, cand_y
                break
        else:
            continue
        break

    baseline_y = round(chosen_y + F.CAP * scale, 1)
    strokes = synthesize_handwriting_line(
        eq_text,
        x0=chosen_x,
        baseline=baseline_y,
        scale=scale,
        color="black",
        width=round(rng.uniform(3.2, 3.6), 2),
        author="student",
        style="student",
        seed=rng.randint(1, 10_000_000),
    )
    return {
        "strokes": strokes,
        "x0": round(chosen_x, 1),
        "baseline_y": baseline_y,
        "scale": scale,
    }


def split_strokes_into_random_bursts(
    text: str,
    strokes: list[dict],
    rng: random.Random | None = None,
    *,
    min_delay_s: float = 0.65,
    max_delay_s: float = 2.65,
) -> list[dict]:
    """Zerlegt eine Gleichungszeile in 2–3 zeitlich zufällige Schreib-Etappen (Bursts).

    Ein echter Schüler schreibt eine Gleichung nicht in 0 ms am Stück, sondern:
    - wartet eine zufällige Überlegungszeit vor dem ersten Strich (`wait_s`),
    - schreibt z. B. erst die linke Seite oder `3x + 6 =`,
    - pausiert zufällig lang mitten in der Zeile (`wait_s`),
    - und schreibt dann den Rest (`15`).
    """
    r = rng or random.Random()
    if not strokes:
        return []

    non_space_indices = [i for i, ch in enumerate(text) if not ch.isspace()]
    if len(non_space_indices) <= 2:
        w_s = round(r.uniform(min_delay_s, max_delay_s), 2)
        return [{
            "burst_index": 1,
            "burst_count": 1,
            "wait_s": w_s,
            "burst_text": text.strip(),
            "cumulative_text": text.strip(),
            "strokes": strokes,
            "is_final": True,
        }]

    # Wähle 2 oder 3 Schreib-Bursts anhand sinnvoller Trennpunkte (z. B. nach '=', '+', '-')
    n_bursts = r.choice((2, 3)) if len(non_space_indices) >= 5 else 2
    candidate_splits: list[int] = []
    for idx, ch in enumerate(text):
        if ch in ("=", "+", "-") and 1 <= idx < len(text) - 1:
            candidate_splits.append(idx + 1)

    split_points: list[int] = []
    if candidate_splits:
        r.shuffle(candidate_splits)
        for sp in sorted(candidate_splits[: n_bursts - 1]):
            if all(abs(sp - prev) >= 2 for prev in split_points):
                split_points.append(sp)

    while len(split_points) < n_bursts - 1:
        sp = r.randint(2, max(2, len(text) - 2))
        if sp not in split_points:
            split_points.append(sp)
    split_points.sort()

    ranges: list[tuple[int, int]] = []
    prev = 0
    for sp in split_points:
        ranges.append((prev, sp))
        prev = sp
    ranges.append((prev, len(text)))

    raw_chunks: list[tuple[str, str, list[dict]]] = []
    for start_i, end_i in ranges:
        c_strokes = [s for s in strokes if start_i <= int(s.get("char_index", 0)) < end_i]
        if not c_strokes:
            continue
        b_txt = text[start_i:end_i].strip()
        cum_txt = text[:end_i].strip()
        raw_chunks.append((b_txt, cum_txt, c_strokes))

    if not raw_chunks:
        raw_chunks = [(text.strip(), text.strip(), strokes)]

    bursts: list[dict] = []
    total = len(raw_chunks)
    for idx, (b_txt, cum_txt, c_strokes) in enumerate(raw_chunks):
        # Erste Etappe = Überlegungszeit vor dem Ansetzen; Folge-Etappen = Zögern mitten in der Gleichung
        wait_s = round(
            r.uniform(min_delay_s * 1.15, max_delay_s * 1.15)
            if idx == 0
            else r.uniform(min_delay_s * 0.75, max_delay_s * 0.95),
            2,
        )
        bursts.append({
            "burst_index": idx + 1,
            "burst_count": total,
            "wait_s": wait_s,
            "burst_text": b_txt,
            "cumulative_text": cum_txt,
            "strokes": c_strokes,
            "is_final": idx == total - 1,
        })
    return bursts
