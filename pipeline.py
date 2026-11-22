#!/usr/bin/env python3
"""Terminal-Steuerung: reMarkable (USB) -> PNG."""

import json
from pathlib import Path
import subprocess
import sys

PIPELINE_VERSION = "0.1.0"
SSH_HOST = "remarkable-usb"
XOCHITL_DIR = "/home/root/.local/share/remarkable/xochitl"
RUNONCE = Path(__file__).resolve().parent / "runonce.sh"

print(f"MinimalreMarkableOCRPipeline v{PIPELINE_VERSION}")

while True:
    # 1. USB-Kabel prüfen
    usb_check = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", SSH_HOST, "echo ok"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    if usb_check.returncode != 0 or "ok" not in usb_check.stdout:
        print("\nreMarkable ist über USB nicht erreichbar. Bitte USB-Kabel einstecken.")
        print(f"  Exit-Code: {usb_check.returncode}")
        if usb_check.stderr.strip():
            print(f"  stderr:    {usb_check.stderr.strip()}")
        sys.exit(1)

    # 2. Notizbücher vom Gerät lesen (Metadaten + Seitenliste per NUL getrennt)
    remote_list_cmd = (
        f'for f in {XOCHITL_DIR}/*.metadata; do '
        'printf "%s\\0" "$f"; cat "$f"; printf "\\0"; '
        'cat "${f%.metadata}.content" 2>/dev/null; printf "\\0"; '
        "done"
    )
    meta_proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, remote_list_cmd],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if meta_proc.returncode != 0 and not meta_proc.stdout:
        print("\nFehler beim Lesen der Notizbücher vom Gerät.")
        print(f"  Exit-Code: {meta_proc.returncode}")
        if meta_proc.stderr.strip():
            print(f"  stderr:    {meta_proc.stderr.strip()}")
        sys.exit(1)

    fields = meta_proc.stdout.split("\0")
    books = []
    for i in range(0, len(fields) - 2, 3):
        meta_path, meta_raw, content_raw = fields[i], fields[i + 1], fields[i + 2]
        doc_uuid = Path(meta_path).stem
        try:
            meta = json.loads(meta_raw)
            content = json.loads(content_raw)
        except ValueError:
            continue
        if not isinstance(meta, dict) or not isinstance(content, dict):
            continue
        if (
            meta.get("type") != "DocumentType"
            or meta.get("deleted")
            or meta.get("parent") == "trash"
            or content.get("fileType") != "notebook"
        ):
            continue

        if "cPages" in content:
            raw_pages = (content.get("cPages") or {}).get("pages") or []
            page_ids = [
                p["id"]
                for p in raw_pages
                if isinstance(p, dict)
                and p.get("id")
                and (p.get("idx") or {}).get("value")
                and not (p.get("deleted") or {}).get("value")
            ]
        else:
            page_ids = [p for p in (content.get("pages") or []) if isinstance(p, str)]

        try:
            last_modified = int(meta.get("lastModified") or 0)
        except (TypeError, ValueError):
            last_modified = 0

        books.append(
            {
                "uuid": doc_uuid,
                "name": meta.get("visibleName") or doc_uuid,
                "last_modified": last_modified,
                "pages": page_ids,
            }
        )

    books.sort(key=lambda b: b["last_modified"], reverse=True)
    top_books = books[:3]

    if not top_books:
        print("\nKeine aktiven Notizbücher auf dem reMarkable gefunden.")
        sys.exit(1)

    # 3. Benutzer wählt ein Notizbuch
    print("\nZuletzt geänderte Notizbücher (Top 3):")
    for idx, book in enumerate(top_books, start=1):
        print(f"  {idx}. {book['name']} ({len(book['pages'])} Seiten, UUID {book['uuid'][:8]}...)")

    try:
        nb_choice = input(f"Notebook wählen [1-{len(top_books)}, q zum Beenden]: ").strip()
    except EOFError:
        break
    if nb_choice.lower() == "q":
        break
    if not nb_choice.isdigit() or not (1 <= int(nb_choice) <= len(top_books)):
        print(f"Ungültige Auswahl: {nb_choice!r}")
        continue

    selected_book = top_books[int(nb_choice) - 1]
    doc_uuid = selected_book["uuid"]
    page_ids = selected_book["pages"]
    if not page_ids:
        print(f"Das Notizbuch '{selected_book['name']}' hat keine aktiven Seiten.")
        continue

    # 4. Seiten des gewählten Notizbuchs + reale .rm-Dateigrößen abfragen
    stat_cmd = f"stat -c '%s %n' {XOCHITL_DIR}/{doc_uuid}/*.rm 2>/dev/null || true"
    stat_proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, stat_cmd],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    rm_sizes = {}
    for line in stat_proc.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            rm_sizes[Path(parts[1].strip()).stem] = int(parts[0])

    print(f"\nSeiten in '{selected_book['name']}':")
    for idx, pid in enumerate(page_ids, start=1):
        if pid in rm_sizes:
            print(f"  {idx}. {pid[:8]}... ({rm_sizes[pid]} Bytes)")
        else:
            print(f"  {idx}. {pid[:8]}... [leer / keine .rm-Datei]")

    # 5. Benutzer wählt eine Seite
    try:
        page_choice = input(f"Seite wählen [1-{len(page_ids)}]: ").strip()
    except EOFError:
        break
    if not page_choice.isdigit() or not (1 <= int(page_choice) <= len(page_ids)):
        print(f"Ungültige Seitenauswahl: {page_choice!r}")
        continue

    page_uuid = page_ids[int(page_choice) - 1]
    if page_uuid not in rm_sizes:
        print(
            f"Seite {page_choice} ({page_uuid[:8]}...) hat keine .rm-Datei auf dem Gerät "
            "(leere oder noch nicht beschriebene Seite)."
        )
        continue

    # 6. runonce.sh für USB -> PNG ausführen
    print(f"\nHole Seite {page_choice} ({page_uuid}) aus '{selected_book['name']}' -> page.png\n")
    run_proc = subprocess.run(
        [str(RUNONCE), doc_uuid, page_uuid, "page"],
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if run_proc.returncode != 0:
        print(f"\nrunonce.sh fehlgeschlagen (Exit-Code {run_proc.returncode}).")
    else:
        print("\npage.png ist bereit. Weiter mit: ./ocr.sh page.png")

    # 7. Weitere Seite holen?
    try:
        again = input("\nNoch eine Seite holen? [j/N]: ").strip()
    except EOFError:
        break
    if again.lower() not in ("j", "y"):
        break
