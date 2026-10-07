# Externer Außentemperaturfühler

Mit Mainboard-Firmware **V3.4** kann die FoxAir einen zweiten, externen Außentemperaturfühler verwenden.

Der grundlegende externe-AT-Pfad ist auch in **V3.5** weiterhin vorhanden.

Wichtig: Der externe Fühler ersetzt den eingebauten Außentemperaturfühler **nicht in jeder Funktion**. Einige Regelungen verwenden den externen bzw. wirksamen AT-Wert, andere greifen weiterhin direkt auf den internen **T04** zurück.

## Anschluss

Der Anschluss wurde praktisch getestet und ist bestätigt:

- **Klemme 3** = Sensorsignal (DIN2)
- **Klemme 4** = GND
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

Dabei wird der externe Fühler nicht einfach global anstelle von T04 eingesetzt. Die Firmware besitzt einen eigenen **wirksamen / effektiven AT-Wert**, den nur bestimmte Regelpfade verwenden.

## Wichtige Register

| Register | Bedeutung |
| ---: | --- |
| **1463** | internen oder externen AT-Fühler auswählen |
| **1464** | AT-Grenze der globalen Heiz-/Sommerabschaltung |
| **1465** | Verzögerungs-/Verweilzeit dieser Heiz-/Sommerabschaltung |
| **2033** | Temperatur des externen AT-Fühlers |
| **2048** | wirksame / ausgewählte Außentemperatur |
| **2088 Bit 7** | externer AT fehlt bzw. ist ungültig |
| **2136** | Temperatur des internen Außentemperaturfühlers |
| **2146 Bit 4** | Status der AT-basierten Heiz-/Sommerabschaltung, bei V3.5 bestätigt |

Bei aktiviertem und funktionierendem externem Fühler zeigen **2033 und 2048** dessen Temperatur an.  
**2136** zeigt weiterhin den internen Außentemperaturfühler.

Damit können gleichzeitig zwei unterschiedliche Außentemperaturen sichtbar sein.

## Welche Funktionen verwenden den externen Außentemperaturfühler?

Die folgende Tabelle basiert auf der Analyse der Mainboard-Firmware V3.4; die Grundlogik des externen AT ist in V3.5 unverändert.

| Funktion | Verwendet externen AT bei 1463 = 1? | Tatsächlich verwendete AT | Hinweis / Register |
| --- | --- | --- | --- |
| **Wirksame Außentemperatur / Anzeige** | **Ja** | effektiver AT | **MAIN:2048** |
| **Heizkennlinie / AT-Kompensation** | **Ja** | effektiver AT | folgt MAIN:1463 |
| **Elektrische Zusatzheizung – AT-Freigabe** | **Ja** | effektiver AT | **A31 / MAIN:1049** |
| **Elektrische Zusatzheizung – Sofort-/Grenzpfad** | **Ja** | effektiver AT | **R45 / MAIN:1231** |
| **Globale Heiz-/Sommerabschaltung** | **Ja** | effektiver AT | **MAIN:1464 / 1465** |
| **Smart-EEV, E01 = 2** | **Ja** | effektiver AT über **MAIN:2048** | AT ist eine direkte Kennfeldachse |
| **EEV E03-1…E03-5** | **Nein** | interner **T04** direkt | temperaturabhängige Heiz-Basis-/Startöffnung |
| **EEV E07-1…E07-5 ab 61 Hz** | **Nein** | interner **T04** direkt | temperaturabhängige Mindestöffnung |
| **EEV E07 unter 61 Hz** | **Nein / ohne AT-Einfluss** | kein AT-Band | verwendet den allgemeinen Wert **E07** |
| **Auto-EEV, E01 = 1** | **Nicht direkt** | E03/E07-Pfade verwenden lokalen T04 | eigentliche Regelung nach Überhitzung / Heißgas |
| **EEV-Zielposition beim Abtauen** | **Nein** | keine AT-Auswahl für die Zielposition | verwendet **E17** |
| **Abtaustart-/Abtaulogik** | **Nein** | interner **T04** direkt | u. a. **D01 / D07 / D09** |
| **Kurbelgehäuseheizung – Thermostat** | **Nein** | interner **T04** direkt | ca. <8,1 °C EIN / ab 10,0 °C AUS |
| **Kurbelgehäuse-Vorheizung / Kaltstart** | **Nein** | interner **T04** direkt | **A34**, Restzeit wird in V3.4 als MAIN:1561 exportiert |
| **AT-abhängige Heiz-Wassertemperaturbegrenzung** | **Nein** | interner **T04** direkt | **R29–R34 / MAIN:1167–1172** |
| **Max. Heiz-Sollwassertemperatur nach AT** | **Nein** | interner **T04** direkt | **R43 / R44, MAIN:1229 / 1230** |
| **Kühl-Frequenzbegrenzung nach AT** | **Nein** | interner **T04** direkt | **R60 / MAIN:1233** |
| **Auto-Start-Heizpfad – zusätzliche AT-Bedingung** | **Nein** | interner **T04** direkt | **R39 / MAIN:1192**; R39 selbst ist im analysierten Pfad eine Wassertemperaturschwelle |
| **Gehäuse-/Wannenheizung** | **Nein** | interner **T04** direkt | **H42 / MAIN:1356**, D30 = Nachlaufzeit |
| **Außenlüfter-/Fan-Drehzahlregelung** | **Nein** | interner **T04** direkt | F-Parameter / Fan-Regelblock |
| **Multi-Sensor-Zonen-/Betriebsbereichsklassifizierer** | **Nein** | interner **T04** direkt | kombiniert T01, T02 und lokalen T04 |
| **Interne 20/22-°C-Hysterese** | **Nein** | interner **T04** direkt | separater interner Regelpfad |

