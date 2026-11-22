#!/usr/bin/env bash
set -euo pipefail

# Tesseract-Parameter (direkt hier anpassen)
TESS_LANG="deu+eng"
OEM="1"
PSM="6"

PNG="${1:-page.png}"
if [ ! -f "$PNG" ]; then
    echo "Fehler: Bilddatei nicht gefunden: $PNG" >&2
    exit 1
fi

OUT="${PNG%.png}"

echo "Installiertes Tesseract: $(tesseract --version | sed -n '1p')"
echo "Befehl: tesseract ${PNG} ${OUT} -l ${TESS_LANG} --oem ${OEM} --psm ${PSM}"
tesseract "${PNG}" "${OUT}" -l "${TESS_LANG}" --oem "${OEM}" --psm "${PSM}"

echo "--- Ergebnis (${OUT}.txt) ---"
cat "${OUT}.txt"
echo "-----------------------------"
