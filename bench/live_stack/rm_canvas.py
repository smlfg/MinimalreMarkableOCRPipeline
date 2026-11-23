"""Lesen, Schreiben (byte-identischer Prefix-Append) und Rendern von reMarkable v6 `.rm` Dateien.

Trennt sauber zwischen:
- Student-Strichen (`layer="Layer 1"`, `author="student"`, Farbe schwarz)
- Tutor-Strichen (`layer="PenEcho Agent"`, `author="tutor"`, Farben rot/grün/blau)

Koordinatensystem: Paper Pro `DOC_WIDTH = 1620`, `DOC_HEIGHT = 2160` (x=0 in der Datei ist Seitenmitte 810).
"""
from __future__ import annotations

import dataclasses
import io
import logging
import math
import random
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageDraw
from rmscene import read_blocks, read_tree, scene_items as si, write_blocks
from rmscene.crdt_sequence import CrdtSequenceItem
from rmscene.scene_stream import SceneGroupItemBlock, SceneLineItemBlock, SceneTreeBlock, TreeNodeBlock
from rmscene.tagged_block_common import HEADER_V6, CrdtId, LwwValue

import dynamic_writer
import font as F

DOC_WIDTH = 1620
DOC_HEIGHT = 2160
STUDENT_LAYER = "Layer 1"
TUTOR_LAYER = "PenEcho Agent"
TUTOR_LAYERS = {TUTOR_LAYER, "InkPartner Agent", "Underline Agent", "inkpartner"}

DISPLAY_RGB = {
    "black": (20, 20, 20),
    "gray": (128, 128, 128),
    "red": (215, 30, 30),
    "green": (0, 150, 70),
    "blue": (20, 70, 200),
    "yellow": (235, 214, 0),
}

PEN_COLOR = {
    "black": "BLACK",
    "gray": "GRAY",
    "red": "RED",
    "green": "GREEN",
    "blue": "BLUE",
    "yellow": "YELLOW",
}


@contextmanager
def _quiet_rmscene():
    names = ["rmscene"] + [
        name for name, lg in logging.Logger.manager.loggerDict.items()
        if name.startswith("rmscene.") and isinstance(lg, logging.Logger)
    ]
    levels = {name: logging.getLogger(name).level for name in names}
    try:
        for name in names:
            logging.getLogger(name).setLevel(logging.ERROR)
        yield
    finally:
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)


def to_page(x: float, y: float) -> tuple[float, float]:
    return x + DOC_WIDTH / 2.0, y


def to_doc(x: float, y: float) -> tuple[float, float]:
    return x - DOC_WIDTH / 2.0, y


def _walk_layers(tree):
    def walk(group, label):
        for child in group.children.values():
            if isinstance(child, si.Group):
                yield from walk(child, child.label.value if child.label else label)
            elif isinstance(child, si.Line):
                yield label or "", child

    yield from walk(tree.root, None)


def read_strokes(rm_path: str | Path) -> list[dict]:
    """Liest alle Striche einer `.rm`-Seite mit `points`, `color`, `width`, `layer`, `author`."""
    with _quiet_rmscene(), open(rm_path, "rb") as f:
        tree = read_tree(f)
    out: list[dict] = []
    for label, line in _walk_layers(tree):
        pts = [
            [round(px, 2), round(py, 2), round(pt.pressure / 255.0, 3)]
            for pt in line.points
            for px, py in [to_page(pt.x, pt.y)]
        ]
        if not pts:
            continue
        widths = [float(p.width) for p in line.points if getattr(p, "width", 0)]
        w = max(1.5, min(20.0, (sum(widths) / len(widths)) / 4.0)) if widths else 3.0
        color_name = line.color.name.lower()
        author = "tutor" if label in TUTOR_LAYERS else "student"
        out.append({
            "points": pts,
            "color": color_name,
            "width": round(w, 2),
            "layer": label,
            "author": author,
        })
    return out


