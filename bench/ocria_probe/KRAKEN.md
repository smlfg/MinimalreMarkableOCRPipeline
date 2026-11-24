# Kraken blla (7.2) als Zeilenfinder – Ergebnis 2026-11-24

**Urteil: verworfen.** Auf den Kalibrierblättern ist Kraken klar schwächer als `cluster_lines`. Den Korpuslauf hat der Owner abgebrochen: Bild-Modelle sind ein Umweg, weil die Striche schon als Geometrie vorliegen.

| Verfahren | Probe (40) | Ketten (60) |
|---|---:|---:|
| cluster_lines | 100 % | 100 % |
| Kraken nackt | 45 % | 45 % |
| Kraken + Reststriche zur nächsten Zeile | 80 % | 67 % |

Fehlerbild: Der Umriss ist ein enger Schlauch um die Grundlinie. Nenner, Hochzahlen und Wurzeln fallen heraus, Formelzeilen werden zerteilt. Overlays liegen in `kraken/` und `kraken_nearest/`. Den Glue gibt es nur im Scratchpad.
