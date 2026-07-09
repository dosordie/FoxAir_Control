# FoxAir / Phnix Control PUBLIC V0.5.52

<p align="center">
  <img src="app_icon.png" alt="FoxAir / Phnix Control Logo" width="160">
</p>

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.

> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern oder Cloud-Werten kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.

### Warmlink RAW / Firmware-Logging

Ab Version `0.5.51` enthält FoxAir Control einen Expertenmodus für den passiven Warmlink RAW Langzeit-Capture.  
Damit können RX/TX-Rohdaten des Modbus-Warmlink/LTE-Datenstroms als Binärdateien gespeichert und über `events.jsonl` sowie `frame_complete` Events für spätere Offline-Analysen indexiert werden.

Die Funktion ist für Diagnose und spätere Firmware-Update-Erkennung vorbereitet:
- passive Beobachtung von Register `2104 / Hauptsoftwareversion`
- Erkennung vollständiger Warmlink-/Modbus-Frames mit Offsets in die RAW-Dateien
- robuste Segmentierung für Langzeitmitschnitte
- keine aktive Firmware-, Replay- oder Schreibfunktion

RAW-Captures können sensible Geräte-/Betriebsdaten enthalten und sollten nicht öffentlich geteilt werden.

## PUBLIC V0.2.46 – Struktur-Refactoring

Diese Public-Version behält das Verhalten aus V0.2.45 bei und räumt die Projektstruktur auf:

- Cloud-Login mit gespeicherter E-Mail und Passwort im OS-Keyring (`keyring>=25.0`)
- Cloud-Geräte-/Device-ID-Anzeige
- Cloud-Polling, Overlay und Cloud-Spalten im Hauptfenster
- Cloud-Wertefinder
- Cloud-Schreibtest mit bestätigtem Endpunkt `app/device/control?lang=en`
- Rechtsklick **Wert per Cloud schreiben ...** für bekannte schreibbare Cloud-Codes
- **Cloud-only Zeilen** gibt es nur im WarmLink-Cloud-Fenster; dort ist der Schalter standardmäßig aktiviert
- Log-Spam-Reduktion für stark wiederholte Display-Bus-Frames bleibt aktiv
- Runtime-Code ist in `core/`, `workers/`, `cloud/`, `dialogs/`, `ui/` und `data/` gegliedert


## Screenshots

![FoxAir / Phnix Control Hauptfenster](docs/screenshots/Screenshot%20Fox_main.png)

![FoxAir / Phnix Control Hauptfenster mit erweiterten Werten](docs/screenshots/Screenshot%20Fox_main2.png)

![FoxAir / Phnix Control Cloud-Ansicht](docs/screenshots/Screenshot%20Fox_cloud.png)

![FoxAir / Phnix Control Steuerung](docs/screenshots/Screenshot%20Fox_control.png)

![FoxAir / Phnix Control Timer](docs/screenshots/Screenshot%20Fox_timer.png)

![FoxAir / Phnix Control AT-Kompensation](docs/screenshots/Screenshot%20Fox_AT.png)

![FoxAir / Phnix Control Einstellungen](docs/screenshots/Screenshot%20Fox_settings.png)

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- WarmLink/Linked-Go Cloud: Login, Geräteübersicht, Statuswerte, Overlay, Wertefinder und Schreiben bekannter Cloud-Codes
- Lesen und Schreiben per Modbus Standart, Modbus Display und Modbus Warmlink LTE
- TCP/IP/ser2net oder USB-RS485/COM-Port
- F1 Hilfe/About mit Version, GitHub-Link und Update-Prüfung
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder
