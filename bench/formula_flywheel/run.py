"""Ein Experiment: pipeline auf dev bewerten, Zeile an results.tsv. Aufruf: python run.py "<beschreibung>" [split]"""
import importlib, json, subprocess, sys
from pathlib import Path
import prepare, pipeline
HERE = Path(__file__).resolve().parent
desc = sys.argv[1] if len(sys.argv) > 1 else "-"; split = sys.argv[2] if len(sys.argv) > 2 else "dev"
m = prepare.evaluate(pipeline.recognize, split, log=HERE / f"last_{split}.jsonl")
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip() or "-"
tsv = HERE / "results.tsv"
if not tsv.exists(): tsv.write_text("commit\tsplit\tstruct\tchar\tp95_s\tcoverage\tprec_certain\tstruct_mw\tstruct_crohme\tdescription\n")
line = f"{commit}\t{split}\t{m['struct']:.4f}\t{m['char']:.4f}\t{m['p95']:.2f}\t{m['coverage']:.3f}\t{m['prec_certain']:.4f}\t{m.get('struct_mw',0):.3f}\t{m.get('struct_crohme',0):.3f}\t{desc}\n"
with open(tsv, "a") as f: f.write(line)
print(json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}))
