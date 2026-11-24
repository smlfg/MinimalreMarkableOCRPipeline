"""Live-Runner: chain_bench mit echten Engines (TexTeller-Worker + GLM via Ollama), kein Cache-Zwang."""
import sys, types
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root)); sys.path.insert(0, str(root / "bench"))
from ocr import formula
tt = formula.TexTeller()
def recognize(path):
    return formula.recognize(path, tt=tt)
m = types.ModuleType("pipeline"); m.recognize = recognize
sys.modules["pipeline"] = m
import chain_bench
chain_bench.main()
