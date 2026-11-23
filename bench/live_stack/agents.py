"""Algebra Tutor Agent & Algebra Student Agent.

- AlgebraTutorAgent:
  Empfängt ausschließlich den VLM-Lese-Output der Student-Schrift, prüft jeden Schritt
  mathematisch exakt (gegen die Aufgabe UND gegen die Vorzeile, damit Folgeschritte oder
  Reparaturen erkannt werden), formuliert einen kurzen deutschen Regel-Hinweis OHNE Lösungsverrat
  und schreibt ihn als echte `.rm`-Striche in die Tutor-Ebene (`PenEcho Agent`).

- AlgebraStudentAgent:
  Empfängt ausschließlich den VLM-Lese-Output der Seite (inkl. des vom VLM abgelesenen
  Tutor-Hinweises!), überlegt über das LLM seinen nächsten Rechenschritt und schreibt
  die neue Gleichungszeile als handgeschriebene `.rm`-Striche in die Student-Ebene (`Layer 1`).
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.request
from fractions import Fraction
from pathlib import Path

import dynamic_writer
import math_parser
import rm_canvas

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
STUDENT_LLM = os.environ.get("STUDENT_LLM", "qwen2.5vl:7b")

HINT_DIST = "Distributivgesetz: Klammer komplett ausmultiplizieren"
HINT_SIGN = "Vorzeichenregel: Beim Seitenwechsel Vorzeichen umkehren"
HINT_DIV = "Divisionsregel: Beide Seiten komplett durch den Faktor teilen"
HINT_GENERIC = "Umformung prüfen: Gleiche Operation auf beiden Seiten"


def generate_dynamic_student_task(rng: random.Random | None = None) -> dict:
    """Generiert prozedural (nicht hartcodiert) eine zufällige lineare Gleichung + typischen Erstfehler."""
    r = rng or random.Random()
    kind = r.choice(("distributiv_plus", "distributiv_minus", "vorzeichen_wechsel", "division_fehler"))
    x_sol = r.choice((2, 3, 4, 5, 6, 7, 8))

    if kind == "distributiv_plus":
        a = r.choice((2, 3, 4, 5, 6))
        b = r.choice((1, 2, 3, 4, 5))
        rhs = a * (x_sol + b)
        return {
            "name": f"Dynamisch generiert (Distributivgesetz mit Faktor {a})",
            "task": f"{a}(x+{b}) = {rhs}",
            "wrong_first": f"{a}x + {b} = {rhs}",
            "use_alt_file": False,
        }
    if kind == "distributiv_minus":
        a = r.choice((2, 3, 4, 5))
        b = r.choice((1, 2, 3))
        if x_sol <= b:
            x_sol = b + r.choice((2, 3, 4))
        rhs = a * (x_sol - b)
        return {
            "name": f"Dynamisch generiert (Klammer mit Minus, Faktor {a})",
            "task": f"{a}(x-{b}) = {rhs}",
            "wrong_first": f"{a}x - {b} = {rhs}",
            "use_alt_file": False,
        }
    if kind == "vorzeichen_wechsel":
        a = r.choice((2, 3, 4, 5))
        b = r.choice((3, 4, 5, 6, 7, 8))
        rhs = a * x_sol + b
        return {
            "name": "Dynamisch generiert (Vorzeichen-Falle beim Seitenwechsel)",
            "task": f"{a}x + {b} = {rhs}",
            "wrong_first": f"{a}x = {rhs + b}",
            "use_alt_file": False,
        }
    # division_fehler
    a = r.choice((2, 3, 4, 5))
    k = r.choice((2, 3, 4))
    b = a * k
    rhs = a * x_sol + b
    return {
        "name": f"Dynamisch generiert (Divisionsfehler durch {a})",
        "task": f"{a}x + {b} = {rhs}",
        "wrong_first": f"x + {b} = {rhs // a}",
        "use_alt_file": False,
    }

def _psub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def classify_line(line: str) -> dict:
    """Klassifiziert eine VLM-Zeile (Gleichung, Arithmetik, Term, offenes `=`, Summe, Frage, Text)."""
    return math_parser.classify_line(line)


def analyze_equation(line: str) -> dict:
    """Parst eine Gleichung `LHS = RHS` in exakte rationale Koeffizienten (inkl. LaTeX)."""
    info = math_parser.classify_line(line)
    if info.get("ok"):
        return info
    return {"ok": False, "kind": info.get("kind", "unparsed"), "parsed": bool(info.get("parsed"))}


def _eval_univariate_poly(poly: math_parser.Poly, var: str, val: Fraction) -> Fraction:
    """Wertet ein univariates Polynom an der Stelle `var = val` exakt aus."""
    total = Fraction(0)
    for monom, coef in poly.items():
        if not monom:
            total += coef
        elif len(monom) == 1 and monom[0][0] == var:
            total += coef * (val ** monom[0][1])
        else:
            raise ValueError("multivariate")
    return total


def _polys_proportional(a: math_parser.Poly, b: math_parser.Poly) -> bool:
    """Prüft, ob `a = c * b` für eine rationale Konstante `c != 0` gilt."""
    if len(a) != len(b) or not a:
        return len(a) == len(b) == 0
    ratio: Fraction | None = None
    for m, ca in a.items():
        cb = b.get(m)
        if cb is None or cb == 0:
            return False
        cur = ca / cb
        if ratio is None:
            ratio = cur
        elif cur != ratio:
            return False
    return True


def diagnose_mistake(basis: dict, cur: dict) -> str:
    """Erkennt den konkreten Regelfehler beim Übergang `basis -> cur`."""
    if "sides" in basis and "sides" in cur:
        for i in (0, 1):
            if "(" in basis["side_raw"][i] and "(" not in cur["side_raw"][i]:
                bs, cs = basis["sides"][i], cur["sides"][i]
                if cs[1] == bs[1] and cs[0] != bs[0]:
                    return HINT_DIST
        dl = _psub(cur["sides"][0], basis["sides"][0])
        dr = _psub(cur["sides"][1], basis["sides"][1])
        if dl[1] == 0 and dr[1] == 0 and dl[0] != 0 and dr[0] == -dl[0]:
            return HINT_SIGN
        bl, cl = basis["sides"][0], cur["sides"][0]
        br, cr = basis["sides"][1], cur["sides"][1]
        if bl[1] != 0 and cl[1] != 0:
            j = cl[1] / bl[1]
            if j != 1 and cr[0] == j * br[0] and cl[0] == bl[0] and bl[0] != 0:
                return HINT_DIV
    return HINT_GENERIC


def _find_anchor_for_var(classified: list[dict], var: str) -> dict | None:
    """Findet die relevante Start-Gleichung für `var` (ignoriert vorangehende Fremdzeilen / First-Line-Curse)."""
    anchor: dict | None = None
    anchor_solved = False
    for item in classified[:-1]:
        if item.get("kind") in ("linear_1var", "poly_1var") and item.get("var") == var:
            if anchor is None or (anchor_solved and not item.get("solved")):
                anchor = item
                anchor_solved = bool(item.get("solved"))
            elif item.get("solved") and item.get("solution") == anchor.get("solution"):
                anchor_solved = True
        elif item.get("kind") == "poly_multi" and var in item.get("vars", []):
            if anchor is None or anchor_solved:
                anchor = item
                anchor_solved = False
    return anchor


def _judge_line_sequence(classified: list[dict]) -> tuple[str, str, str]:
    """Bestimmt `(verdict, note, color)` aus der gesamten klassifizierten Zeilenliste (niemals G1/G2)."""
    cur = classified[-1]
    kind = cur["kind"]

    if kind == "incomplete_rhs":
        return "incomplete", "Rechte Seite fehlt noch — Term ausrechnen", "red"

    if kind == "chained_rhs":
        for prev in reversed(classified[:-1]):
            pk = prev.get("kind")
            if pk == "term":
                combined = math_parser.classify_line(f"{prev['norm']} {cur['raw']}")
                if combined.get("ok"):
                    cur = combined
                    kind = cur["kind"]
                    break
            elif "=" in prev.get("raw", "") and pk != "chained_rhs":
                lhs_base = prev["raw"].split("=", 1)[0].strip()
                if lhs_base:
                    combined = math_parser.classify_line(f"{lhs_base} {cur['raw']}")
                    if combined.get("ok"):
                        cur = combined
                        kind = cur["kind"]
                        break
        else:
            return "incomplete", "Fortsetzung nach = : Zwischenschritt prüfen", "red"

    if kind in ("term", "term_numeric"):
        if len(classified) >= 2 and classified[-2]["kind"] == "incomplete_rhs":
            merged = math_parser.classify_line(f"{classified[-2]['lhs_str']} = {cur['norm']}")
            if merged.get("ok"):
                cur = merged
                kind = cur["kind"]
        elif kind == "term":
            if len(classified) >= 2 and classified[-2]["kind"] == "term":
                same = (math_parser._poly_sub(cur["poly"], classified[-2]["poly"]) == {})
                if same:
                    return "correct_step", "Richtige Termumformung! Weiter so", "green"
                return "wrong", "Termumformung prüfen: Ausgangsterm nicht gleichwertig", "red"
            if cur.get("is_const"):
                return "incomplete", "Rechenterm erkannt — Ergebnis mit = ergänzen", "red"
            return "incomplete", "Term erkannt — Gleichung oder Umformung fortsetzen", "red"
        if kind == "term_numeric":
            return "incomplete", "Rechenausdruck erkannt — Ergebnis mit = ergänzen", "red"

    if kind == "scalar":
        return "incomplete", "Einzelwert erkannt — vollständigen Rechenschritt notieren", "red"

    if kind == "question":
        return "question", "Frage erkannt — ersten Ansatz mit = aufschreiben", "green"

    if kind == "sum":
        return "sum", "Summenformel erkannt — schreibe ein paar Summanden mit + auf", "green"

    if not cur.get("ok"):
        if "=" in cur.get("raw", ""):
            return "non_math", "Kein reiner Rechenterm — Gleichung isoliert schreiben", "red"
        return "non_math", "Text erkannt — bitte Rechenzeile notieren", "red"

    if kind == "arithmetic":
        if cur["correct"]:
            return "solved", "Richtig gerechnet! Prima!", "green"
        return "wrong", f"Nicht ganz: Linke Seite ergibt {cur['left_val']}", "red"

    if kind in ("chained_equation", "chained_equation_num"):
        if cur["all_equal"]:
            return "solved", "Richtig gerechnet! Prima!", "green"
        return "wrong", "Kettenrechnung prüfen: Zwischenschritt stimmt nicht", "red"

    if kind == "numeric_identity":
        if cur["is_identity"]:
            return "solved", "Richtig umgeformt! Prima!", "green"
        return "wrong", "Umformung prüfen: Beide Seiten stimmen nicht überein", "red"

    if kind in ("poly_multi", "poly_1var"):
        if cur.get("is_identity"):
            return "solved", "Richtig umgeformt! Prima!", "green"
        if cur.get("is_contradiction"):
            return "wrong", "Widerspruch in Gleichung: Beide Seiten prüfen", "red"
        if cur.get("has_expansion_on_lhs"):
            return "wrong", "Klammer-/Potenzregel prüfen: Faktoren und Exponenten genau ausrechnen", "red"
        anchor = _find_anchor_for_var(classified, cur["var"]) if cur.get("var") else None
        if anchor is None:
            return "task_ready", "Aufgabe steht! Rechne den ersten Schritt", "green"
        if "diff_poly" in anchor and "diff_poly" in cur and _polys_proportional(cur["diff_poly"], anchor["diff_poly"]):
            return "correct_step", "Richtige Umformung! Weiter auflösen", "green"
        return "wrong", HINT_GENERIC, "red"

    var = cur["var"]
    anchor = _find_anchor_for_var(classified, var)
    if anchor is None:
        if cur["solved"]:
            return "solved", "Richtig gelöst! Prima!", "green"
        return "task_ready", "Aufgabe steht! Rechne den ersten Schritt", "green"

    if anchor.get("kind") == "poly_1var" and "diff_poly" in anchor and cur.get("solved") and cur.get("solution") is not None:
        try:
            if _eval_univariate_poly(anchor["diff_poly"], var, cur["solution"]) == 0:
                return "solved", "Richtig gelöst! Prima!", "green"
        except Exception:
            pass
        return "wrong", "Probe prüfen: Wert erfüllt Ausgangsgleichung nicht", "red"

    if anchor.get("solution") is not None and cur["solution"] != anchor["solution"]:
        basis = anchor
        for prev in reversed(classified[:-1]):
            if prev.get("kind") == "linear_1var" and prev.get("var") == var and prev.get("solution") == anchor["solution"]:
                basis = prev
                break
        return "wrong", diagnose_mistake(basis, cur), "red"

    if cur["solved"]:
        return "solved", "Richtig gelöst! Prima!", "green"
    return "correct_step", f"Richtiger Schritt! Jetzt nach {var} auflösen", "green"


class AlgebraTutorAgent:
    """Liest über das VLM die Schülerschrift, prüft den neuesten Schritt und schreibt dynamisch auf die `.rm`-Seite."""

    def plan_feedback(
        self,
        vlm_student_read: dict,
        rm_in: str | Path | None,
        *,
        existing_strokes: list[dict] | None = None,
    ) -> dict:
        """Berechnet Urteil, Hinweis-Text und dynamisch platzierte Tutor-Striche (ohne Datei-Write).

        `existing_strokes` (Mensch-Modus): vollständige Belegung des Blatts (`.rm` + Live-Stift +
        bereits injizierte Tutor-Striche) für `FreeGrid`, statt die `.rm`-Datei zu lesen.
        """
        lines = vlm_student_read["lines"]
        boxes = vlm_student_read["line_boxes"]
        if not lines:
            raise ValueError("Tutor sieht keine Zeilen vom VLM.")

        if existing_strokes is None:
            existing_strokes = rm_canvas.read_strokes(rm_in)
        latest_idx = len(lines) - 1
        latest_text = lines[latest_idx]
        anchor_box = boxes[min(latest_idx, len(boxes) - 1)]["bbox"] if boxes else [350.0, 500.0, 1000.0, 620.0]

        classified = [classify_line(ln) for ln in lines]
        verdict, note, color = _judge_line_sequence(classified)
        if color == "green":
            mark_strokes = rm_canvas.tick_strokes(anchor_box, color="green", existing_strokes=existing_strokes)
        else:
            mark_strokes = rm_canvas.underline_strokes(anchor_box, color="red")

        # Dynamische Freiraum-Suche (FreeGrid) statt hartcodiertem y+78
        placement = dynamic_writer.place_tutor_note_dynamically(
            note,
            anchor_box,
            existing_strokes + mark_strokes,
            color=color,
        )
        all_tutor_strokes = mark_strokes + placement["strokes"]
        return {
            "latest_line_read": latest_text,
            "verdict": verdict,
            "tutor_note_written": note,
            "color": color,
            "spot_kind": placement["spot_kind"],
            "note_bbox": placement["bbox"],
            "tutor_strokes": all_tutor_strokes,
        }

    def evaluate_and_write(self, vlm_student_read: dict, rm_in: str | Path, rm_out: str | Path) -> dict:
        plan = self.plan_feedback(vlm_student_read, rm_in)
        append_info = rm_canvas.append_strokes(
            rm_in,
            plan["tutor_strokes"],
            rm_out,
            layer_name=rm_canvas.TUTOR_LAYER,
        )
        return {
            **plan,
            "append_info": append_info,
        }


class AlgebraStudentAgent:
    """Liest über das VLM die Seite inkl. Tutor-Hinweis und schreibt die nächste Gleichung auf die `.rm`-Seite."""

    def __init__(self, model: str = STUDENT_LLM, *, mistake_prob: float = 0.0, seed: int | None = None) -> None:
        self.model = model
        self.mistake_prob = mistake_prob
        self.rng = random.Random(seed)
        self.last_persona_note = "konzentriert"
        self.mistakes_made = 0

    def choose_task_from_prompt(
        self,
        user_nudge: str = "Such dir eine Mathe-Aufgabe aus, zeichne sie auf Papier",
    ) -> str:
        """Der Student bekommt nur den offenen Anstoß und denkt sich selbst per LLM eine Mathe-Aufgabe aus."""
        self.last_persona_note = f"💡 Freier Impuls: „{user_nudge}“"
        # Zufälliger Würfel-Impuls im Prompt verhindert, dass ein 7B-Modell immer dieselbe Zahl wählt
        dice_a = self.rng.randint(2, 6)
        dice_b = self.rng.randint(1, 7)
        dice_x = self.rng.randint(2, 8)
        style_hint = self.rng.choice((
            "eine Gleichung mit Klammer auf der linken Seite, z. B. Faktor mal (x + Zahl) = Ergebnis",
            "eine Gleichung mit Klammer und Minus, z. B. Faktor mal (x - Zahl) = Ergebnis",
            "eine zweistufige Gleichung ohne Klammer, z. B. Faktor*x + Zahl = Ergebnis",
        ))
        prompt = (
            "Du bist ein Schüler vor einem komplett leeren Blatt Papier.\n"
            f"Du wirst angestoßen mit: \"{user_nudge}\"\n\n"
            f"Denke dir jetzt EINE eigene lineare Algebra-Gleichung mit der Variable x aus ({style_hint}).\n"
            f"Nutze als Inspiration für deine Zahlen heute gern Werte rund um {dice_a}, {dice_b} und Lösung x={dice_x}, "
            "damit x am Ende eine glatte positive ganze Zahl wird.\n"
            "WICHTIG: Schreibe NUR die ungelöste Start-Gleichung auf (noch keinen Rechenschritt und nicht x=...).\n"
            "Gib exakt eine Zeile im Format Term = Zahl aus, ohne Worte, ohne Erklärung."
        )
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.85,
                "seed": self.rng.randint(1, 999999),
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            data = json.loads(resp.read())
        raw = (data.get("response") or "").strip()
        for line in raw.splitlines():
            clean = re.sub(r"[^0-9a-zA-Z+\-*/=().,\s]", "", line).strip()
            if "=" not in clean:
                continue
            ana = analyze_equation(clean)
            if ana.get("ok") and not ana.get("solved") and ana["solution"].denominator == 1 and ana["solution"] > 0:
                return clean
            # Falls das LLM Zahlen gewählt hat, die nicht glatt aufgehen, runde die rechte Seite auf ganzzahliges x
            if ana.get("ok") and not ana.get("solved"):
                lhs_s = clean.split("=")[0].strip()
                pl = ana["sides"][0]
                rhs_int = int(pl[0] + pl[1] * dice_x)
                fixed = f"{lhs_s} = {rhs_int}"
                if analyze_equation(fixed).get("ok"):
                    return fixed
        raise ValueError(f"Student-LLM konnte keine gültige Start-Aufgabe wählen: {raw!r}")

    def draw_initial_task_on_blank_rm(
        self,
        rm_out: str | Path,
        *,
        user_nudge: str = "Such dir eine Mathe-Aufgabe aus, zeichne sie auf Papier",
        realtime_sleep: bool = False,
        clock_s: float = 0.0,
        on_burst=None,
    ) -> dict:
        """Startet auf einem komplett leeren `.rm`-Blatt, lässt den Studenten eine Aufgabe wählen und zeichnet sie."""
        rm_out_path = Path(rm_out)
        blank_rm = rm_out_path.parent / "step_00_blank.rm"
        blank_png = rm_out_path.parent / "step_00_blank.png"
        rm_canvas.write_blank_rm_page(blank_rm)
        rm_canvas.render_page_png(blank_rm, blank_png, authors=("student", "tutor"))

        chosen_task = self.choose_task_from_prompt(user_nudge)
        act = self.write_step_on_rm(
            chosen_task,
            blank_rm,
            rm_out_path,
            turn_index=0,
            realtime_sleep=realtime_sleep,
            clock_s=clock_s,
            on_burst=on_burst,
        )
        act["user_nudge"] = user_nudge
        act["chosen_task"] = chosen_task
        act["blank_rm"] = str(blank_rm)
        act["blank_png"] = str(blank_png)
        return act

    def think_next_equation(self, student_lines_seen_by_vlm: list[str], tutor_note_seen_by_vlm: str) -> str:
        """Fragt das lokale Sprachmodell in der Rolle des Schülers nach genau der nächsten Gleichungszeile.

        Mit Wahrscheinlichkeit `self.mistake_prob` würfelt der Student eine menschliche Schusseligkeit
        (z. B. Vorzeichenfehler beim Seitenwechsel oder Rechenfehler), sofern er nicht gerade schon
        vom Tutor wegen eines Fehlers korrigiert wird.
        """
        history = "\n".join(student_lines_seen_by_vlm)
        task_line = student_lines_seen_by_vlm[0] if student_lines_seen_by_vlm else ""
        last_line = student_lines_seen_by_vlm[-1] if student_lines_seen_by_vlm else ""
        was_just_corrected = any(
            w in tutor_note_seen_by_vlm
            for w in ("Distributivgesetz", "Vorzeichenregel", "Divisionsregel", "prüfen")
        )
        roll_mistake = (
            (not was_just_corrected)
            and (self.mistakes_made == 0)
            and (self.rng.random() < self.mistake_prob)
        )

        if roll_mistake:
            self.mistakes_made += 1
            self.last_persona_note = "🎲 Zufalls-Schusseligkeit gewürfelt (macht typischen Schülerfehler)"
            behavior_instruction = (
                f"Forme die Gleichung \"{last_line}\" um, aber mache dabei absichtlich einen typischen Schülerfehler: "
                "Falls eine Klammer wie a(x+b)=c dasteht, löse die Klammer auf, aber vergiss die zweite Zahl b mit a "
                "zu multiplizieren (schreibe also a*x + b = c ohne Klammer!). "
                "Falls keine Klammer dasteht, rechne beim Seitenwechsel + statt -."
            )
        elif was_just_corrected:
            self.last_persona_note = "💡 Korrigiert seinen Fehler anhand des Tutor-Hinweises"
            behavior_instruction = (
                f"ACHTUNG: Deine letzte Zeile \"{last_line}\" war FALSCH (rot unterstrichen vom Tutor mit dem Hinweis: "
                f"\"{tutor_note_seen_by_vlm}\")! Rechne NICHT mit der falschen Zeile \"{last_line}\" weiter, "
                f"sondern gehe zurück zur Aufgabenzeile \"{task_line}\" und schreibe die korrigierte Umformung "
                "(z. B. Klammer komplett ausmultipliziert als a*x + a*b = c) richtig hin!"
            )
        else:
            self.last_persona_note = "🎯 Konzentriert (rechnet nächsten Schritt korrekt)"
            behavior_instruction = (
                f"Rechne von deiner richtigen Zeile \"{last_line}\" aus genau EINEN Schritt weiter in Richtung x = Zahl."
            )

        prompt = (
            "Du bist ein Schüler, der eine Algebra-Aufgabe Schritt für Schritt auf einem Tablet löst.\n"
            f"Start-Aufgabe oben auf dem Blatt: {task_line}\n"
            f"Alle bisherigen Zeilen auf dem Blatt:\n{history}\n\n"
            f"Zuletzt geschriebene Zeile: {last_line}\n"
            f"Hinweis des Tutors auf dem Blatt: \"{tutor_note_seen_by_vlm}\"\n\n"
            f"Anweisung für diesen Zug: {behavior_instruction}\n"
            f"WICHTIG: Wiederhole NICHT \"{last_line}\", sondern schreibe genau EINE neue Gleichungszeile (Term = Term)!\n"
            "Gib NUR die neue Gleichung aus, ohne Worte, ohne LaTeX, ohne Erklärung."
        )
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.45 if self.mistake_prob > 0 else 0.0,
                "seed": self.rng.randint(1, 999999),
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            data = json.loads(resp.read())
        raw = (data.get("response") or "").strip()
        last_norm = _normalize(last_line)
        candidates: list[str] = []
        for line in raw.splitlines():
            clean = re.sub(r"[^0-9a-zA-Z+\-*/=().,\s]", "", line).strip()
            if "=" in clean:
                candidates.append(clean)
        for cand in candidates:
            if _normalize(cand) != last_norm:
                if roll_mistake:
                    task_ana = analyze_equation(student_lines_seen_by_vlm[0]) if student_lines_seen_by_vlm else {"ok": False}
                    cand_ana = analyze_equation(cand)
                    if task_ana.get("ok") and cand_ana.get("ok") and cand_ana["solution"] == task_ana["solution"]:
                        # Das 7B-Modell hat trotz Fehler-Würfel richtig gerechnet -> zweiter gezielter Impuls ans LLM
                        retry_prompt = (
                            f"Forme \"{last_line}\" mit einem typischen Schülerfehler um: "
                            "Löse eine vorhandene Klammer a(x+b)=c fehlerhaft zu ax + b = c auf (ohne Klammer!), "
                            "oder mache beim Seitenwechsel einen Vorzeichenfehler (+ statt -).\n"
                            "Gib NUR die eine fehlerhafte Gleichung (ohne Klammer) mit = aus:"
                        )
                        r_payload = json.dumps({
                            "model": self.model,
                            "prompt": retry_prompt,
                            "stream": False,
                            "options": {"temperature": 0.7, "seed": self.rng.randint(1, 999999)},
                        }).encode("utf-8")
                        r_req = urllib.request.Request(
                            f"{OLLAMA_HOST}/api/generate",
                            data=r_payload,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(r_req, timeout=45.0) as r_resp:
                            r_data = json.loads(r_resp.read())
                        for r_line in (r_data.get("response") or "").splitlines():
                            r_clean = re.sub(r"[^0-9a-zA-Z+\-*/=().,\s]", "", r_line).strip()
                            r_ana = analyze_equation(r_clean)
                            if "=" in r_clean and r_ana.get("ok") and r_ana["solution"] != task_ana["solution"]:
                                return r_clean
                return cand
        if candidates:
            return candidates[-1]
        raise ValueError(f"Student-Modell lieferte keine gültige Gleichung: {raw!r}")

    def plan_bursts(self, next_eq: str, rm_in: str | Path, *, turn_index: int = 1) -> dict:
        """Plant die dynamische Zeilenplatzierung und teilt die Striche in zufällige Zeit-Etappen (Bursts)."""
        existing = rm_canvas.read_strokes(rm_in)
        placed = dynamic_writer.place_student_line_dynamically(
            next_eq,
            existing,
            seed=self.rng.randint(1, 10_000_000) + turn_index,
        )
        bursts = dynamic_writer.split_strokes_into_random_bursts(
            next_eq,
            placed["strokes"],
            self.rng,
        )
        return {
            "x0": placed["x0"],
            "baseline_y": placed["baseline_y"],
            "strokes": placed["strokes"],
            "bursts": bursts,
        }

    def write_step_on_rm(
        self,
        next_eq: str,
        rm_in: str | Path,
        rm_out: str | Path,
        *,
        turn_index: int = 1,
        realtime_sleep: bool = False,
        clock_s: float = 0.0,
        on_burst=None,
    ) -> dict:
        """Schreibt die neue Schüler-Gleichung zu zufälligen Zeitpunkten (in 2–3 Bursts) auf die `.rm`-Seite."""
        planned = self.plan_bursts(next_eq, rm_in, turn_index=turn_index)
        bursts = planned["bursts"]

        rm_out_path = Path(rm_out)
        prev_rm = Path(rm_in)
        cur_clock = clock_s
        burst_records: list[dict] = []
        last_append_info: dict = {}

        for b in bursts:
            wait_s = float(b["wait_s"])
            if realtime_sleep and wait_s > 0:
                time.sleep(wait_s)
            cur_clock = round(cur_clock + wait_s, 2)

            if b["is_final"]:
                target_rm = rm_out_path
                target_png = rm_out_path.with_suffix(".png")
            else:
                stem = rm_out_path.stem
                target_rm = rm_out_path.parent / f"{stem}_burst_{b['burst_index']}.rm"
                target_png = rm_out_path.parent / f"{stem}_burst_{b['burst_index']}.png"

            last_append_info = rm_canvas.append_strokes(
                prev_rm,
                b["strokes"],
                target_rm,
                layer_name=rm_canvas.STUDENT_LAYER,
            )
            rm_canvas.render_page_png(target_rm, target_png, authors=("student", "tutor"))

            rec = {
                "burst_index": b["burst_index"],
                "burst_count": b["burst_count"],
                "wait_s": wait_s,
                "timestamp_s": cur_clock,
                "burst_text": b["burst_text"],
                "cumulative_text": b["cumulative_text"],
                "is_final": b["is_final"],
                "rm_path": str(target_rm),
                "png_path": str(target_png),
                "rm_bytes": target_rm.stat().st_size,
            }
            burst_records.append(rec)
            if on_burst is not None:
                on_burst(rec)
            prev_rm = target_rm

        return {
            "student_equation_written": next_eq,
            "persona_state": self.last_persona_note,
            "x0": planned["x0"],
            "baseline_y": planned["baseline_y"],
            "bursts": burst_records,
            "clock_s": cur_clock,
            "append_info": last_append_info,
        }
