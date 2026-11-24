"""Unabhängiger Adapter + Runner für ein Modell aus MODEL_REGISTRY.json. Ändert keine Produktionsdatei.

  python mb_run.py --model uni_qwen3vl_2b --split own_probe [--limit 5] [--tag smoke]
Schreibt raw/<model>/<tag-or-split>.jsonl (roh, vor jeder Bereinigung) + raw/<model>/<name>.meta.json.
Resumierbar: bereits vorhandene ids werden übersprungen. Fehlschläge werden als Zeile mit "error" bewahrt.
Kein CPU-Fallback: ohne MPS Abbruch."""
import argparse, json, os, resource, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parent / "formula_flywheel"
REG = json.load(open(HERE / "MODEL_REGISTRY.json"))["models"]
HF_HOME = HERE / "hf_cache"           # eigener Cache, nach dem Lauf löschbar (Platte knapp)
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ["TOKENIZERS_PARALLELISM"] = "false"
MAXTOK = 256


def load_rows(split):
    return [json.loads(l) for l in open(FW / "data" / f"{split}.jsonl")]


def peak_rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss      # macOS: Bytes
    return r / 1e6


def mps_mb():
    import torch
    try: return torch.mps.driver_allocated_memory() / 1e6
    except Exception: return -1.0


def fetch(cfg):
    from huggingface_hub import snapshot_download
    return snapshot_download(cfg["repo"], revision=cfg["revision"], allow_patterns=cfg["allow"], cache_dir=HF_HOME / cfg["key"])   # eigener Cache je Modell (parallele Vorab-Downloads)


class QwenVL:
    def __init__(self, cfg, path):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.torch, self.cfg = torch, cfg
        self.proc = AutoProcessor.from_pretrained(path)
        if cfg["key"].startswith("uni_"):
            try: self.proc.image_processor.max_pixels = 262144      # Trainings-Auflösung laut Model Card
            except Exception: pass
        self.model = AutoModelForImageTextToText.from_pretrained(path, dtype=getattr(torch, cfg["dtype"])).to("mps").eval()
        tk = self.proc.tokenizer   # Stop bei <|im_end|>/<|endoftext|>: Finetunes liefern sonst "assistant<think>"-Schleifen (Versuch 1)
        flat = [tk.convert_tokens_to_ids(t) for t in ("<|im_end|>", "<|endoftext|>")]
        e = self.model.generation_config.eos_token_id
        flat += e if isinstance(e, list) else [e]
        self.eos = sorted({i for i in flat if isinstance(i, int) and i >= 0})

    def __call__(self, img):
        torch = self.torch
        msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": self.cfg["prompt"]}]}]
        try: text = self.proc.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False)
        except TypeError: text = self.proc.apply_chat_template(msgs, add_generation_prompt=True)
        inp = self.proc(text=[text], images=[img], return_tensors="pt").to("mps")
        with torch.no_grad():
            out = self.model.generate(**inp, max_new_tokens=MAXTOK, do_sample=False, eos_token_id=self.eos)
        torch.mps.synchronize()
        return self.proc.batch_decode(out[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0]


class VED:
    """VisionEncoderDecoder (nougat-latex, MixTeX): HF-Image-Processor + Tokenizer, Greedy."""
    def __init__(self, cfg, path):
        import torch
        from transformers import AutoImageProcessor, AutoTokenizer, VisionEncoderDecoderModel
        self.torch, self.cfg = torch, cfg
        self.ip = AutoImageProcessor.from_pretrained(path); self.tok = AutoTokenizer.from_pretrained(path)
        self.model = VisionEncoderDecoderModel.from_pretrained(path, dtype=getattr(torch, cfg["dtype"])).to("mps").eval()

    def __call__(self, img):
        torch = self.torch
        pv = self.ip(img, return_tensors="pt").pixel_values.to("mps")
        kw = {}
        if self.cfg["family"] == "ved_nougat":
            bos = self.tok(self.tok.bos_token, add_special_tokens=False, return_tensors="pt").input_ids.to("mps")
            kw = dict(decoder_input_ids=bos, bad_words_ids=[[self.tok.unk_token_id]])
        with torch.no_grad():
            out = self.model.generate(pv, max_new_tokens=MAXTOK, num_beams=1, do_sample=False, pad_token_id=self.tok.pad_token_id, eos_token_id=self.tok.eos_token_id, **kw)
        torch.mps.synchronize()
        return self.tok.batch_decode(out, skip_special_tokens=True)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--split", required=True, help="ein Split oder Komma-Liste (Modell wird nur einmal geladen)")
    ap.add_argument("--limit", type=int); ap.add_argument("--tag")
    a = ap.parse_args()
    cfg = next(m for m in REG if m["key"] == a.model)
    if cfg["family"] == "custom_blocked": sys.exit(f"{a.model}: BLOCKED (Fremdcode nicht verfügbar) - siehe Registry")
    import torch
    from PIL import Image
    if not torch.backends.mps.is_available(): sys.exit("MPS nicht verfügbar - kein CPU-Fallback, Abbruch")
    from PIL import Image
    splits = a.split.split(",")
    todo_by = {}
    for sp in splits:
        name = a.tag or sp; rawf = HERE / "raw" / a.model / f"{name}.jsonl"
        done = {json.loads(l)["id"] for l in open(rawf)} if rawf.exists() else set()
        todo = [r for r in load_rows(sp)[:a.limit] if r["id"] not in done]
        if todo: todo_by[sp] = (name, todo)
    if not todo_by: print("nichts zu tun"); return
    t0 = time.perf_counter(); path = fetch(cfg); t_fetch = time.perf_counter() - t0
    t0 = time.perf_counter(); runner = (QwenVL if cfg["family"] == "qwen_vl" else VED)(cfg, path); torch.mps.synchronize()
    t_load = time.perf_counter() - t0
    dev = str(next(runner.model.parameters()).device)
    assert dev.startswith("mps"), f"Modell nicht auf MPS: {dev}"
    wdisk = sum(p.stat().st_size for p in Path(path).resolve().rglob("*") if p.is_file()) / 1e6
    first = True
    for sp, (name, todo) in todo_by.items():
        outdir = HERE / "raw" / a.model; outdir.mkdir(parents=True, exist_ok=True)
        rawf, metaf = outdir / f"{name}.jsonl", outdir / f"{name}.meta.json"; cold = None
        with open(rawf, "a") as f:
            for i, r in enumerate(todo):
                img = Image.open(FW / r["png"]).convert("RGB")
                t0 = time.perf_counter(); err = None
                try: raw = runner(img)
                except Exception as e: raw, err = "", f"{type(e).__name__}: {e}"
                dt = time.perf_counter() - t0
                if i == 0: cold = dt
                f.write(json.dumps({"id": r["id"], "src": r["src"], "raw": raw, "s": dt, "error": err}, ensure_ascii=False) + "\n"); f.flush()
        meta = {"model": a.model, "repo": cfg["repo"], "revision": cfg["revision"], "split": sp, "n_new": len(todo),
                "fetch_s": t_fetch, "load_s": t_load, "first_inference_s": cold, "device": dev, "load_shared_across_splits": len(todo_by) > 1,
                "peak_rss_mb": peak_rss_mb(), "mps_driver_mb": mps_mb(), "torch": torch.__version__, "weights_disk_mb": wdisk}
        metaf.write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))


if __name__ == "__main__":
    main()
