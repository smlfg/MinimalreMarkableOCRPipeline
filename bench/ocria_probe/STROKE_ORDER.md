# Zeilen aus der Schreibreihenfolge – Ergebnis 2026-11-24

**Idee:** Kein OCR nötig. Die .rm-Striche liegen in Schreibreihenfolge vor. Ein Zeilenumbruch ist der Sprung des Stifts weit nach links UND nach unten.

**Daten geprüft:** Die Reihenfolge in der Datei ist die echte Schreibreihenfolge (`order/strokeorder_881240d5.png`, blau = früh, rot = spät). Spätere Nachträge erscheinen auch später.

## Kalibrierblätter (GT)
| Verfahren | Probe (40) | Ketten (60) |
|---|---:|---:|
| cluster_lines | 40 | 60 |
| Schreibreihenfolge v1 | 39 | 54 |

Fehler v1: Alle 6 zerteilten Kettenschritte sind Brüche (K20–K23). Beim Nenner springt der Stift nach links unten, genau wie bei einem Zeilenumbruch. Eine andere Schwelle für den Sprung nach unten (1,2–2,3 Strichhöhen) oder für „weit weg“ (3–6) behebt das nicht.

## Freie Seiten (265, ohne GT, Sichtprüfung)
- **Fließtext: besser als cluster_lines.** Auf `881240d5_9a5e90a6` und `881240d5_023f5ba0` sind alle Textzeilen sauber getrennt, auch dort, wo Unterlängen in die nächste Zeile ragen. Genau diese Paare hatte cluster_lines zusammengeklebt.
- **Zeichnungen und Graphen: zerfallen in viele Stücke.** Deshalb gibt es 5900 „Zeilen“ statt etwa 1400.
- Die Regel „Schwerpunkte > 2,5 Strichhöhen auseinander“ taugt nicht als Messgröße. Sie schlägt schon bei langen Unterlängen an (J, g).

## Folgerung: Kombination
Beide Verfahren haben gegenläufige Fehler:
- cluster_lines klebt dichte Textzeilen zusammen, hält aber Brüche und Zeichnungen zusammen.
- Die Schreibreihenfolge trennt dichte Textzeilen, zerreißt aber Brüche und Zeichnungen.

→ Nächster Versuch: Zuerst mit cluster_lines gruppieren. Dann wird eine Gruppe nur geteilt, wenn sie zu hoch ist (mehr als etwa 2× die mittlere Zeilenhöhe) UND die Schreibreihenfolge darin einen echten Zeilenumbruch zeigt. Für eine verlässliche Zahl auf freien Seiten braucht es GT: etwa 20 Seiten, Zeilen von Hand markiert.

Glue nur im Scratchpad (`ocria/glue/order_lines.py`, `sweep.py`), nichts im Repo-Code.
