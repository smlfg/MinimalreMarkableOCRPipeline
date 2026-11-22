#!/usr/bin/env python3
"""Sync all non-empty active notebook .rm pages from USB reMarkable -> data/real_corpus/."""

import json, subprocess, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SSH_HOST = "remarkable-usb"
XOCHITL_DIR = "/home/root/.local/share/remarkable/xochitl"
OUT_DIR = BASE_DIR / "data" / "real_corpus"
MIN_BYTES = 5000


def main() -> int:
    meta_cmd = (
        f'for f in {XOCHITL_DIR}/*.metadata; do '
        'printf "%s\\0" "$f"; cat "$f"; printf "\\0"; '
        'cat "${f%.metadata}.content" 2>/dev/null; printf "\\0"; done'
    )
    mp = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", SSH_HOST, meta_cmd],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", check=False,
    )
    if mp.returncode != 0 and not mp.stdout:
        print(f"Fehler: reMarkable nicht erreichbar ({mp.stderr.strip()})", file=sys.stderr)
        return 1

    books = {}
    fields = mp.stdout.split("\0")
    for i in range(0, len(fields) - 2, 3):
        doc_uuid = Path(fields[i]).stem
        try:
            meta, content = json.loads(fields[i + 1]), json.loads(fields[i + 2])
        except ValueError:
            continue
        if (
            isinstance(meta, dict) and isinstance(content, dict)
            and meta.get("type") == "DocumentType"
            and not meta.get("deleted")
            and meta.get("parent") != "trash"
            and content.get("fileType") == "notebook"
        ):
            books[doc_uuid] = (meta.get("visibleName") or doc_uuid).replace("\t", " ").replace("\n", " ")

    sp = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, f"stat -c '%s %n' {XOCHITL_DIR}/*/*.rm 2>/dev/null || true"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False,
    )

    rows, to_fetch = [], []
    rm_root = OUT_DIR / "rm"
    rm_root.mkdir(parents=True, exist_ok=True)
    for line in sp.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        sz, full = int(parts[0]), parts[1].strip()
        p = Path(full)
        doc_uuid, page_uuid = p.parent.name, p.stem
        if doc_uuid not in books or sz < MIN_BYTES:
            continue
        rel = f"{doc_uuid}/{page_uuid}.rm"
        rows.append((f"{doc_uuid[:8]}_{page_uuid[:8]}", books[doc_uuid], doc_uuid, page_uuid, sz, rel))
        local = rm_root / rel
        if not local.is_file() or local.stat().st_size != sz:
            to_fetch.append(rel)

    rows.sort(key=lambda r: (r[1].casefold(), r[2], r[3]))
    if to_fetch:
        print(f"Lade {len(to_fetch)} .rm-Seiten per USB-tar...")
        tar_proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, f"tar -C {XOCHITL_DIR} -cf - -T -"],
            input=("\n".join(to_fetch) + "\n").encode("utf-8"),
            capture_output=True, check=True,
        )
        subprocess.run(["tar", "-xf", "-", "-C", str(rm_root)], input=tar_proc.stdout, check=True)

    manifest = OUT_DIR / "manifest.tsv"
    manifest.write_text(
        "id\tnotebook\tdoc_uuid\tpage_uuid\trm_bytes\trel_path\n"
        + "".join(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}\n" for r in rows),
        encoding="utf-8",
    )
    total_mb = sum(r[4] for r in rows) / (1024 * 1024)
    n_books = len({r[2] for r in rows})
    print(f"Sync fertig: {len(rows)} Seiten aus {n_books} Notizbüchern ({total_mb:.1f} MB) -> {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
