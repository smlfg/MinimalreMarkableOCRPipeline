import argparse
import json
import sys
import time


def extract_rapidocr_text(result) -> str:
    if not result:
        return ""
    items = []
    for box, text, _ in result:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append((sum(ys) / 4.0, min(xs), max(ys) - min(ys), str(text)))
    items.sort(key=lambda x: x[0])
    rows = []
    for yc, xmin, h, txt in items:
        if rows and abs(yc - rows[-1][0]) <= 0.6 * max(rows[-1][1], h, 10.0):
            rows[-1][2].append((xmin, txt))
        else:
            rows.append([yc, h, [(xmin, txt)]])
    return "\n".join(" ".join(t for _, t in sorted(r[2])) for r in rows).strip()


def load_engine(name: str):
    if name == "rapidocr":
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        return lambda path: extract_rapidocr_text(engine(path)[0])
    from rapid_latex_ocr import LaTeXOCR
    engine = LaTeXOCR()
    return lambda path: (engine(path)[0] or "").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["rapidocr", "rapid_latex"], default="rapidocr")
    args = ap.parse_args()
    infer = load_engine(args.engine)
    while raw := sys.stdin.readline():
        path = raw.rstrip("\r\n")
        if not path:
            continue
        t0 = time.perf_counter()
        try:
            text = infer(path)
            ms = round((time.perf_counter() - t0) * 1000.0, 1)
            out = {"path": path, "text": text, "ms": ms}
        except Exception as exc:
            out = {"path": path, "text": "", "ms": 0.0, "error": str(exc)}
        print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
