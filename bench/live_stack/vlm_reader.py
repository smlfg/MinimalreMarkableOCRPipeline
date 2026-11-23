"""VLM-Reader: liest die gerenderten `.rm`-Seiten über das lokale Vision-Language-Model (`qwen2.5vl:7b`).

Beide Agenten (Tutor und Student) dürfen die `.rm`-Datei NICHT über gespeicherte Strings lesen,
sondern müssen das vom `.rm` gerenderte PNG über das VLM ablesen!
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from pathlib import Path

import rm_canvas

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
VLM_MODEL = os.environ.get("VLM_MODEL", "qwen2.5vl:7b")


def call_vlm(png_path: str | Path, prompt: str, *, model: str = VLM_MODEL, timeout: float = 45.0) -> str:
    """Sendet ein PNG-Bild + Prompt an das lokale VLM und gibt die Antwort zurück."""
    img_b64 = base64.b64encode(Path(png_path).read_bytes()).decode("ascii")
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return (data.get("response") or "").strip()


def clean_lines(raw_text: str) -> list[str]:
    """Bereinigt Markdown/LaTeX-Wrapper aus der VLM-Antwort in einzelne Textzeilen."""
    lines = []
    for raw in raw_text.splitlines():
        s = raw.strip()
        if not s or s.startswith("```"):
            continue
        s = re.sub(r"^\\[\(\[]|\\[\)\]]$", "", s).strip()
        s = s.strip("$").strip()
        if s:
            lines.append(s)
    return lines


def vlm_read_student_writing(rm_path: str | Path, out_png: str | Path, *, model: str = VLM_MODEL) -> dict:
    """Das VLM liest für den Tutor, was der Student auf die `.rm`-Seite geschrieben hat."""
    render_info = rm_canvas.render_page_png(rm_path, out_png, authors=("student",))
    prompt = (
        "Lies alle handgeschriebenen mathematischen Gleichungen auf diesem Bild Zeile für Zeile "
        "von oben nach unten exakt ab. Gib NUR die Gleichungen aus, eine pro Zeile, ohne Kommentar."
    )
    raw = call_vlm(out_png, prompt, model=model)
    lines = clean_lines(raw)
    strokes = rm_canvas.read_strokes(rm_path)
    line_boxes = rm_canvas.cluster_student_lines(strokes)
    return {
        "png_path": render_info["png_path"],
        "raw_vlm": raw,
        "lines": lines,
        "line_boxes": line_boxes,
    }


def vlm_read_student_strokes(strokes: list[dict], out_png: str | Path, *, model: str = VLM_MODEL) -> dict:
    """Wie `vlm_read_student_writing`, aber für bereits zusammengeführte Striche (Live-Stift + `.rm`).

    Der Mensch-Modus (`human_student`) liest nur die Striche des Menschen; Tutor-Striche hat der
    Aufrufer vorher ausgefiltert, weil `xochitl` sie bei `evdev`-Injektion in `Layer 1` ablegt.
    """
    student = [s for s in strokes if s.get("author") == "student" and s.get("points")]
    render_info = rm_canvas.render_strokes_png(student, out_png, authors=("student",))
    prompt = (
        "Lies alle handgeschriebenen mathematischen Gleichungen auf diesem Bild Zeile für Zeile "
        "von oben nach unten exakt ab. Gib NUR die Gleichungen aus, eine pro Zeile, ohne Kommentar."
    )
    raw = call_vlm(out_png, prompt, model=model) if student else ""
    return {
        "png_path": render_info["png_path"],
        "raw_vlm": raw,
        "lines": clean_lines(raw),
        "line_boxes": rm_canvas.cluster_student_lines(student),
    }


def vlm_read_tutor_feedback(rm_path: str | Path, out_png: str | Path, *, model: str = VLM_MODEL) -> dict:
    """Das VLM liest für den Studenten die gesamte Seite inklusive der farbigen Tutor-Notiz."""
    render_info = rm_canvas.render_page_png(rm_path, out_png, authors=("student", "tutor"))
    # Zusätzlich rendern wir für präzises Lesen der Tutor-Schrift die Tutor-Ebene als Bildausschnitt,
    # falls Tutor-Striche vorhanden sind — beides stammt 100 % aus den `.rm`-Strichen via VLM!
    tutor_png = Path(out_png).with_name(Path(out_png).stem + "_tutor_layer.png")
    rm_canvas.render_page_png(rm_path, tutor_png, authors=("tutor",))
    prompt_tutor = (
        "Lies den Texthinweis auf diesem Bild exakt ab. "
        "Gib nur den gelesenen deutschen Satz oder das Zeichen zurück, ohne Kommentar."
    )
    tutor_text = call_vlm(tutor_png, prompt_tutor, model=model)
    prompt_full = (
        "Auf diesem Arbeitsblatt stehen schwarze Gleichungen des Schülers und farbige "
        "(rote oder grüne) Anmerkungen des Tutors. Lies alle sichtbaren Zeilen ab."
    )
    full_text = call_vlm(out_png, prompt_full, model=model)
    return {
        "png_path": render_info["png_path"],
        "tutor_layer_png": str(tutor_png),
        "vlm_read_tutor_note": " ".join(clean_lines(tutor_text)),
        "vlm_read_full_page": clean_lines(full_text),
    }
