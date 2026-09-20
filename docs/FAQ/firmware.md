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

Das kleine DWIN-Display wird **direkt über eine SD-Speicherkarte** aktualisiert. Dafür ist keine Verbindung zu FoxAir Control, Modbus oder zur Cloud notwendig.

### Display-Firmware V1.7

Mit der Display-Firmware **V1.7** wird die Sprache des Displays von der originalen **polnischen Oberfläche auf Englisch** umgestellt.

Bekannte Version:

- **Softwarecode:** 82400463
- **Version:** V1.7
- **Build:** 202311131429

Download:

[Display-Firmware 82400463 V1.7 herunterladen](https://drive.google.com/file/d/1uNjJeRfVrqpYvHlOIn6u2vSbIlBpba4t/view?usp=sharing)

Alternativer Download:

[Display-Firmware 82400463 V1.7 herunterladen](http://apolan.de/downloads/Waermepumpe/Foxair/updates/82400463%20202311131429%20V17.zip)

> **Achtung:** Das ZIP hinter diesem Link ist nach mehreren Berichten im Forum **fehlerhaft bzw. unzuverlässig**. Es wurden **CRC-Fehler und fehlende Dateien** beobachtet; bei unterschiedlichen Downloads fehlten teilweise unterschiedliche Dateien. Den Download daher **nicht ungeprüft verwenden**. Ein sauberer alternativer V1.7-Mirror ist derzeit nicht bekannt.

Der Download wurde im FoxAir-Thread im Photovoltaikforum bereitgestellt:

[FoxAir Wärmepumpen – Erfahrungen, Meinungen, Tipps](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=12)

### Update vorbereiten

Für das DWIN-Display empfiehlt sich eine **SD-Speicherkarte mit 1 bis 16 GB**.

- **Dateisystem:** FAT32
- **Clustergröße / Allocation Unit:** 4096 Byte
- praktisch getestet wurden **1-GB- und 2-GB-SD-Karten**
- Karten mit mehr als **16 GB** sind für diesen DWIN-Updateweg nicht vorgesehen und sollten vermieden werden

1. ZIP-Datei herunterladen und vollständig entpacken.
2. Eine **SD-Speicherkarte mit 1 bis 16 GB** mit **FAT32 / 4096 Byte Clustergröße** formatieren.
3. Den vollständigen Ordner **DWIN_SET** in das Hauptverzeichnis der SD-Karte kopieren.

Auf der SD-Karte muss also direkt dieser Ordner liegen:

```text
DWIN_SET/
```

Nicht den ZIP-Ordner oder einen zusätzlichen übergeordneten Ordner auf die Karte kopieren.

### SD-Kartenslot am Display erreichen

Der SD-Kartenslot ist von außen nicht zugänglich.

Das Display muss dafür geöffnet werden. Dazu werden auf der Gehäuse rückseite **6 kleine Schrauben** gelöst, darin ist das Display mit **4 kleinen Schrauben** befestigt.

Anschließend kann das Display vorsichtig geöffnet werden, bis der SD-Kartenslot zugänglich ist.

> **Hinweis:** Das Display nicht unter Spannung öffnen. Beim Öffnen darauf achten, Kabel und Steckverbinder nicht zu beschädigen.

### Update durchführen

1. Wärmepumpe bzw. Display **ausschalten**.
2. Display öffnen und SD-Speicherkarte in den Kartenslot des DWIN-Displays einsetzen.
3. Display wieder einschalten.
4. Das Display erkennt **DWIN_SET** automatisch und startet das Update.
5. Während des Updates erscheinen typischerweise ein blauer Bildschirm sowie nacheinander die übertragenen Display-Dateien bzw. Oberflächenbilder.
6. Warten, bis der Updatevorgang vollständig abgeschlossen ist.
7. Display wieder ausschalten.
8. SD-Speicherkarte entfernen.
9. Display wieder zusammenbauen und normal einschalten.

> **Wichtig:** Während des Updates die Stromversorgung nicht unterbrechen und die SD-Speicherkarte nicht entfernen.

Nach dem Update kann die Versionsnummer des Displays kontrolliert werden.

Bekannte Display-Versionen für Softwarecode **82400463** sind unter anderem V1.3 und V1.7.

## Mainboard-Firmware aktualisieren

Die Mainboard-Firmware wird **nicht** über die SD-Speicherkarte des Displays aktualisiert.

Für Mainboard-Updates gibt es den **FoxAir Updater**:

[FoxAir Updater auf GitHub](https://github.com/dosordie/FoxAir_updater)

Unter Windows ist die grafische Version der empfohlene Weg. Die vollständige Schritt-für-Schritt-Anleitung steht hier:

[Mainboard-Firmwareupdate mit dem FoxAir Updater unter Windows](https://github.com/dosordie/FoxAir_updater/blob/main/docs/HowTo/firmware_update_windows.md)

Die benötigte Mainboard-Firmware wird **nicht öffentlich im Repository bereitgestellt**.  
Die Firmware kann **bei mir per PN** angefragt werden.

> **Wichtig:** Ein Mainboard-Firmwareupdate erfolgt auf eigenes Risiko. Wärmepumpe und LTE-Modem während des laufenden Updates nicht stromlos machen.
