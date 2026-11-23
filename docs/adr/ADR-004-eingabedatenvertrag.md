# ADR 004: Verbindlicher Eingabedatenvertrag der OCR-Schicht

**Status:** provisional, 23.11.2026 · **Beantwortet:** offene Frage Q4 aus `ADR-001-ocr-messaufbau-provisional.md`

## Kontext

Die OCR-Pipeline (`MinimalreMarkableOCRPipeline`) und der Algebra-Tutor
(`algebra-agent`) sind getrennte Komponenten. Damit der Tutor eine
Rechnung **prüfen** kann, muss die OCR-Schicht Text in einer Form liefern,
die der SymPy-Validator fehlerfrei verarbeiten kann.

Dieses ADR leitet den Vertrag **aus dem Validator ab** — nicht aus einer
Wunschvorstellung, welche Notation "schön" wäre. Grundlage sind zwei
Validator-Implementierungen:

| Validator | Datei | Zweck |
|---|---|---|
| `SymPyChecker` | `urgent-Math-help/src/math_help/checker.py` | symbolische Prüfung (Gleichungen mit Unbekannten) |
| `arithmetic` | `algebra-agent/src/algebra_agent/arithmetic.py` | exakte Prüfung numerischer Rechenwege (produktiv) |

## Befund 1: Der produktive Validator ist `arithmetic`, nicht SymPy

`algebra_agent/arithmetic.py` hat **zwei** Mechanismen:

### Normalisierung (`_SUP`)

```python
_SUP = str.maketrans({'²':'^2','³':'^3','−':'-','×':'*','·':'*','÷':'/'})
```

| Eingabe | normalisiert |
|---|---|
| `²` (U+00B2) | `^2` |
| `³` (U+00B3) | `^3` |
| `−` (U+2212 minus) | `-` (ASCII) |
| `×` (U+00D7) | `*` |
| `·` (U+00B7 middle dot) | `*` |
| `÷` (U+00F7) | `/` |

Danach wird `^` → `**` ersetzt und mit `ast.parse(mode='eval')` geparst.

### Whitelist (`numeric_equations`)

```python
re.fullmatch(r'[\d\s.()+*/^=−×·÷²³-]+', s)
```

**Erlaubte Zeichen:** Ziffern, Whitespace, `.` `(` `)` `+` `*` `/` `^`
`=` `−` `×` `·` `÷` `²` `³` `-`

**Verboten:** Buchstaben (`x`, `y`, `a`), Komma, Doppelpunkt, `|`,
Prose, alles Sonstige.

Weitere Bedingungen: `1 <= count('=') <= 7` und keine leere Seite an `=`.

## Befund 2: `SymPyChecker` ist ein anderes, breiteres Schema

```python
lhs_str, rhs_str = line.split("=", 1)
lhs = sympify(lhs_str.strip()); rhs = sympify(rhs_str.strip())
diff = simplify(lhs - rhs)
```

`sympify` akzeptiert **implizite Multiplikation** (`2x`), Single-Letter-Symbole,
Potenzschreibweise (`x**2`), `sqrt`. Es **rejectet** aber `·`, `×`, `÷`,
`≤`, `|`, Prose, `12.5%`.

**Empirisch geprüft (SymPy 1.14.0):**

| Eingabe | `sympify` | Ergebnis |
|---|---|---|
| `17*3=3*10+3*7` | Error | `=` gehört nicht in einen Ausdruck |
| `17·3=3·10+3·7` | Error | `·` unbekannt |
| `2x + 6 = 16` | Error | implizite Multiplikation **innerhalb** eines Strings mit `=` nicht parsebar; `sympify('2x')` allein wäre ok |
| `215,6` | **ok** | → Tupel `(215, 6)` — **stiller Fehler** |
| `3.5` | ok | → Float |
| `12.5%` | Error | |
| `7x+1≤11x+5|-1` | Error | |
| `\frac{1}{2}` | Error | |

**Der stille Fehler `215,6` → `(215, 6)`** ist relevant: SymPy meldet
keinen Fehler, aber das Ergebnis ist ein Tupel statt einer Zahl. Im
`SymPyChecker` fällt das erst bei `simplify(lhs - rhs)` auf
(`unsupported operand type(s) for -: 'tuple' and 'Integer'`) — also
**spät** und mit schwer lesbarer Meldung.

## Abgeleiteter Eingabedatenvertrag

Die OCR-Schicht muss liefern:

### V1 — Zeilen

Jede Zeile ist **eine** Aussage. Kein Prose-Mix, keine Vermischung von
Rechenschritten und Kommentaren in einer Zeile.

### V2 — Zeichensatz

**Variante A (`arithmetic`, produktiv):** ausschließlich Zeichen aus
`[\d\s.()+*/^=−×·÷²³-]`.

**Variante B (`SymPyChecker`, symbolisch):** von `sympify` parsebar,
also u. a. Single-Letter-Symbole und implizite Multiplikation.

**Die Wahl zwischen A und B ist eine Produktentscheidung, keine
OCR-Entscheidung.** Beide Validatoren existieren. `arithmetic` ist der
produktivere Pfad (`algebra-agent`), `SymPyChecker` der engere
(`urgent-Math-help`). Die OCR-Schicht muss den Vertrag des jeweils
eingesetzten Validators bedienen — **beide** Formen sind von der Engine
lieferbar, die Entscheidung liegt beim Aufrufer.

### V3 — Multiplikationszeichen

| Form | `arithmetic` | `SymPyChecker` |
|---|---|---|
| `*` | ✓ | ✓ |
| `·` (U+00B7) | ✓ (normalisiert) | ✗ |
| `×` (U+00D7) | ✓ (normalisiert) | ✗ |
| implizit `2x` | ✗ (Regex) | ✓ (einzeln) |

