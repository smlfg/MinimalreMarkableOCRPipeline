"""Adapter: Produktcode ocr/formula.py mit gecachten Engines (models.py). Experimente ändern ocr/formula.py bzw. ocr/coherence.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import models as M
from ocr import formula


def recognize(path):
    return formula.recognize(path, tt=M.tt, glm=lambda img: M.ask("glm-ocr:q8_0", img))