def _crdt_ids(obj, out, seen=None):
    seen = seen if seen is not None else set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, CrdtId):
        out.append(obj)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            _crdt_ids(getattr(obj, f.name), out, seen)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _crdt_ids(k, out, seen)
            _crdt_ids(v, out, seen)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            _crdt_ids(v, out, seen)
    elif hasattr(obj, "sequence_items"):
        for v in obj.sequence_items():
            _crdt_ids(v, out, seen)


def _line_item(stroke: dict) -> si.Line:
    pts = []
    w_raw = max(1, int(round(float(stroke.get("width", 3.0)) * 4.0)))
    for p in stroke["points"]:
        dx, dy = to_doc(float(p[0]), float(p[1]))
        press = int(255 * (float(p[2]) if len(p) > 2 else 0.7))
        pts.append(si.Point(x=dx, y=dy, speed=0, direction=0, width=w_raw, pressure=press))
    col_enum = getattr(si.PenColor, PEN_COLOR.get(stroke.get("color", "black"), "BLACK"))
    return si.Line(
        color=col_enum,
        tool=si.Pen.FINELINER_2,
        points=pts,
        thickness_scale=1.0,
        starting_length=0.0,
    )


def write_new_student_page(
    lines: list[str],
    path_out: str | Path,
    *,
    x0: float = 320.0,
    top_y: float = 240.0,
    spacing_y: float = 175.0,
    seed: int = 42,
) -> dict:
    """Erzeugt eine frische `.rm`-v6-Seite mit handgeschriebenen Schüler-Zeilen in `Layer 1`."""
    from uuid import UUID
    from rmscene.scene_stream import AuthorIdsBlock, MigrationInfoBlock, PageInfoBlock

    all_strokes: list[dict] = []
    for i, line_text in enumerate(lines):
        st = text_to_strokes(
            line_text,
            x0=x0 + (i % 2) * 14.0,
            baseline=top_y + i * spacing_y,
            scale=3.5,
            color="black",
            width=3.4,
            author="student",
            jitter_seed=seed + i * 17,
        )
        all_strokes.extend(st)

    counter = 100

    def new_id() -> CrdtId:
        nonlocal counter
        counter += 1
        return CrdtId(1, counter)

    root_id = CrdtId(0, 1)
    layer_id = new_id()
    blocks = [
        AuthorIdsBlock(author_uuids={1: UUID("6a1c0d2e-0000-4000-8000-a1ce0a6e47a1")}),
        MigrationInfoBlock(migration_id=CrdtId(1, 1), is_device=True),
        PageInfoBlock(loads_count=1, merges_count=0, text_chars_count=0, text_lines_count=0),
        TreeNodeBlock(si.Group(node_id=root_id)),
        SceneTreeBlock(tree_id=layer_id, node_id=CrdtId(0, 0), is_update=True, parent_id=root_id),
        TreeNodeBlock(si.Group(node_id=layer_id, label=LwwValue(timestamp=new_id(), value=STUDENT_LAYER))),
        SceneGroupItemBlock(
            parent_id=root_id,
            item=CrdtSequenceItem(
                item_id=new_id(),
                left_id=CrdtId(0, 0),
                right_id=CrdtId(0, 0),
                deleted_length=0,
                value=layer_id,
            ),
        ),
    ]
    left = CrdtId(0, 0)
    for s in all_strokes:
        iid = new_id()
        blocks.append(
            SceneLineItemBlock(
                parent_id=layer_id,
                item=CrdtSequenceItem(
                    item_id=iid,
                    left_id=left,
                    right_id=CrdtId(0, 0),
                    deleted_length=0,
                    value=_line_item(s),
                ),
            )
        )
        left = iid

    Path(path_out).parent.mkdir(parents=True, exist_ok=True)
    with open(path_out, "wb") as f:
        write_blocks(f, blocks)
    return {"path": str(path_out), "strokes": len(all_strokes), "lines": lines}


