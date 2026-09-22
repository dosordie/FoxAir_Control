# Firmware-Versionen, Changelog und Display-Update

Bei der FoxAir gibt es mehrere voneinander unabhängige Firmware-Versionen.

Das ist wichtig, weil zum Beispiel **Display V1.7 nicht Mainboard V1.7** bedeutet.

## Welche Firmware gibt es?

| Komponente | Typischer Softwarecode | Beispiele |
| --- | --- | --- |
| Mainboard / Hauptsteuerung | 82400644 | V1.2, V1.3, V3.3, V3.4, V3.5 |
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

### V3.5

V3.5 ist inzwischen als **`82400644 / 0035`** bestätigt. Die untersuchte Firmware stammt von einer **FoxAir BlueLine (BL)**, gehört aber zur selben `82400644`-Mainboard-Firmwarelinie wie die entsprechenden **GreenLine-/GL-Geräte**.

Wichtige Erkenntnisse gegenüber V3.4:

- die bekannte Grundregelung, SG-/PV-State-Machine, externe-AT-Umschaltung und Pumpenregelung bleiben grundsätzlich erhalten
- V3.5 ergänzt spezialisierte Warmlink-Remoteeingänge **8021–8028** für Kompressor-Frequenzgrenzen sowie Heiz-/Kühl-/Warmwasser- und Zonen-Sollwertkorrekturen
- **8055** ist ein zusätzlicher skalierter Sollwert-Modulationskanal für bestimmte Multi-Zone-T-Betriebsarten
- **MAIN 1540** aktiviert einen zusätzlichen adaptiven Inverter-/Leistungsregelpfad mit zeitlich gültigen Korrekturwerten und einem sichtbaren 6-Hz-Frequenzraster
- die in der App angebotene Funktion **AI Saving / dynamischer Stromtarif ist nicht ausschließlich eine V3.5-Funktion**: der grundlegende Remote-Energy-Control-/8001-/8004-Regelkomplex ist bereits in V3.4 vorhanden; V3.5 erweitert ihn

Die Bezeichnung **AI** sollte technisch mit Vorsicht verwendet werden: Eine Cloud-/Remote-Regelung ist durch die Kommunikationspfade gut gestützt, ein tatsächlicher Machine-Learning-/AI-Algorithmus ist aus der Mainboard-Firmware nicht bewiesen.

> **BlueLine / GreenLine:** Die Bezeichnungen BL und GL bedeuten hier keine getrennten Firmwarezweige. Bei Geräten mit Mainboard-Softwarecode **`82400644`** wird dieselbe Mainboard-Firmwarelinie verwendet. Die vorliegende V3.5 aus einer BlueLine ist deshalb auch für entsprechende GreenLine-/GL-Geräte dieser `82400644`-Familie kompatibel – und umgekehrt. Bei einem unbekannten Modell sollte der Mainboard-Softwarecode vor einem Update trotzdem geprüft werden.
>
> **Update-Hinweis:** Der FoxAir Updater hat reale Firmwarewechsel bis V3.4 erfolgreich durchgeführt. Ein kompletter Updatevorgang **auf oder von V3.5** ist dort aktuell noch nicht real validiert.  

Eine ausführlichere technische Übersicht gibt es hier:

[FoxAir / PHNIX Firmware-Übersicht](../firmware_overview.md)

## Display-Firmware aktualisieren

Die Display-Firmware ist unabhängig von der Mainboard-Firmware.

Das kleine DWIN-Display wird **direkt über eine SD-Speicherkarte** aktualisiert. Dafür ist keine Verbindung zu FoxAir Control, Modbus oder zur Cloud notwendig.

### Empfehlung bei Mainboard-Firmware V3.3 oder neuer

Wer das Mainboard auf **V3.3, V3.4 oder V3.5** aktualisiert, sollte nach Möglichkeit auch das kleine DWIN-Display auf die aktuell bekannte **Display-Firmware V1.7** aktualisieren.

Der Grund: Eine ältere Display-Firmware kennt neu hinzugekommene Mainboard-Funktionen nicht und kann diese deshalb weder sinnvoll anzeigen noch konfigurieren.

Ein praktisches Beispiel aus dem Forum war die Kombination:

```text
Mainboard V3.5
Display V1.3
```

Die WarmLink-App zeigte dabei bereits neue Funktionen der V3.x-Mainboard-Firmware, während das ältere Display diese Funktionen nicht kannte.

Besonders betroffen sind mindestens:

- **Leistungs-/Power-Timer**
- **SG-Ready-/PV-Funktionen**
- weitere Parameter und Funktionen, die erst mit der V3.x-Mainboard-Firmware hinzugekommen sind

Daher als Empfehlung:

> **Ab Mainboard-Firmware V3.3 sollte möglichst Display-Firmware V1.7 verwendet werden.**

Das ist keine harte technische Mindestanforderung – die Wärmepumpe kann auch mit einer älteren Display-Firmware grundsätzlich weiterlaufen. Das Display bildet dann aber möglicherweise nur einen älteren Funktionsumfang ab, obwohl das Mainboard bereits mehr Funktionen unterstützt.

Hintergrund aus dem Forum:

[Erfahrungsbericht: Mainboard V3.5 mit Display V1.3](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?postID=4884291#post4884291)

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
