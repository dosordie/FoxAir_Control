# Externer Außentemperaturfühler

Mit Mainboard-Firmware **V3.4** kann die FoxAir einen zweiten, externen Außentemperaturfühler verwenden.

Der externe Fühler ersetzt den internen T04 dabei **nicht global in jeder Funktion**. Die Firmware besitzt einen umschaltbaren **wirksamen T04-Pfad** und daneben einzelne Funktionen, die weiterhin direkt den internen T04 lesen.

## Anschluss

Der Anschluss wurde praktisch getestet und ist bestätigt:

- **Klemme 4** = Sensorsignal
- **Klemme 3** = GND
- Klemmenpaar der bisherigen **DIN2 / Remote Heat-Cool**-Funktion

Ein Widerstand zwischen Klemme 3 und 4 wird bei aktiviertem externem AT-Eingang als Temperatursensor ausgewertet.

## Fühlertyp

Verwendet wird ein **NTC mit 2,2 kΩ bei 25 °C** und einer Kennlinie um **B ≈ 3250 K**.

Passend zur ermittelten Kennlinie ist z. B. der Typ **TDK NTCG203FH222JT1**:

- R25 = 2,2 kΩ
- B25/50 = 3248 K
- B25/85 = 3300 K

Die gemessenen Punkte am realen Eingang passen dazu:

| Widerstand | angezeigte Temperatur |
| ---: | ---: |
| 2,27 kΩ | +24,1 °C |
| 3,02 kΩ | +16,6 °C |
| 6,76 kΩ | -2,7 °C |
| 10,0 kΩ | -11,7 °C |

## Aktivieren

Register **1463** wählt den Außentemperaturpfad:

- **0** = normaler/interner T04
- **1** = externer Außentemperaturfühler

Bei `1463 = 1` wird der externe Sensor über den zusätzlichen Sensorkanal 23 eingelesen.

## Relevante Register

- **1463** = Auswahl interner/externer AT
- **2033** = direkter Messwert des externen AT-Fühlers
- **2048** = wirksame/öffentliche Außentemperatur T04
- **2088 Bit 7 (0x0080)** = Fehler des externen AT-Pfads
- **2136** = direkter interner T04-Wert; bleibt vom Umschalten auf den externen Fühler unberührt

Bei gültigem externem Sensor gilt:

```text
1463 = 1
   → externer Sensorkanal 23
   → 2033
   → 2048 = wirksame Außentemperatur
```

Live getestet wurde z. B. mit **6,76 kΩ**:

```text
2033 = -2,7 °C
2048 = -2,7 °C
2088 Bit 7 = 0
```

## Wo wirkt der externe AT?

### Heizkurve / Außentemperaturkompensation

Die Heizkurven-/Außentemperaturkompensation arbeitet mit dem **wirksamen T04-Pfad**. Bei `1463 = 1` geht damit der externe AT in diesen Regelpfad ein.

### EEV: E03-1 … E03-5

Die temperaturabhängigen Heiz-Basis-/Startöffnungen des Haupt-EEV werden direkt nach T04 ausgewählt. Bei aktivem externem AT gelten daher dessen Werte:

| Bereich der wirksamen T04 | verwendeter Parameter |
| --- | --- |
| ≥ +7,1 °C | E03-1 |
| +0,1 … +7,0 °C | E03-2 |
| -4,9 … 0,0 °C | E03-3 |
| -9,9 … -5,0 °C | E03-4 |
| ≤ -10,0 °C | E03-5 |

Die Auswahl besitzt keine zusätzliche Hysterese.

### EEV: E07-1 … E07-5

Auch die temperaturabhängigen EEV-Mindestöffnungen verwenden T04 mit denselben fünf Temperaturbereichen.

Wichtig ist die zusätzliche Frequenzbedingung:

- bei **Kompressor-Istfrequenz < 61 Hz** wird das globale **E07** verwendet
- ab **61 Hz** wird – bei aktivem E07-Schutzpfad – **E07-1 … E07-5 nach T04** ausgewählt

Der externe AT beeinflusst die E07-x-Auswahl daher **nur in diesem ≥61-Hz-Pfad**. Unter 61 Hz hat die Außentemperatur auf diese Mindestöffnung keinen Einfluss.

