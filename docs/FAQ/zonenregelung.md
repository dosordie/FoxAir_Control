# Zonenregelung – Raumfühler, Thermostate und Mischer

Die FoxAir-/PHNIX-Steuerung unterstützt **zwei Heizzonen**, beispielsweise **Zone 1 mit Heizkörpern** und **Zone 2 mit Fußbodenheizung und Mischer**. Beim untersuchten **PC4003-G-Mainboard der FoxAir GL9** sind die wesentlichen Fühler- und Relaisanschlüsse direkt auf der Platine vorhanden.

**Für die lokale Regelung über Raumfühler oder passive Thermostatkontakte ist grundsätzlich keine externe Hydraulikstation erforderlich.** Die Angaben beziehen sich vor allem auf die untersuchte Mainboard-Firmware **V3.5**. Je nach Gerätevariante sind nicht alle Anschlüsse bis zum äußeren Klemmfeld geführt.

## Zonenregelung aktivieren: Z01 / Register 1069

| Z01 | Betriebsart |
| ---: | --- |
| 0 | Zonenregelung aus |
| **1 / 2 / 3** | **Raumfühler (S):** Zone 1 / Zone 2 / beide |
| **4 / 5 / 6** | **Kommunikationsthermostat (T):** Zone 1 / Zone 2 / beide |
| **7 / 8 / 9** | **Passives Thermostat (P):** Zone 1 / Zone 2 / beide |

- **S (Sensor):** Die Regelung nutzt gemessene Raumtemperaturen und eingestellte Raum-Sollwerte.
- **T (Thermostat):** Für passende digitale Raumthermostate über einen Kommunikationsanschluss.
- **P (Passiv):** Ein externer Kontakt meldet lediglich Wärmebedarf. Eine Raumtemperatur wird dabei nicht übertragen.

## Lokale Eingänge und Ausgänge

Die folgenden Bezeichnungen gelten für die **PC4003-Platine**, nicht automatisch für die nummerierten Klemmen am Außengerät.

| Mainboardanschluss | Funktion |
| --- | --- |
| **AI/DI07 + GND** | Raumtemperaturfühler **Zone 1** oder passives Thermostat Zone 1 |
| **AI17 (50K) + GND** | Raumtemperaturfühler **Zone 2** oder passives Thermostat Zone 2 |
| **AI/DI15 + GND** | **Zone 2: Vorlauffühler nach dem Mischer** |
| **RO02 / RO03** | 3-Punkt-Mischventil Zone 2 (zwei Stellrichtungen) |
| **RO14** | Heizkreispumpe Zone 1 |
| **RO15** | Heizkreispumpe Zone 2 |

**Achtung:** Die Eingänge können je nach Konfiguration mehrfach genutzt sein. AI17 ist in der Herstellerbelegung beispielsweise zusätzlich als Warmwasserkontakt vorgesehen. Vorhandene Brücken, Abschlusswiderstände und Kabel deshalb nicht ohne Prüfung des eigenen Schaltplans entfernen.

Weitere Details zu den Ausgängen stehen unter [Relaisausgänge am Mainboard](relais_ausgaenge.md).

## Mit lokalen Raumtemperaturfühlern regeln (Z01 = 1–3)

- **Zone 1** misst die Raumtemperatur an **AI/DI07**; Anzeige in **Modbus 2160**.
- **Zone 2** misst die Raumtemperatur an **AI17 (50K)**; Anzeige in **Modbus 2162**.
- Die Raumtemperatur-Korrekturen sind **1353** (Zone 1) und **1354** (Zone 2). Dies sind **Offsets**, keine Eingaberegister für beliebige Raumtemperaturen.

**NTC-Typ:** Für AI/DI07 und den Mischervorlauffühler spricht die bisherige Analyse für **5 kΩ bei 25 °C**. AI17 ist als **50K** beschriftet; ein **50-kΩ-NTC** ist daher naheliegend. Die **exakten B-Kennlinien** sind für diese GL9-Eingänge noch nicht vollständig praktisch bestätigt. Einen beliebigen Sensor mit passendem Nennwiderstand daher nicht automatisch als kompatibel ansehen.

## Passive Thermostate / Hausautomation (Z01 = 7–9)

