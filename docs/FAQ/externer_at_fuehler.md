# Externer Außentemperaturfühler

Mit Mainboard-Firmware **V3.4** kann die FoxAir einen zweiten, externen Außentemperaturfühler verwenden.

Der externe Fühler ersetzt den internen T04 dabei **nicht global in jeder Funktion**. Die Firmware besitzt einen umschaltbaren „wirksamen“ Außentemperaturpfad und daneben einzelne Funktionen, die weiterhin direkt den internen T04 lesen.

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

## Welche Funktionen verwenden den externen AT?

Alle Funktionen, die den **wirksamen T04-Pfad / Register 2048** benutzen, sehen bei `1463 = 1` den externen Außentemperaturwert.

Firmwareseitig bestätigt sind insbesondere:

- **Außentemperatur-/Wetterkompensation bzw. Heizkurven-Regelpfad**
- **Smart-EEV-Kennfeld**
- temperaturabhängige **E07-x-Auswahl** im EEV-Regelpfad bei höherer Verdichterfrequenz
- Anzeige bzw. Veröffentlichung der wirksamen Außentemperatur über **2048**

## Welche Funktionen verwenden weiterhin den internen T04?

Mindestens die **Kurbelgehäuse-/Kompressorheizung** verwendet ausdrücklich **nicht** den externen AT-Pfad.

Sie liest den internen T04/Sensorkanal 3 direkt:

- unter **8,1 °C** → Kurbelgehäuseheizung EIN
- von **8,1 bis unter 10,0 °C** → Zustand halten
- ab **10,0 °C** → Kurbelgehäuseheizung AUS

Der Status wird unter anderem über **2019 Bit 11** sichtbar.

Auch **Register 2136** bleibt der direkte interne T04-Wert und folgt nicht dem externen Sensor.

Dadurch können bei aktiviertem externem AT bewusst zwei verschiedene Außentemperaturen gleichzeitig vorhanden sein:

```text
2033 / 2048 = externer AT
2136        = interner T04
```

## Verhalten bei fehlendem oder defektem externem Fühler

Ist `1463 = 1`, der externe Sensor aber offen oder ungültig:

- **2033** liefert einen ungültigen Grenzwert; im Test wurde **409,1 °C** beobachtet
- **2088 Bit 7** wird gesetzt
- die Wärmepumpe läuft weiter
- der wirksame Außentemperaturpfad fällt auf den normalen T04 zurück

Der externe Fühler ist damit kein zusätzlicher Zwangssensor, dessen Ausfall die Wärmepumpe stilllegt.
