# ADR 007: Kohärenz-Schicht und Unsicherheit – nie still korrigieren

**Status:** angenommen, 23.11.2026 · **Baut auf:** ADR-005 (Feld `uncertain`, `checks.cause`) · **Code:** `ocr/coherence.py` (`coherent`, `closed_truth`, `decimal_comma`)

## Kontext

Die Restfehler sind Zeichenverwechslungen (a/0, z/2, ·/./÷, l/1, 9/g). Viele lassen sich über die Mathematik entscheiden: `17.3 = 51` ist falsch, `17·3 = 51` stimmt. Gleichzeitig enthalten echte Rechnungen **Rechenfehler des Lernenden** (`9/9 + 9/4 = 18/13` auf einer eigenen Seite; Trugschluss `√1·√1 = √−1·√−1` in MathWriting). Eine Korrektur, die Unstimmiges glättet, versteckt genau das, was der Tutor finden soll.

Kontext-Check auf echten Rechenketten (23.11.) ergab die Entscheidungsregel:

| Modelle | Kette / Rechnung | Bedeutung |
|---|---|---|
| uneinig | genau eine Lesart stimmt | OCR-Fehler → diese Lesart, markiert als repariert |
| einig | stimmt nicht | **Rechenfehler des Lernenden** → melden, nicht korrigieren |
| – | nichts stimmt | `uncertain` |

## Entscheidung

1. **Verwechslungspaare werden nur getauscht, wenn eine variablenfreie Gleichungskette dadurch wahr wird**, oder (Ziffer → Buchstabe) wenn die Zweitmeinung (GLM) genau diese Lesart unabhängig liefert.
2. **Jede Reparatur hinterlässt eine Spur** (`repair: "<vorher> -> <nachher>"`) und macht die Zeile `uncertain`.
3. **Eine falsche Zahlengleichung ist immer `uncertain`**: Sie kann OCR- oder Rechenfehler sein; das entscheidet der Mensch bzw. der Validator mit Kontext.
4. **Deutsches Dezimalkomma** `0,5` → `0.5`, aber nicht innerhalb von `{…}`, `(…)`, `[…]` (dort Trennzeichen, z. B. `{1,3}`).
5. Fehlender Malpunkt zwischen Ziffern (`3 10`) ist ein Verwechslungspaar wie die anderen (nur wenn die Kette dadurch stimmt).

## Nachtrag (Issue #1): `uncertain` vs. `math_status`

Punkt 3 oben gilt für die **Validierungs-/Tutor-Logik** weiter; für das OCR-Feld **`uncertain`** gilt:

- Eine falsche, aber von beiden Engines **übereinstimmend** gelesene Gleichung ist **`uncertain=False`**, mit **`math_status=False`** (Lernender-Rechenfehler, kein OCR-Zweifel).
- **Reparaturen** (`repair` gesetzt) bleiben **immer `uncertain=True`** (ADR-007 Punkt 2).
- `closed_truth` steht konsumentenseitig als **`math_status`** zur Verfügung, nicht als OCR-Konfidenz.

## Folgen

- Synthetische Zeilen: Präzision der „sicheren“ Zeilen 100 % bei 73 % Abdeckung; dev unverändert (kein Rückschritt).
- Die Paarliste ist heute von Hand; sie soll aus der Verwechslungsmatrix der Kalibrierungsblätter **gelernt** werden (persönlich, z. B. `l` ohne Haken ≠ `1`).
- Rechenkette über mehrere Zeilen (Lösungsmengen-Vergleich) ist belegt, aber noch nicht in der Pipeline; sie braucht vollständige Zeilensegmentierung.
