# ADR 001 (Anhang): Stratifizierter manueller Error Audit — 30 Beispiele

**Status:** provisional, 23.11.2026 · **Teil von:** `ADR-001-ocr-messaufbau-provisional.md`

## Zweck

Der Zeilen-Recall aus M3 (Full-Page 55,0 % / Line-Mode 50,2 %) erlaubt zwei
unvereinbare Lesarten: die OCR-Engine verfehlt echte Zeilen, **oder** die
Referenz enthält Zeilen, die so nicht auf der Seite stehen. Dieser Audit
soll das quantifizieren, **ohne** vorab eine der beiden Lesarten
festzulegen.

## Stichprobe

**Stratifiziert** über drei Achsen, aus dem Pool der 99 Seiten, die sowohl
Konsens-Zeilen als auch einen Vollseiten-Render besitzen:

| Achse | Werte |
|---|---|
| Bucket | `real_math`, `real_text_dev`, `real_text_holdout` |
| Agreement der Referenz | 100 %, 90–99 %, 50–89 % |
| Zeilenlänge | kurz (≤ 12), mittel (≤ 30), lang (> 30) |

Bis zu 2 Beispiele je besetztem Stratum, **30 gesamt**. Die vier
nachträglich ergänzten Beispiele (#27–#30) wurden gezielt aus den
Klassen mit der größten Abweichung gezogen, damit der Audit nicht nur
leichte Fälle abbildet.

Seed: 20261123 (Stichprobe) / 777 (Nachtrag). Rohdaten:
`data/arena/audit_items.json`, Klassifikation: `data/arena/audit_classified.json`.

## Klassifikationskriterien

Die Klassifikation folgt **mechanischen Regeln**, nicht Bauchgefühl:

| Klasse | Kriterium |
|---|---|
| `ok` | `levenshtein(GT, LINE) == 0` (normalisiert) |
| `ocr_fehler` | Distanz ≤ 12 % der GT-Länge → Zeichenverwechslung, Struktur intakt |
| `struktur_fehler` | Engine bricht die Zeile an einer unnatürlichen Stelle um (`\n` im Output), Inhalt aber vorhanden |
| `alignment_fehler` | Distanz > 50 % der GT-Länge → GT und Output passen nicht zueinander |
| `referenz_fehler` | GT enthält nachweislich Metatexte/Annotationen, die nicht auf der Seite stehen |

## Ergebnis

| Klasse | Anzahl | Anteil |
|---|---:|---:|
| `ocr_fehler` | 17 | 57 % |
| `ok` | 8 | 27 % |
| `alignment_fehler` | 4 | 13 % |
| `struktur_fehler` | 1 | 3 % |
| `referenz_fehler` | 0 | 0 % |

### Was das für die offene Frage Q1 heißt

**In dieser Stichprobe ist kein einziges Beispiel als `referenz_fehler`
klassifiziert worden.** Die 4 `alignment_fehler` sind jedoch **nicht
als Referenzfehler gewertet**, sondern als Fälle, in denen GT und Output
nicht zusammenpassen — die Richtung (falsche Referenz vs. falsche
Erkennung) ist aus dem Text allein nicht entscheidbar. Beispiele:

```
GT   : 'j=1'          LINE: 'V=P'          FULL: 'J=1'      (d_line=2, d_full=0)
GT   : 'knowledge start'  LINE: 'o uno wiod stand'  FULL: 'O knowledg stande'
GT   : '0 1 2 3 4 5'  LINE: 'S'            FULL: '0 12'     (d_line=6)
GT   : 'tun doch period wol aus sin/cos gebildet'  LINE: 'Can date period'
```

Bei #2 ist die Full-Page-Ausgabe **exakt** (`'J=1'` vs. GT `'j=1'`, nur
Groß-/Klein), die Line-Ausgabe ist `'V=P'` — der Fehler liegt also im
**Modus**, nicht zwingend in der Referenz. Bei #4 und #30 sind beide
Modi fehlerhaft.

