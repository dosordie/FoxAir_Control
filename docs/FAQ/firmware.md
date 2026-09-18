# Firmware-Versionen, Changelog und Display-Update

Bei der FoxAir gibt es mehrere voneinander unabhängige Firmware-Versionen.

Das ist wichtig, weil zum Beispiel **Display V1.7 nicht Mainboard V1.7** bedeutet.

## Welche Firmware gibt es?

| Komponente | Typischer Softwarecode | Beispiele |
| --- | --- | --- |
| Mainboard / Hauptsteuerung | 82400644 | V1.2, V1.3, V3.3, V3.4 |
| kleines DWIN-Display | 82400463 | V1.3, V1.7 |
| LTE-/WarmLink-DTU | z. B. 82400409 | z. B. V1.2 |

Für einen Versionsvergleich deshalb möglichst immer **Softwarecode und Versionsnummer** angeben.

## Mainboard-Firmware – wichtige Änderungen

### V3.3

Bekannte Änderungen:

- automatische Regelung der Hauptumwälzpumpe
- erweiterte Pumpen- und Abtaulogik
- zusätzliche Modbus-Parameter
- SG-Ready-Funktionen erweitert

### V3.4

Bekannte Änderungen gegenüber V3.3:

- Heizkurve und Leistungstimer können gleichzeitig verwendet werden
- überarbeitete Kaltstart-/Vorheizlogik
- neue Strombegrenzungslogik
- erweiterte SG-/PV-Steuerung
- zusätzlicher externer Außentemperaturfühler

Eine ausführlichere technische Übersicht gibt es hier:

[FoxAir / PHNIX Firmware-Übersicht](../firmware_overview.md)

## Display-Firmware aktualisieren

Die Display-Firmware ist unabhängig von der Mainboard-Firmware und wird beim kleinen DWIN-Display über eine Speicherkarte aktualisiert.

Kurzablauf:

1. passendes Display-Firmwarepaket herunterladen und entpacken
2. den vollständigen Ordner **DWIN_SET** auf die Speicherkarte kopieren
3. Display bzw. Wärmepumpe ausschalten
4. Speicherkarte in das Display einsetzen
5. Display einschalten und den Updatevorgang vollständig durchlaufen lassen
6. danach wieder ausschalten
7. Speicherkarte entfernen und Display normal starten

> Während des Updates die Stromversorgung nicht unterbrechen.

### Download der Display-Firmware

**Forum-Link zur Display-Firmware:** _wird noch ergänzt_

<!-- TODO: Forum-Link zur Display-Firmware hier eintragen -->

Bekannte Display-Versionen für Softwarecode **82400463** sind unter anderem V1.3 und V1.7.

## Mainboard-Firmware aktualisieren

Die Mainboard-Firmware wird nicht über die Speicherkarte des Displays aktualisiert.  
Updates laufen über den PHNIX-/WarmLink-/OTA-Weg bzw. den jeweiligen Support.

Vor einem Mainboard-Update empfiehlt es sich, die Einstellungen zu sichern:

[Einstellungen vor einem Firmwareupdate sichern](einstellungen_sichern.md)
