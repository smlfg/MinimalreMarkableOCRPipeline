# UPSTREAM_SEARCH – Zeilendetektor für Handschriftseiten

Bedarf: Auf einer reMarkable-Seite Textzeilen und Formelzeilen finden. Das ist die Lücke „Seitenstruktur ist nicht gemessen“.

| # | Kandidat | Repo | Zweck | Andockpunkt | Status |
|---|---|---|---|---|---|
| 1 | OCRia-nano-1 det.onnx | github.com/run-llama/liteparse + huggingface.co/llamaindex/OCRia-nano-1 | Zeilendetektor, 0,08M, ONNX, CPU | PNG rein, Boxen raus (ONNX Runtime) | in dieser Probe getestet |
| 2 | Kraken (blla-Segmentierung) | github.com/mittagessen/kraken | Baseline-Segmentierung für Handschrift (HTR) | CLI `kraken -i page.png out segment -bl` → JSON | Kandidat, nicht getestet |
| 3 | Surya Detection | github.com/datalab-to/surya | Zeilendetektion, viele Sprachen | Python-API, PNG rein, Polygone raus | Kandidat, nicht getestet |
| 4 | Strich-Geometrie (.rm) | eigener Glue (rmscene) | Zeilen aus y-Clustern der Striche | Striche aus tablet/ | Fallback, kein ML |

Entscheidung: Zuerst messen wir nur Kandidat 1, weil der Nutzer danach gefragt hat. Ein Einbau folgt erst nach einem Vergleich mit Kandidat 2 und 3.
