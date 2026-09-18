# Externer Außentemperaturfühler

Mit Mainboard-Firmware **V3.4** kann die FoxAir einen zweiten, externen Außentemperaturfühler verwenden.

Wichtig: Der externe Fühler ersetzt den eingebauten Außentemperaturfühler **nicht in jeder Funktion**. Einige Regelungen verwenden den externen Wert, andere greifen weiterhin auf den internen Fühler zurück.

## Anschluss

Der Anschluss wurde praktisch getestet und ist bestätigt:

- **Klemme 4** = Sensorsignal
- **Klemme 3** = GND
- verwendet wird das Klemmenpaar der bisherigen **DIN2 / Remote Heat-Cool**-Funktion

## Fühlertyp

Verwendet wird ein **NTC mit 2,2 kΩ bei 25 °C** und einer Kennlinie um **B ≈ 3250 K**.

Passend zur ermittelten Kennlinie ist z. B. der **TDK NTCG203FH222JT1**.

Gemessene Vergleichswerte:

| Widerstand | angezeigte Temperatur |
| ---: | ---: |
| 2,27 kΩ | +24,1 °C |
| 3,02 kΩ | +16,6 °C |
| 6,76 kΩ | -2,7 °C |
| 10,0 kΩ | -11,7 °C |

## Aktivieren

Register **1463** wählt den verwendeten Außentemperaturfühler:

- **0** = interner Außentemperaturfühler
- **1** = externer Außentemperaturfühler

## Wichtige Register

- **1463** = internen oder externen AT-Fühler auswählen
- **2033** = Temperatur des externen AT-Fühlers
- **2048** = von der Regelung verwendete Außentemperatur
- **2088 Bit 7** = Fehler externer AT-Fühler
- **2136** = Temperatur des internen AT-Fühlers

Bei aktiviertem und funktionierendem externem Fühler zeigen **2033 und 2048** dessen Temperatur an.  
**2136** zeigt weiterhin den internen Außentemperaturfühler.

Damit können gleichzeitig zwei unterschiedliche Außentemperaturen sichtbar sein.

## Welche Funktionen verwenden den externen Außentemperaturfühler?

### Heizkurve / Außentemperaturkompensation

**Ja.**

Die Heizkurve bzw. Außentemperaturkompensation verwendet die wirksame Außentemperatur. Ist der externe Fühler aktiviert, wird dafür dessen Temperatur verwendet.

### EEV – temperaturabhängige Start-/Basisöffnung

**Ja.**

Die Wärmepumpe besitzt für das elektronische Expansionsventil die Parameter **E03-1 bis E03-5**. Welcher Wert verwendet wird, hängt von der Außentemperatur ab:

| Außentemperatur | Parameter |
| --- | --- |
| ab +7,1 °C | E03-1 |
| +0,1 bis +7,0 °C | E03-2 |
| -4,9 bis 0,0 °C | E03-3 |
| -9,9 bis -5,0 °C | E03-4 |
| bis -10,0 °C | E03-5 |

Bei aktiviertem externem AT-Fühler erfolgt diese Auswahl nach dessen Temperatur.

### EEV – temperaturabhängige Mindestöffnung

**Teilweise.**

Bei höherer Kompressorleistung verwendet die Wärmepumpe die temperaturabhängigen Parameter **E07-1 bis E07-5**. Auch hier wird bei aktiviertem externem Fühler dessen Temperatur verwendet.

Unterhalb von etwa **61 Hz Kompressorfrequenz** wird dagegen der allgemeine Wert **E07** verwendet. In diesem Bereich hat die Außentemperatur auf diese Mindestöffnung keinen Einfluss.

### Smart-EEV

**Ja.**

Im EEV-Modus **Smart** ist die Außentemperatur ein direkter Bestandteil des Kennfelds. Der externe AT beeinflusst damit die Vorsteuerung des Expansionsventils.

Neben der Außentemperatur berücksichtigt die Smart-Regelung auch die Kompressorleistung und die Einlasswassertemperatur.

### Automatische EEV-Regelung

**Nicht direkt.**

Die eigentliche automatische EEV-Regelung regelt hauptsächlich nach Überhitzung und Heißgastemperatur.

Der externe AT kann das EEV trotzdem indirekt beeinflussen, weil zuvor die temperaturabhängigen E03- und teilweise E07-Werte ausgewählt werden.

### EEV beim Abtauen

**Für die direkte EEV-Zielposition nein.**

Während des Abtauens verwendet die Wärmepumpe den eigenen Parameter **E17** als EEV-Zielposition. Die E03-/E07-Temperaturbereiche bestimmen diese Position nicht.

Ob der externe AT zusätzlich andere Teile der Abtaustart- oder Abtauende-Logik beeinflusst, ist noch nicht vollständig geklärt.

### Kurbelgehäuse-/Kompressorheizung

**Nein.**

Die Kurbelgehäuseheizung verwendet weiterhin den **internen Außentemperaturfühler**.

Die bekannten Schaltpunkte sind ungefähr:

- unter **8,1 °C** → Heizung EIN
- zwischen **8,1 und 9,9 °C** → Zustand bleibt erhalten
- ab **10,0 °C** → Heizung AUS

Das bedeutet: Selbst wenn der externe Fühler beispielsweise -10 °C meldet, kann die Kurbelgehäuseheizung weiterhin nach einer deutlich höheren internen Außentemperatur entscheiden.

## Noch nicht vollständig geklärt

Für einige Sonder- und Schutzfunktionen ist noch nicht abschließend geklärt, ob sie den internen oder externen Außentemperaturfühler verwenden. Dazu gehören unter anderem:

- vollständige Abtaustart-/Abtauende-Logik
- A34-Kaltstart-/Vorheizfunktion
- Wannenheizung
- weitere temperaturabhängige Schutzfunktionen

## Verhalten bei fehlendem oder defektem externem Fühler

Ist der externe Fühler aktiviert, aber nicht angeschlossen oder defekt:

- Register **2033** zeigt einen ungültigen Wert; im Test wurden **409,1 °C** beobachtet
- **2088 Bit 7** wird gesetzt
- die Wärmepumpe läuft weiter
- für die wirksame Außentemperatur wird wieder der interne Fühler verwendet

Ein Ausfall des externen Fühlers legt die Wärmepumpe daher nicht still.