def write_blank_rm_page(path_out: str | Path) -> dict:
    """Erzeugt ein komplett leeres, weißes `.rm`-v6-Blatt (0 Striche)."""
    return write_new_student_page([], path_out)


def append_strokes(
    path_in: str | Path,
    strokes: list[dict],
    path_out: str | Path,
    *,
    layer_name: str = TUTOR_LAYER,
) -> dict:
    """Hängt neue Striche byte-identisch (Prefix bleibt unangetastet) in `layer_name` an."""
    original = Path(path_in).read_bytes()
    with _quiet_rmscene():
        blocks = list(read_blocks(io.BytesIO(original)))
        tree = read_tree(io.BytesIO(original))

    ids: list[CrdtId] = []
    _crdt_ids(blocks, ids)
    counter = max([i.part2 for i in ids if i.part1 == 1] + [100]) + 1

    def new_id() -> CrdtId:
        nonlocal counter
        counter += 1
        return CrdtId(1, counter - 1)

    new_blocks = []
    target_layer = None
    for child in tree.root.children.values():
        if isinstance(child, si.Group) and child.label and child.label.value == layer_name:
            target_layer = child
            break

    if target_layer is None:
        layer_id = new_id()
        root_keys = list(tree.root.children.keys())
        new_blocks.append(
            SceneTreeBlock(tree_id=layer_id, node_id=CrdtId(0, 0), is_update=True, parent_id=CrdtId(0, 1))
        )
        new_blocks.append(
            TreeNodeBlock(si.Group(node_id=layer_id, label=LwwValue(timestamp=new_id(), value=layer_name)))
        )
        new_blocks.append(
            SceneGroupItemBlock(
                parent_id=CrdtId(0, 1),
                item=CrdtSequenceItem(
                    item_id=new_id(),
                    left_id=root_keys[-1] if root_keys else CrdtId(0, 0),
                    right_id=CrdtId(0, 0),
                    deleted_length=0,
                    value=layer_id,
                ),
            )
        )
        left = CrdtId(0, 0)
    else:
        layer_id = target_layer.node_id
        keys = list(target_layer.children.keys())
        left = keys[-1] if keys else CrdtId(0, 0)

    for s in strokes:
        iid = new_id()
        new_blocks.append(
            SceneLineItemBlock(
                parent_id=layer_id,
                item=CrdtSequenceItem(
                    item_id=iid,
                    left_id=left,
                    right_id=CrdtId(0, 0),
                    deleted_length=0,
                    value=_line_item(s),
                ),
            )
        )
        left = iid

    buf = io.BytesIO()
    write_blocks(buf, new_blocks)
    tail = buf.getvalue()
    assert tail.startswith(HEADER_V6)
    out_bytes = original + tail[len(HEADER_V6):]
    Path(path_out).write_bytes(out_bytes)
    return {
        "original_bytes": len(original),
        "appended_bytes": len(tail) - len(HEADER_V6),
        "total_bytes": len(out_bytes),
        "new_strokes": len(strokes),
        "layer": layer_name,
    }


def stroke_bbox(strokes: list[dict]) -> list[float] | None:
    xs = [p[0] for s in strokes for p in s.get("points") or ()]
    ys = [p[1] for s in strokes for p in s.get("points") or ()]
    if not xs:
        return None
    return [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]


def cluster_student_lines(strokes: list[dict], pad: float = 22.0) -> list[dict]:
    """Findet die vertikalen Zeilen-Boxen der Student-Striche."""
    student = [s for s in strokes if s.get("author") == "student" and s.get("points")]
    boxes = []
    for s in student:
        b = stroke_bbox([s])
        if b:
            boxes.append(b)
    if not boxes:
        return []
    rows: list[list[float]] = []
    for b in sorted(boxes, key=lambda r: r[1]):
        if rows and b[1] <= rows[-1][3] + pad:
            r = rows[-1]
            rows[-1] = [min(r[0], b[0]), min(r[1], b[1]), max(r[2], b[2]), max(r[3], b[3])]
        else:
            rows.append(list(b))
    return [{"index": i, "bbox": [round(v, 1) for v in r]} for i, r in enumerate(rows)]


