## Unreleased

### Geräte-Info
- Neuer eigenständiger, nicht blockierender Geräte-Info-Dialog neben dem About-Button.
- Read-only Register-4-Sonderabfrage ohne falschen generischen FC03-Timeout; Fortschritt über acht eindeutige Datenblöcke und 90-Sekunden-Teilabschluss.
- Gemeinsame Decoder für WiFi-ID und Datum, PHNIX/Aliyun ProductKey, C544-Hardware-/Softwareinformation sowie C37B-Quittung.
- Geräteidentität aus dem About-Dialog entfernt und fest codierte reale Gerätekennung durch strukturelle Prüfung ersetzt.
- Register 200–215, 50043–50044 und 50500–50512 vollständig beschriftet.

## 0.5.51

### Highlights
- Neuer Warmlink RAW Langzeit-Capture für den Modbus-Warmlink/LTE-Datenstrom.
- Passives Firmware-/Update-Logging vorbereitet, ohne Schreib- oder Replay-Funktion.
- Frame-Complete-Index für spätere Offline-Analyse vollständiger Warmlink-/Modbus-Frames.
- Robusteres Segment-Handling: neue Captures hängen nicht mehr an alte Tagessegmente an.

### Warmlink RAW / Firmware-Logging
- RX/TX-Rohdaten werden verlustarm als echte Binärdateien `.rx.bin` / `.tx.bin` gespeichert.
- `events.jsonl` dient als Hilfsindex mit Chunk-, Status-, Anomalie- und Firmware-Events.
- Neue `frame_complete` Events indexieren vollständig erkannte Frames mit:
  - Richtung RX/TX
  - Dateiname
  - Offset-Start/Ende
  - Länge
  - Bus/Function-Code
  - Registeradresse/Menge
  - Payloadbereich, soweit sicher bestimmbar
  - CRC-Status
- Register `2104 / Hauptsoftwareversion` wird passiv beobachtet.
- Aktives zyklisches 2104-Polling wurde wieder entfernt, weil der Wert im normalen Warmlink-Datenstrom auftaucht.
- Änderungen von 2104 erzeugen Firmware-Version-Events und optional eine `UPDATE_DETECTED` Markerdatei.
- Normale Statusblöcke wie `0x0443`, `0x07D1` und `0x082B` mit 90 Registern werden nicht mehr fälschlich als Firmware-Verdacht gewertet.
- TCP-Continuation-Chunks werden nicht mehr als neue Frames bzw. falsche `unknown_function`-Anomalien gewertet.

### Segmentierung / Langzeitbetrieb
- Jeder Capture-Start erzeugt ein neues freies Segment.
- Wenn `_001` bereits existiert, wird automatisch `_002`, `_003`, usw. verwendet.
- Offsets in `events.jsonl` und `frame_complete` beziehen sich eindeutig auf die zugehörige `.rx.bin`/`.tx.bin`.
- Queue-Drops werden in Events/Summary dokumentiert.
- Summary enthält Drop-Status und Firmware-Verdacht.

### UI / Einstellungen
- Programmeinstellungen können auch bei aktiver Verbindung geöffnet werden.
- Live-Kommunikationsparameter sind bei aktiver Verbindung gesperrt.
- Warmlink-Capture-Optionen bleiben bei aktiver Warmlink-Verbindung bedienbar.
- Capture-/Logger-Einstellungen sind nur für den Warmlink-Modbus/LTE-Stream vorgesehen.

### Hinweise
- Der Capture ist rein passiv.
- Es gibt keine Firmware-Schreib-, Replay- oder Update-Funktion.
- RAW-Captures können sensible Daten enthalten und sollten nicht öffentlich geteilt werden.

## PUBLIC V0.2.46

- Version auf **0.2.46** angehoben; `APP_EDITION` bleibt **PUBLIC**.
- Projektstruktur aufgeräumt: Core, Cloud, Worker, Dialoge, UI-Helfer und JSON-Daten liegen jetzt in eigenen Ordnern.
- WarmLink-Cloud/LTE-Fenster aus `foxair_phnix_control.py` nach `dialogs/cloud_dialog.py` ausgelagert.
- Pfad-/Resource-Helfer nach `ui/paths.py` und kleine UI-Konstanten nach `ui/theme.py` ausgelagert.
- JSON-Register-/Knowledge-Dateien nach `data/` verschoben und Build-Pfade angepasst.
- Dev-/Experimentierwerkzeuge nach `devtools/` verschoben; sie werden nicht als Runtime-Daten in den PyInstaller-Build gepackt.
- Verhalten aus PUBLIC V0.2.45 bleibt erhalten: Cloud-only-Schalter nur im Cloud-Fenster, dort standardmäßig aktiv; keyring bleibt Pflicht-Abhängigkeit; Cloud-Schreibformat unverändert.

## PUBLIC V0.2.45

- Cloud-only-Zeilen-Schalter aus dem Hauptfenster entfernt.
- Cloud-only-Zeilen bleiben im WarmLink-Cloud-Fenster und sind dort standardmäßig aktiviert.
- `keyring>=25.0` bleibt Pflicht-Abhängigkeit.
- PyInstaller-Build sammelt `keyring`/Windows-Keyring-Abhängigkeiten ein.

## PUBLIC V0.2.44

- Public-Build mit WarmLink/Linked-Go-Cloud-Funktionen erstellt; `APP_EDITION` ist **PUBLIC**.
- Enthält Cloud-Login, Geräte-/Device-ID-Anzeige, Cloud-Polling, Cloud-Overlay, Cloud-Wertefinder und Cloud-Schreibtest.
- Cloud-Schreiben nutzt das bestätigte Format: `app/device/control?lang=en` mit `appId="16"` und `param: [{deviceCode, protocolCode, value}]`.
- Hauptfenster: Rechtsklick **Wert per Cloud schreiben ...** für bekannte schreibbare Cloud-Codes.
- Log-Spam im Backend **Modbus Display** reduziert.