### Smart-EEV

Im Modus **E01 = 2 / Smart** ist T04 eine direkte Achse des Smart-Kennfelds.

Das Smart-Ziel wird aus drei Größen gebildet:

```text
Kompressor-Sollfrequenz
× T04 / wirksame Außentemperatur
× T01 / Einlasswassertemperatur
```

Die T04-Achse verwendet **MAIN:2048** und besitzt sechs Zustände mit Hysterese:

| Übergang nach oben | Rückschaltung |
| ---: | ---: |
| -12,9 °C | -14,9 °C |
| -6,9 °C | -8,9 °C |
| +0,1 °C | -1,9 °C |
| +7,1 °C | +5,1 °C |
| +20,1 °C | +18,1 °C |

Damit wirkt der externe AT im Smart-Modus direkt auf die Kennfeld-Vorsteuerung des Haupt-EEV.

## Wo wirkt der externe AT nicht direkt?

### Auto-EEV-Feedbackregelung

Im Modus **E01 = 1 / Auto** verwendet die eigentliche geschlossene EEV-Feedbackregelung **nicht direkt T04**.

Die wesentlichen Regelgrößen sind:

- **MAIN:2066** = Abgasüberhitzung
- **MAIN:2053 / T12** = Heißgastemperatur
- **MAIN:2067** = Rückgas-/Saugüberhitzung

Die Auto-Regelung arbeitet mit einer 4×5-Zustandsmatrix aus 2066 und T12 und regelt anschließend gegen die Saugüberhitzung 2067.

T04 kann den EEV-Betrieb trotzdem **indirekt** über die vorgelagerten E03-Basisöffnungen und – wenn aktiv – über E07/E07-x beeinflussen. Die eigentliche Auto-Feedbackmatrix selbst hat aber keine T04-Achse.

### EEV während Abtauung

Im öffentlichen Abtaubetrieb **MAIN:2012 = 2** wird **E17** als direkte Haupt-EEV-Zielöffnung verwendet.

Für diesen EEV-Zielwert wird nicht zwischen E03-/E07-T04-Bändern gewählt.

Das bedeutet jedoch **nicht**, dass damit bereits die komplette Abtaustart-/Abtauende-Logik hinsichtlich interner oder externer AT vollständig bewertet ist.

### Kurbelgehäuse-/Kompressorheizung

Die Kurbelgehäuseheizung verwendet ausdrücklich **nicht** den wirksamen 2048-Pfad.

Sie liest den internen T04 / Sensorkanal 3 direkt:

- unter **8,1 °C** → Kurbelgehäuseheizung EIN
- von **8,1 bis unter 10,0 °C** → Zustand halten
- ab **10,0 °C** → Kurbelgehäuseheizung AUS

Der Status wird über **2019 Bit 11** sichtbar.

Auch **Register 2136** bleibt der direkte interne T04-Wert und folgt nicht dem externen Sensor.

Dadurch können bei aktiviertem externem AT bewusst zwei verschiedene Außentemperaturen gleichzeitig vorhanden sein:

```text
2033 / 2048 = externer bzw. wirksamer AT
2136        = interner T04
```

## Noch nicht für jede Funktion geschlossen

Aus `2048 = externer AT` darf nicht automatisch geschlossen werden, dass **jede** temperaturabhängige Schutz- oder Sonderfunktion den externen Wert benutzt.

Für einzelne weitere Pfade – z. B. vollständige Abtau-Start-/Endelogik, A34-Kaltstartvorheizung, Wannenheizung oder weitere Schutz-/Grenzfunktionen – muss der konkrete Sensorzugriff jeweils separat geprüft werden.

## Verhalten bei fehlendem oder defektem externem Fühler

Ist `1463 = 1`, der externe Sensor aber offen oder ungültig:

- **2033** liefert einen ungültigen Grenzwert; im Test wurde **409,1 °C** beobachtet
- **2088 Bit 7** wird gesetzt
- die Wärmepumpe läuft weiter
- der wirksame Außentemperaturpfad fällt auf den normalen T04 zurück

Der externe Fühler ist damit kein zusätzlicher Zwangssensor, dessen Ausfall die Wärmepumpe stilllegt.