An denselben lokalen Eingängen können stattdessen **passive Thermostatkontakte** ausgewertet werden:

- Zone 1: **AI/DI07 + GND**
- Zone 2: **AI17 + GND**

Damit ist eine Wärmeanforderung aus einer externen Raumregelung bzw. Hausautomation grundsätzlich möglich – **ohne Raumtemperaturfühler und ohne Hydraulikstation**.

Im Firmwarepfad bedeutet der interne Eingangswert **0 = Wärmeanforderung**, **ungleich 0 = keine Wärmeanforderung**. Ob das am konkreten Eingang einem **geöffneten oder geschlossenen Kontakt** entspricht, ist noch nicht elektrisch bestätigt. **Nicht auf Verdacht brücken und keine Fremdspannung einspeisen.**

Im passiven Betrieb werden keine tatsächlichen Raumtemperaturen gemessen. **2160 / 2162 können daher 0,0 °C anzeigen**, ohne dass das einen Fehler bedeutet.

## Digitale Raumthermostate (Z01 = 4–6)

Diese Betriebsarten verwenden einen **separaten Thermostat-Datenpfad**. Die PC4003-Anschlussbeschreibung nennt **JP5_3 (RS485)** für digitale Thermostate 1 und 2. Das ist weder der lokale passive Kontakt noch automatisch die externe Hydraulikstation.

Das genaue Kommunikationsprotokoll ist noch nicht vollständig bekannt. Ein beliebiges Modbus-Raumthermostat ist deshalb **nicht automatisch kompatibel**.

## Mischerregelung für Zone 2

Für eine geregelte Fußbodenheizungszone benötigt die FoxAir zusätzlich die **Vorlauftemperatur hinter dem Mischer**:

- **AI/DI15 + GND**: lokaler Mischervorlauffühler
- **RO02 / RO03**: Auf-/Zu-Steuerung des 3-Punkt-Mischers
- **RO15**: Zonenpumpe
- **2161**: Mischervorlauf **Ist**
- **2165**: Heizwasser-Sollwert Zone 2
- **2163**: interner Mischerstellwert / Mischverhältnis (0–100 %)

Der Mischervorlauffühler ist **nicht** der normale Wärmepumpen-Vorlauffühler T02. Auch der Raumfühler für Zone 2 ersetzt ihn nicht.

**2163 ist keine gemessene mechanische Ventilstellung.** Das Display stellt den Wert teilweise invertiert dar; 0 % oder 100 % deshalb nicht ungeprüft als „ganz offen“ bzw. „ganz geschlossen“ interpretieren.

Ist AI/DI15 im Geräteschaltplan **nach GND gebrückt**, kann die Firmware den Kurzschluss als ungültigen Sensor interpretieren. **2161 = 0,0 °C** ist auch bei deaktivierter Zone möglich und damit kein Beweis für tatsächlich 0 °C Vorlauf.

## Wichtige Zonenparameter

| Parameter / Modbus | Bedeutung |
| --- | --- |
| **Z01 / 1069** | Zonenbetrieb und Eingangstyp (S/T/P) |
| Z02 / 1070 | Raumtemperatur-Sollwert Zone 1 |
| Z03 / 1071 | Startdifferenz Raumtemperatur Zone 1 |
| Z04 / 1072 | Raumtemperatur-Sollwert Zone 2 |
| Z05 / 1073 | Startdifferenz Raumtemperatur Zone 2 |
| **Z06 / 1075** | Heizwasser-Solltemperatur Zone 1 |
| **Z07 / 1076** | Heizwasser-/Mischwasser-Solltemperatur Zone 2 |
| Z17 / 1077 | Außentemperaturkompensation Zone 2 |
| 1078 / 1079 | Kennlinienparameter Zone 2 |
| Z08 / 1080 | Einstellung manuelle Mischerstellung / Automatik |
| Z09 / 1082 | Öffnungszeit des Mischers |
| Z10 / 1084 | Schließzeit des Mischers |
| Z11 / 1085 | Mischer-P-Anteil |
| Z12 / 1088 | Mischer-I-Anteil |
| Z13 / 1090 | Mischer-Regelzyklus |
| 1353 / 1354 | Korrektur der beiden Raumtemperaturen |
| **H30 / 1036** | Typ der optionalen Hydraulikstation |

