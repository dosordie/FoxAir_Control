# Warmlink RAW Langzeit-Capture

## Zweck
Der Warmlink RAW Langzeit-Capture ist eine Experten-/Sonderfunktion, um über lange Zeiträume den rohen Warmlink-/Modbus-TCP-Byte-Strom mitzuschneiden. Da das LTE-Modem über den Modbus mit dem WP-Mainboard verbunden ist, ist der Warmlink-Modbus-Datenstrom der zentrale Ort, um mögliche Firmware-Update-Übertragungen oder Update-Handshakes zu beobachten. Der Langzeit-Capture speichert deshalb den rohen Byte-Strom unabhängig davon, ob die App die Daten bereits interpretieren kann.

Es wird **keine** Firmware-Update-, Replay- oder Schreibfunktion implementiert. Der Capture ist passiv.

## Aktivierung
Die Funktion befindet sich in `Programm-Einstellungen` im Expertenbereich `Warmlink RAW Langzeit-Capture`. Dort können RX/TX-Binärdateien, Events/Index, Rotation, Größenlimits, Aufbewahrung und Anomalie-Erkennung konfiguriert werden.

## Dateiformate
Pro Segment werden Dateien nach folgendem Schema erzeugt:

- `warmlink_capture_YYYY-MM-DD_NNN.rx.bin`: rohe vom Socket empfangene Bytes.
- `warmlink_capture_YYYY-MM-DD_NNN.tx.bin`: rohe an den Socket gesendete Bytes.
- `warmlink_capture_YYYY-MM-DD_NNN.events.jsonl`: JSON-Lines mit Chunk-, Frame- und Anomalie-Metadaten.
- `warmlink_capture_YYYY-MM-DD_NNN.summary.txt`: Segment-Zusammenfassung.
- `warmlink_capture_YYYY-MM-DD_NNN.UPDATE_DETECTED.txt`: Marker, falls Register 2104 geändert wurde.

Die `.bin`-Dateien sind echte Binärdateien, kein Hex-Text. `events.jsonl` ist nur ein Hilfsindex/Kommentarstrom; Quelle der Wahrheit bleiben RX/TX-Binärdateien. Chunk-Metadaten in `events.jsonl` basieren auf TCP-Chunks. Zusätzlich schreibt der Capture schlanke `frame_complete`-Events für vollständig und plausibel erkannte Modbus-/Warmlink-Frames mit Dateioffsets, Funktionscode, Registeradresse, Payloadbereich und CRC-Status. Die Frame-Events sind nur ein Analyseindex; Quelle der Wahrheit bleiben RX/TX-Binärdateien.

## Rotation und Limits
Tagessegmente werden mit `_001`, `_002`, ... nummeriert. Ein neues Segment kann manuell gestartet werden. Die Größenbegrenzung pro Einzeldatei startet sofort ein neues Segment. Die konfigurierte Tagesrotation nach Inaktivität ist für lange Captures vorgesehen, damit nicht mitten in einer Übertragung rotiert wird.

Maximaler Gesamtspeicher und Aufbewahrungstage dienen dazu, alte abgeschlossene Segmente zu entfernen bzw. den Capture bei nicht auflösbaren Limits sicher zu stoppen. Aktive Segmente dürfen nicht gelöscht werden.

## Anomalien und Firmware-Verdacht
Stufe 1 markiert einfache Heuristiken, z. B. unbekannte Funktionscodes, ungewöhnlich große RX-Datenmengen, viele FC16-/Write-Multiple-Register-Frames, fortlaufende Adressen oder unbekannte Datenfolgen. `unknown_function` bedeutet nur dann auffällig, wenn ein plausibler neuer Frame mit erwarteter Busadresse, aber unbekanntem Function Code erkannt wurde. Partial-, Chunk- und Continuation-Daten großer Warmlink-Statusblöcke werden nicht als `unknown_function` gewertet. Normale FC16-Statusblöcke wie `0x0443`, `0x07D1` und `0x082B` mit 90 Registern gelten nicht als Firmware-Verdacht. Im normalen GUI-Log erscheinen nur kurze Statuszeilen, keine Rohdaten.

## Firmware-/Update-Watch Register 2104
Register `2104 / 0x0838` ist als Hauptsoftwareversion bekannt. Eine Änderung von Register 2104 gilt als starkes Indiz für ein abgeschlossenes oder laufendes Firmwareupdate. Ob der Wert numerisch höher wird, hängt vom Versionsformat ab; daher wird jede Änderung erfasst.

Events:

- `firmware_version_seen`: Baseline beim ersten Erfassen.
- `firmware_version_changed`: Wert oder Anzeige hat sich geändert.
- `firmware_version_increased`: numerisch sicher höherer Rohwert.
- `firmware_update_suspected`: kann mit Datenburst-/FC16-/Reconnect-Anomalien korreliert werden.

Register 2104 wird nicht aktiv gepollt. Die App erkennt Änderungen passiv, sobald 2104 im normalen Warmlink-Datenstrom auftaucht.

## Datenschutz
RAW-Captures können Device-IDs, Tokens, Betriebsdaten oder andere sensible Informationen enthalten. Nicht öffentlich hochladen und nur gezielt mit vertrauenswürdigen Personen teilen.

## Offline-Analyse
`tools/analyze_warmlink_capture.py` liest `events.jsonl` und fasst Zeitraum, RX/TX-Bytes, Frames nach Typ, unbekannte Frames, Anomalien, RX-Bursts und Reconnects zusammen.

## GUI-Statusmeldungen und Vollständigkeit
Capture-Logmeldungen im normalen GUI-Log sind ausschließlich kurze Statusmeldungen wie Start, Stop, Segmentwechsel, Anomalie, Speicherlimit, Schreibfehler oder eine Änderung von Register 2104. Rohdaten werden dort nicht ausgegeben; die vollständigen Bytes liegen nur in den RX/TX-Binärdateien.

Wenn `capture_drop` in `events.jsonl` erscheint oder der Drop-Zähler im Status/Summary größer als 0 ist, ist der Capture ab diesem Zeitpunkt möglicherweise nicht mehr vollständig. Ursache ist eine volle Capture-Queue; die normale Wärmepumpen-Kommunikation wird dann bewusst nicht blockiert, damit die App weiterläuft.

## Passive 2104-Erkennung
Register 2104 wird nicht aktiv gepollt. Die App erkennt Änderungen passiv, sobald 2104 im normalen Warmlink-Datenstrom auftaucht.