**Befund, nicht Interpretation:** In 4 von 30 Fällen passen GT und Output
nicht zusammen; in 26 von 30 liegt der Output strukturell nah an der GT.
Das ist mit der Annahme vereinbar, dass die Referenz überwiegend trägt —
**bewiesen ist es damit nicht.** Die Richtung der 4 Fälle ist mit
Textanalyse nicht auflösbar; das erfordert den Vergleich mit dem
**Seitenbild** (visuell), was als nächstes Skript des Audits geplant ist.

### Fehlerbilder im Detail

**Zeichenverwechslungen (17 Fälle)** dominieren. Typische Klassen:

| Muster | Beispiel |
|---|---|
| `·` → `:` | GT `'215·6 = 12+3 = 15'` → `'215:6 = 12+3 = 15'` |
| `·` → `-` | GT `'17·3=3·10+3·7=30+21'` → `'17:3=3-10+37-30+21'` |
| `l` → `1` / `I` | GT `'UKW MHZ'` → `'UW MHE'` |
| `n` → `u` / `m` | GT `'Begroffe Nontext'` → `'Begröffe Houlext'` |
| `c` → `e` | GT `'knowledge start'` → `'O knowledg stande'` |
| `·` → `,` | GT `'1,5 .'` → `'1,5 '` |

**Strukturfehler (1 Fall, plus several in `ocr_fehler` enthalten):**
Die Engine bricht auch **innerhalb** eines Zeilen-Crops um:

```
GT   : '48 x 25% Kettenrechnung prüfen: Zwischenschritt stimmt nicht'
LINE : '48x<≤%\nKettenrechnung prüfen:\nZwischenschritt stimmt nicht'
```

Das ist bemerkenswert: der Crop ist **eine** Zeile, die Engine liefert
**drei**. Das ist keine Seitenstruktur, sondern ein **Zeilen-Segmentierungs-
fehler der Engine** — und er ist unabhängig vom Full/Line-Modus.

**Zeilenweise vs. volle Seite:** In 6 von 30 Fällen ist die Full-Page-
Ausgabe näher an der GT als die Line-Ausgabe, in 4 Fällen umgekehrt.
Der Modus allein ist damit **nicht** der erklärende Faktor.

## Was dieser Audit noch **nicht** beantwortet

1. **Die Richtung der 4 `alignment_fehler`** ist ungeklärt (GT falsch vs.
   Erkennung falsch). Erfordert visuellen Vergleich mit dem Seitenbild.
2. **`referenz_fehler` als Klasse hat 0 Treffer** — aber die Klasse wurde
   nur über Textmarker (`nicht eindeutig`, `erkannt ?`, `->`) erkannt.
   Ein Referenzfehler, der wie ein normaler Handschrifttext aussieht,
   ist mit dieser Methode **nicht** auffindbar. Beispiel #6 zeigt das
   Grenzfall-Risiko: die GT enthält den Metatext
   `'2x + 6 = 16 Ausdruck nicht eindeutig erkannt'` — ob dieser Text
   wirklich auf der Seite steht, ist ungeprüft.
3. **Keine Aussage zur mathematischen Struktur.** Alle Klassen sind
   zeichenbasiert. Ob `'17·3=3·10+3·7'` mathematisch korrekt wiedergegeben
   ist, wird nicht geprüft (→ Q2).
4. **Stichprobengröße 30** — nach Bucket: 12 `real_math`, 11 `real_text_dev`,
   7 `real_text_holdout`. Für Anteilsschätzungen ist das zu wenig;
   die Zahlen sind **illustrativ**, nicht inferenzstatistisch.

## Konsequenz

- Die Annahme „die Referenz sei überwiegend intakt" ist **durch diesen Audit
  nicht widerlegt** — aber auch **nicht bewiesen**.
- Der nächste Schritt ist die visuelle Gegenprüfung der 4
  `alignment_fehler` **plus** der mathetischen Fälle am Seitenbild, um Q1
  abschließend zu beantworten.
- Q2 (Metriken für mathematische Struktur) bleibt unabhängig davon offen
  und ist in `ADR-002-metriken.md` zu bearbeiten.
