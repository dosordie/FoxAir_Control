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

Die Display-Firmware ist unabhängig von der Mainboard-Firmware.

Das kleine DWIN-Display wird **direkt über eine microSD-/SD-Speicherkarte** aktualisiert. Dafür ist keine Verbindung zu FoxAir Control, Modbus oder zur Cloud notwendig.

### Display-Firmware V1.7

Bekannte Version:

- **Softwarecode:** 82400463
- **Version:** V1.7
- **Build:** 202311131429

Download:

[Display-Firmware 82400463 V1.7 herunterladen](http://apolan.de/downloads/Waermepumpe/Foxair/updates/82400463%20202311131429%20V17.zip)

Der Download wurde im FoxAir-Thread im Photovoltaikforum bereitgestellt:

[FoxAir Wärmepumpen – Erfahrungen, Meinungen, Tipps](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=12)

### Update vorbereiten

1. ZIP-Datei herunterladen und vollständig entpacken.
2. Eine Speicherkarte mit **FAT32** formatieren.
3. Den vollständigen Ordner **DWIN_SET** in das Hauptverzeichnis der Speicherkarte kopieren.

Auf der Speicherkarte muss also direkt dieser Ordner liegen:

```text
DWIN_SET/
```

Nicht den ZIP-Ordner oder einen zusätzlichen übergeordneten Ordner auf die Karte kopieren.

### Update durchführen

1. Wärmepumpe bzw. Display **ausschalten**.
2. Speicherkarte in den Kartenslot des DWIN-Displays einsetzen.
3. Display wieder einschalten.
4. Das Display erkennt **DWIN_SET** automatisch und startet das Update.
5. Während des Updates erscheinen typischerweise ein blauer Bildschirm sowie nacheinander die übertragenen Display-Dateien bzw. Oberflächenbilder.
6. Warten, bis der Updatevorgang vollständig abgeschlossen ist.
7. Display wieder ausschalten.
8. Speicherkarte entfernen.
9. Display normal einschalten.

> **Wichtig:** Während des Updates die Stromversorgung nicht unterbrechen und die Speicherkarte nicht entfernen.

Nach dem Update kann die Versionsnummer des Displays kontrolliert werden.

Bekannte Display-Versionen für Softwarecode **82400463** sind unter anderem V1.3 und V1.7.

## Mainboard-Firmware aktualisieren

Die Mainboard-Firmware wird **nicht** über die Speicherkarte des Displays aktualisiert.  
Updates laufen über den PHNIX-/WarmLink-/OTA-Weg bzw. den jeweiligen Support.

Vor einem Mainboard-Update empfiehlt es sich, die Einstellungen zu sichern:

[Einstellungen vor einem Firmwareupdate sichern](einstellungen_sichern.md)