**Empfehlung:** `*` als kanonische Ausgabe, `·`/`×` als erlaubte
Eingaben. Das ist die einzige Form, die **beide** Validatoren akzeptieren.

### V4 — Dezimaltrennzeichen

**Nur `.` (Punkt).** Komma ist verboten (`arithmetic`: nicht im Regex;
`SymPyChecker`: stiller Tupel-Fehler). Deutsche Schreibweise mit Komma
muss vor dem Validator umgesetzt werden — **bevor** sie als Text
weitergegeben wird, sonst ist der Fehler nicht mehr sichtbar.

### V5 — Dezimalzahlen

`arithmetic.value()` parst `3.5` **nicht**:

```
value('3.5')    -> 7/2      ✅  (einzeln aufgerufen)
value('3.5 = 3.5') -> SyntaxError
```

Der Grund: `ast.parse` erzeugt `ast.Constant(value=3.5)` mit Typ `float`;
`visit()` akzeptiert aber nur `type(n.value) in (int, float)` → es
*wird* akzeptiert, aber `Fraction(str(3.5))` → `Fraction('3.5')` wirft
`ValueError`. **Ergebnis:** `numeric_equations(['3.5 = 3.5'])` ist `True`,
der Wert ist aber nicht berechenbar. Das ist ein **Widerspruch zwischen
der Whitelist und dem Evaluator** — im produktiven Code.

**Konsequenz für den Vertrag:** Dezimalzahlen mit `.` sind zwar
whitelist-konform, aber nicht auswertbar. Der Vertrag muss daher
fordern, dass Dezimalzahlen **keine** Priorität haben, oder die
Whitelist muss um `.` verkürzt werden. **Offen, nicht entschieden.**

### V6 — Ungleichungen

`≤` ist in **beiden** Validatoren verboten. `7x+1≤11x+5|-1` aus dem
Konsens-Datensatz ist für keinen von beiden auswertbar. Ungleichungen
brauchen einen **dritten** Vertragspfad (oder sind als „nicht prüfbar"
zu markieren).

### V7 — Zeilenreihenfolge

Für den Rechenweg muss die Reihenfolge der Zeilen stimmen. Das ist die
Motivation für Metrik **B3 (Read Order Edit Distance)** aus
`ADR-002-metriken.md` und für die Vision-Bounding-Boxen aus
`ADR-003-strukturoutputs.md`.

## Was die OCR-Schicht dafür braucht (und heute nicht nutzt)

| Bedarf | Erfüllbar mit | Heute genutzt |
|---|---|---|
| `·` vs `×` vs `*` unterscheiden | Zeichenebene | ✓ (Zeichenebene) |
| Komma → `.` | Zeichenebene | ✓ |
| `2x` (Buchstabe) | Zeichenebene | ✓ |
| Zeilenreihenfolge | **Vision-Bounding-Boxen** | ✗ |
| beste Variante wählen (Top-N) | **Vision-Top-Candidaten** | ✗ |
| `12.5%` → parsebar | Top-N + Auswahlregel | ✗ |
| Exponent/Hochstellung | **Box-Geometrie** oder `ocr/post.py` | teilweise (`detect_sup`) |

**Die zwei wichtigsten Hebel sind die bereits verfügbaren, aber
ungenutzten Top-N-Kandidaten und Bounding-Boxen** (siehe
`ADR-003-strukturoutputs.md`).

## Gefundene Inkonsistenzen (Bugs, nicht Design)

1. **`arithmetic`: Dezimalpunkt whitelisted, aber nicht auswertbar.**
   `numeric_equations(['3.5 = 3.5']) == True`, `value('3.5')` wirft.
2. **`SymPyChecker`: Komma erzeugt stillen Tupel-Fehler** statt
   eines Parse-Fehlers. Die Fehlermeldung kommt erst bei `simplify`.
3. **`SymPyChecker` vs. `arithmetic`: `sympify('2x')` funktioniert,
   `ast.parse('2x')` nicht.** Die Validatoren akzeptieren
   **verschiedene** Eingabesprachen — ohne dokumentierten Adapter.

## Konsequenz

- Der Vertrag ist **verträglich mit der heutigen OCR-Pipeline**: `·` wird
  bereits geliefert, `·` ist im `arithmetic`-Validator erlaubt. Die
  `real_math`-Zeilen im Konsens-Datensatz sind überwiegend `arithmetic`-
  kompatibel.
- Der Vertrag macht **C1 (Parsebarkeit, ADR-002)** zur harten
  Vorbedingung für C2 (Äquivalenz). Ohne C1 ist C2 bedeutungslos.
- Die drei Inkonsistenzen gehören **nicht** in dieses ADR (keine
  Architekturänderung im Auftrag) — sie sind als Befund dokumentiert und
  sollten in `algebra-agent` bzw. `urgent-Math-help` separat adressiert
  werden.
- **Nicht entschieden:** A oder B als kanonisches Format. Das ist eine
  Produktentscheidung (welcher Validator im Tutor läuft) und gehört
  zur Tutor-Seite, nicht zur OCR-Seite.

## Offen

- Welcher Validator ist der kanonische? (`algebra-agent/arithmetic.py`
  vs. `urgent-Math-help/checker.py`)
- Wie wird mit `≤`, `|`, `%`, `√` umgegangen — Verwerfen, Markieren
  oder eigener Pfad?
- Wird die Zeile "diese Rechnung ist falsch" vom OCR oder vom Tutor
  entschieden? (Der Vertrag legt nur das Format fest, nicht die
  Bewertung.)