def render_page_png(
    rm_path: str | Path,
    png_path: str | Path,
    *,
    authors: tuple[str, ...] = ("student", "tutor"),
    pad: float = 40.0,
) -> dict:
    """Rendert die `.rm`-Seite auf den aktiven Tinten-Ausschnitt zugeschnitten als PNG."""
    return render_strokes_png(read_strokes(rm_path), png_path, authors=authors, pad=pad)


def render_strokes_png(
    all_strokes: list[dict],
    png_path: str | Path,
    *,
    authors: tuple[str, ...] = ("student", "tutor"),
    pad: float = 40.0,
) -> dict:
    """Rendert bereits geparste Striche (z. B. Live-Stift + `.rm`) auf den Tinten-Ausschnitt als PNG."""
    strokes = [s for s in all_strokes if s.get("author") in authors]
    box = stroke_bbox(strokes)
    if box is None:
        im = Image.new("RGB", (1250, 600), "white")
        Path(png_path).parent.mkdir(parents=True, exist_ok=True)
        im.save(png_path, "PNG")
        return {"png_path": str(png_path), "width": 1250, "height": 600, "crop_box": [200.0, 0.0, 1450.0, 600.0]}
    x0 = min(200.0, box[0] - pad)
    y0 = max(0.0, box[1] - pad)
    x1 = max(1450.0, box[2] + pad)
    y1 = box[3] + pad
    w = max(1, int(round(x1 - x0)))
    h = max(1, int(round(y1 - y0)))
    im = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(im)
    for s in strokes:
        pts = s.get("points") or ()
        if not pts:
            continue
        xy = [(p[0] - x0, p[1] - y0) for p in pts]
        lw = max(2, int(round(float(s.get("width", 3.0)))))
        rgb = DISPLAY_RGB.get(s.get("color", "black"), DISPLAY_RGB["black"])
        if len(xy) == 1:
            px, py = xy[0]
            draw.ellipse([px - lw / 2, py - lw / 2, px + lw / 2, py + lw / 2], fill=rgb)
        else:
            draw.line(xy, fill=rgb, width=lw, joint="curve")
    Path(png_path).parent.mkdir(parents=True, exist_ok=True)
    im.save(png_path, "PNG")
    return {"png_path": str(png_path), "width": w, "height": h, "crop_box": [x0, y0, x1, y1]}


def text_to_strokes(
    text: str,
    x0: float,
    baseline: float,
    *,
    scale: float = 3.2,
    color: str = "black",
    width: float = 3.2,
    author: str = "student",
    jitter_seed: int | None = None,
    tracking: float = 2.0,
) -> list[dict]:
    """Delegiert an die dynamische Spline-Handschrift-Synthese (`dynamic_writer`)."""
    style = "student" if author == "student" else "tutor"
    return dynamic_writer.synthesize_handwriting_line(
        text,
        x0=x0,
        baseline=baseline,
        scale=scale,
        color=color,
        width=width,
        author=author,
        style=style,
        seed=jitter_seed,
    )


def underline_strokes(bbox: list[float], *, color: str = "red", width: float = 3.5, seed: int | None = None) -> list[dict]:
    """Zeichnet eine dynamische, leicht geschwungene Unterstreichung unter `bbox`."""
    return dynamic_writer.dynamic_underline(bbox, color=color, width=width, seed=seed)


def tick_strokes(
    bbox: list[float],
    *,
    color: str = "green",
    width: float = 4.0,
    existing_strokes: list[dict] | None = None,
    seed: int | None = None,
) -> list[dict]:
    """Zeichnet einen dynamisch platzierten und geschwungenen grünen Haken neben `bbox`."""
    return dynamic_writer.dynamic_tick(bbox, existing_strokes or [], color=color, width=width, seed=seed)