### Wichtig für E03 / E07 / Smart-EEV

Hier muss zwischen drei verschiedenen Dingen unterschieden werden:

- **E03-1…E03-5:** Auswahl erfolgt nach dem **internen T04**, nicht nach dem externen Fühler.
- **E07-1…E07-5:** oberhalb bzw. ab etwa **61 Hz Kompressor-Istfrequenz** erfolgt die Auswahl ebenfalls nach dem **internen T04**.
- **Smart-EEV (E01 = 2):** die Smart-Kennfeldachse verwendet **MAIN:2048** und damit bei aktivem externem Fühler tatsächlich den **externen AT**.

Damit kann derselbe EEV-Regelkomplex gleichzeitig an verschiedenen Stellen unterschiedliche Außentemperaturquellen verwenden.

## Heizkennlinie / Außentemperaturkompensation

Die Heizkennlinie verwendet den **wirksamen Außentemperaturwert**.

Bei:

```text
1463 = 0
→ interner T04

1463 = 1 und externer Sensor gültig
→ externer AT
```

wird die Heizkennlinie entsprechend mit dem ausgewählten Wert berechnet.

Das ist der wichtigste Anwendungsfall für einen besser platzierten externen Gebäudefühler.

## Heiz-/Sommerabschaltung über 1464 / 1465

Der externe Fühler hat auch dann einen Nutzen, wenn **keine klassische Heizkurve** verwendet wird.

**1464 / 1465** bilden eine globale AT-basierte Heizfreigabe bzw. Sommerabschaltung:

```text
effektiver AT >= 1464
→ nach Ablauf von 1465
→ Heizbetrieb sperren

effektiver AT <= 1464 - 3,0 K
→ nach Ablauf von 1465
→ Heizbetrieb wieder freigeben
```

Die Hysterese beträgt **3,0 K**.

Beispiel:

```text
1464 = 18,0 °C
1465 = 30

AT >= 18,0 °C für ca. 30 min
→ Heizen gesperrt

AT <= 15,0 °C für ca. 30 min
→ Heizen wieder freigegeben
```

Die Einheit von **1465** ist nach der Firmwareanalyse **sehr wahrscheinlich Minuten**.

Bei **1465 = 0** wird der interne Zustand zurückgesetzt; die zeitverzögerte Heizabschaltung ist damit praktisch deaktiviert.

## Beispiel: interner und externer Fühler zeigen stark unterschiedliche Werte

Angenommen:

```text
interner T04 = +10 °C
externer AT  = -10 °C
1463         = 1
```

Dann gilt beispielsweise:

| Funktion | verwendete Temperatur |
| --- | ---: |
| MAIN:2048 / wirksame AT | etwa **-10 °C** |
| Heizkennlinie | etwa **-10 °C** |
| A31 / R45 Zusatzheizung | etwa **-10 °C** |
| 1464/1465 Heiz-/Sommerabschaltung | etwa **-10 °C** |
| Smart-EEV AT-Achse | etwa **-10 °C** |
| E03-1…5 | **+10 °C** |
| E07-1…5 | **+10 °C** |
| Abtaulogik | **+10 °C** |
| Kurbelgehäuseheizung | **+10 °C** |
| R29–R34 / R43 / R44 | **+10 °C** |
| H42 Wannenheizung | **+10 °C** |
| Außenlüfterregelung | **+10 °C** |

Das erklärt, warum sich nach Aktivierung des externen Fühlers **nicht jede temperaturabhängige Funktion gleich verhält**.

## Verhalten bei fehlendem oder defektem externem Fühler

Ist der externe Fühler aktiviert, aber nicht angeschlossen oder defekt:

- Register **2033** zeigt einen ungültigen Wert; im Test wurden **409,1 °C** beobachtet
- **2088 Bit 7** wird gesetzt
- der effektive AT-Selector fällt auf den **internen T04** zurück, solange dieser gültig ist
- die Wärmepumpe läuft weiter

Ein Ausfall des externen Fühlers legt die Wärmepumpe daher nicht still.

## Praktische Einordnung

Der externe Außentemperaturfühler ist besonders sinnvoll, wenn der interne T04 durch die Position direkt am Außengerät nicht repräsentativ für die tatsächliche Gebäudeaußentemperatur ist.

Er beeinflusst aber bewusst **nur ausgewählte Regelpfade**.

Wer ihn verwendet, sollte deshalb nicht davon ausgehen, dass nach **1463 = 1** sämtliche AT-abhängigen Funktionen automatisch auf den externen Fühler wechseln.
