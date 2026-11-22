#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Verwendung: $0 <DOC_UUID> <PAGE_UUID> [OUT_BASIS]" >&2
    exit 1
fi

DOC_UUID="$1"
PAGE_UUID="$2"
OUT="${3:-page}"

REMOTE_PATH="/home/root/.local/share/remarkable/xochitl/${DOC_UUID}/${PAGE_UUID}.rm"

echo "[1/3] Hole .rm per USB (scp)..."
scp -o BatchMode=yes -o ConnectTimeout=5 "remarkable-usb:${REMOTE_PATH}" "${OUT}.rm"

echo "[2/3] Konvertiere .rm -> .svg (rmc)..."
rmc -t svg "${OUT}.rm" -o "${OUT}.svg"

echo "[3/3] Rasterisiere .svg -> .png mit weißem Hintergrund (rsvg-convert)..."
rsvg-convert -b white "${OUT}.svg" -o "${OUT}.png"

echo "Fertig: ${OUT}.png"
