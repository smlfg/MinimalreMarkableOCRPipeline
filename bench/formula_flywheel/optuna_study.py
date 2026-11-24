"""Optuna-Study ueber die CONFUSE-Schalter der Kohaerenz-Schicht (ocr/coherence.py).

Suche: auf `train` (Score = struct). Kontrolle: `dev`, nur einmal fuer den Gewinner und die Baseline.
`test` wird nicht angefasst. Speicherung: SQLite fuer das optuna-dashboard.

Aufruf (aus diesem Ordner):
  ../../.venv_optuna/bin/python optuna_study.py 40            # 40 Versuche, Suche auf train
  ../../.venv_optuna/bin/python optuna_study.py 5 --limit 20  # Schnelltest auf 20 Zeilen
Dashboard:
  ../../.venv_optuna/bin/optuna-dashboard "sqlite:///<absoluter Pfad>/optuna.db"
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import optuna  # noqa: E402
import prepare  # noqa: E402
import pipeline  # noqa: E402
from ocr import coherence as C  # noqa: E402

STUDY = "confuse_switches"
DB = HERE.parents[1] / ".venv_optuna" / "flywheel_study.db"


def run_split(split: str, off: set[int], limit=None) -> dict:
    C.DISABLED = set(off)
    try:
        return prepare.evaluate(pipeline.recognize, split, limit=limit)
    finally:
        C.DISABLED = set()


def pair_label(i: int) -> str:
    pat, rep = C.CONFUSE[i]
    return f"{pat!r} -> {rep!r}"


def make_objective(limit):
    def objective(trial):
        off = {i for i in range(len(C.CONFUSE))
               if trial.suggest_categorical(f"off_{i}", [False, True])}
        m = run_split("train", off, limit)
        trial.set_user_attr("off_pairs", [pair_label(i) for i in sorted(off)])
        trial.set_user_attr("train_char", m["char"])
        return m["struct"]
    return objective


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n_trials", type=int, nargs="?", default=40)
    ap.add_argument("--limit", type=int, default=None, help="nur die ersten N Zeilen (Schnelltest)")
    a = ap.parse_args()

    study = optuna.create_study(
        study_name=STUDY, storage=f"sqlite:///{DB}", direction="maximize", load_if_exists=True)
    if not study.trials:
        study.enqueue_trial({f"off_{i}": False for i in range(len(C.CONFUSE))})  # Baseline = alle an
    study.optimize(make_objective(a.limit), n_trials=a.n_trials)

    best = study.best_trial
    best_off = {i for i in range(len(C.CONFUSE)) if best.params.get(f"off_{i}")}
    base = run_split("dev", set(), a.limit)
    win = run_split("dev", best_off, a.limit)
    print(f"Study: {STUDY}  Versuche: {len(study.trials)}  Speicher: {DB}")
    print(f"Bester Train-Struct: {best.value:.4f}  aus Schaltern: {[pair_label(i) for i in sorted(best_off)]}")
    print(f"dev struct  Baseline: {base['struct']:.4f}   Gewinner: {win['struct']:.4f}")
    print(f"dev char    Baseline: {base['char']:.4f}   Gewinner: {win['char']:.4f}")


if __name__ == "__main__":
    main()