Die Mischer-Laufzeiten und Reglerparameter müssen zum vorhandenen Antrieb passen. Die grundlegende Wärmepumpen-Regelauswahl **H25** ist davon zu unterscheiden; siehe [Heizungsregelung und Heizkurve](regelung_heizkurve.md).

## Wichtige Modbus-Anzeigen

| Register | Wert |
| ---: | --- |
| **2160** | Zone 1 Raumtemperatur **Ist** |
| **2161** | Zone 2 Mischervorlauf **Ist** |
| **2162** | Zone 2 Raumtemperatur **Ist** |
| **2163** | Mischerstellwert / Mischverhältnis |
| **2164** | Wassersollwert Zone 1 nach AT-Kompensation |
| **2165** | Wassersollwert Zone 2 nach AT-Kompensation |
| **2018 Bit 8** | Pumpe Zone 1 / RO14 |
| **2018 Bit 9** | Pumpe Zone 2 / RO15 |

Temperaturen sind im Modbus mit **0,1 °C pro Rohwert** skaliert. Diese **Statusregister sind zum Lesen** gedacht: Das direkte Schreiben einer vorgegebenen Raumtemperatur auf **2160/2162** ist nicht als unterstützter Weg bestätigt.

Siehe auch [Modbus-Anschluss am Klemmfeld](modbus.md).

## Was ist mit einer externen Hydraulikstation?

**Sie ist für die lokalen Varianten nicht erforderlich.** Die Firmware unterstützt aber alternative Datenquellen über ein externes Hydraulikmodul. Bei **H30 / 1036 = 3** kommen in der untersuchten V3.5 die **Raumtemperaturen, passiven Zonen-Eingangszustände und die Mischervorlauftemperatur** aus dem Hydraulikmodulpfad statt von den entsprechenden lokalen Mainboard-Eingängen.

Das Mainboard spricht diese Variante über seinen **internen RS485-Bus (Moduladresse 0x61)** an – **nicht** über den gewöhnlichen Benutzer-Modbus am äußeren Klemmfeld. Die einzelnen Register und ein möglicher Modul-Emulator sind noch nicht vollständig bestätigt.

**H30 nicht allein zu Testzwecken umstellen:** Damit wird die erwartete Geräte-/Modulkonfiguration geändert.

## Häufige Fragen

**Warum stehen die Raumtemperaturen oder der Mischervorlauf auf 0,0 °C?**  
Mögliche Ursachen sind eine inaktive Zone (Z01), der passive Thermostatmodus ohne Temperaturmessung, fehlende/überbrückte Fühler oder eine über H30 anders gewählte Sensorquelle.

**Kann ich nur Zone 2 aktivieren?**  
Ja: **Z01 = 2 (Sensor), 5 (Kommunikationsthermostat) oder 8 (passives Thermostat)**. Für den Mischerbetrieb ist zusätzlich der Vorlauffühler nach dem Mischer erforderlich.

**Kann meine Hausautomation die Heizkreise anfordern?**  
Grundsätzlich ja, über die dafür vorgesehenen **passiven Eingänge**, sofern die elektrische Kontaktbeschaltung der eigenen Platine geprüft wurde. Eine direkte Vorgabe der beiden Raumtemperatur-Istwerte über den normalen Modbus ist nicht nachgewiesen.

**Sind AI/DI07, AI17 und AI/DI15 am Außenklemmenfeld erreichbar?**  
Nicht zwingend. Die Bezeichnungen gehören zu den **Platinenanschlüssen**. Ausschlaggebend ist der Schaltplan der jeweiligen Wärmepumpe.

> **Sicherheit:** Im Gerät können 230-V-Anschlüsse vorhanden sein. Sensoren, Brücken und Kontakte nur bei vollständig abgeschalteter Versorgung prüfen oder ändern. Keine externe Spannung auf die AI/DI-Eingänge geben. Arbeiten an Relais, Pumpen und Mischerantrieb nur durch entsprechend fachkundige Personen.

---

*Stand: untersuchte FoxAir GL9 / PC4003-G mit Mainboard-Firmware V3.5. Anschlussfunktionen durch PC4003-Unterlagen gestützt; nicht alle Kombinationen wurden an einer realen Anlage durchgetestet.*
