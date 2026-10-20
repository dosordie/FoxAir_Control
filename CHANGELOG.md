## Unreleased

- GL9 V3.5: direkte Engineering-RAM-Register 8802–8808 ergänzt; signed int16,
  8802–8804 mit /10 °C, übrige Einheiten offen. Standardmäßig Engineering-Ansicht;
  Korrekturquellenwahl über 1334/1540 und flüchtige Werte dokumentiert.
- Effektiver Heiz-Wassersollwert auf MAIN:2017 korrigiert (V3.5+, FC03, TEMP1);
  ungültigen Alias 1557 entfernt. 2014/2016 als Spiegel derselben Quelle und
  2013 als eigenes internes Feld präzisiert. Keine neuen Cloud-/Display-Mappings.

- Cloud-Schnellverbindung als kompakter SVG-Iconbutton: Wolke mit grünem Stecker
  zum Verbinden bzw. rotem getrennten Stecker zum Trennen. Tooltips, zugängliche
  Zustandsbeschriftung und deaktivierte Übergänge bleiben erhalten.

- Hauptfenster: kompakter Cloud-Verbinden/Trennen-Button direkt neben dem
  animierten Statusbutton. Gespeicherter Zugang und Geräteauswahl nutzen den
  vorhandenen Cloud-Worker; bei fehlendem Zugang öffnet sich der Cloud-Dialog.
  Manuelles Trennen deaktiviert die Sitzung, sperrt neue Aufträge und wartet auf
  geordnetes Worker-Cleanup. Zugangsdaten, Tokens und Autostart bleiben gespeichert.
- Kombinierter WP-Ein/Aus-/Silent-Timer: einstellbare Schreibpause, Raw-Eingaben
  und „live aktualisieren“ entfernt. Lokale Writes verwenden fest 1.200 ms;
  Partner-Bytes werden intern erhalten. Automatischer Initialread und manuelles
  Neuladen bleiben verfügbar; lokale wie Cloud-Updates schützen offene Eingaben.
  KG-Codes, Cloud-Freigaben, ACK-/Readback- und Display-Sequenzen bleiben unverändert.

- Cloud WP Ein/Aus Timer: wieder vollständiger kombinierter Dialog mit Timer 1–6 und Silentmodus statt Silent-Umleitung. KG1–KG12 und KG13~KG28 / KG29~KG44 / KG45~KG60 den MAIN-Registern 1256–1270 zugeordnet; ganze HH:MM-/Tagesmasken, nur geänderte Werte, frische Readbacks und Schutz des Partner-Bytes. Cloud-Schreibpfad neu und noch nicht live bestätigt.
- Cloud-Mapping-Inventar um M-/W-/DP-Kandidaten ergänzt; keine neuen Schreibfreigaben außerhalb der 15 KG-Timer-Register.

- Kontaktdecoder (2034 / S01~S10) und Lastausgangsdecoder (2019 / O01~023):
  frischer asynchroner Cloud-Autoload, Jetzt lesen, Polling und korrekte uint16-
  BINARY-/Dezimalwerte. Fehlende/ungültige Werte bleiben unbekannt; beide bleiben read-only.
- Silentmodus-Timer 1244–1249 vollständig über Cloud les- und schreibbar:
  alle sechs Werte gemeinsam laden, nur geänderte Werte per zentralem Batch schreiben,
  gemeinsamer frischer Readback mit Einzelprüfung und Schutz neuerer Eingaben.
  Deaktivierungen zuerst bestätigen, geänderte Zeiten gemeinsam bestätigen,
  Aktivierungen zuletzt. Keine experimentelle Freigabe oder zusätzliche Cloud-Rückfrage.
- Stand von PR #191: Cloud-only leitete den WP-Ein/Aus-Timer zunächst zum Silent-Editor um; im aktuellen Unreleased-Stand ist der kombinierte Editor für Cloud wiederhergestellt.
- Silent-Timer-Cloud-Writes sind neu implementiert und noch nicht live verifiziert.
  Nutzung ist regulär möglich; gegebenenfalls sind Live-Nachbesserungen erforderlich.

- AT-Kompensation: sieben kompakte Eingabefelder, berechnete Werteübersicht,
  kontextabhängiger Kurvenschreibbutton und Schutz ungespeicherter Live-Eingaben.
- Cloud: zentrale Batch-API (`appId: "16"`, `param[]`) mit einem gemeinsamen
  Readback, höchstens drei Leseversuchen, Einzelcode-Ergebnissen und gesondertem
  Status für gesendet / API bestätigt / Readback bestätigt. Kein Write-Replay,
  kein Rollback; Account-I/O ist zwischen Poll-, Snapshot- und CommandWorker serialisiert.
- GL9-Livenachweis vom 17.10.2026: sieben AT-Punkte einzeln und gemeinsam als
  7-fach-Write/-Readback erfolgreich. AT linear, H36 und SG01–SG08 regulär freigegeben;
  experimentelle Checkboxen und zusätzliche Cloud-Schreibbestätigungen entfernt.
- AT schreibt nur geänderte Cloud-Kurvenwerte und bereinigt nur bestätigte Editorversionen.
- SG-Editor: Reihenfolge SG01–SG08, SG08 als Aus/Ein; geänderte SG02–SG08 als Batch.
  Aktivierung SG01 erst nach bestätigtem Parameterbatch; Deaktivierung SG01=0 zuerst.
  Lokale 500-ms-Abstände und Display-Paketsync bleiben erhalten; Status ist read-only,
  8801 bleibt auf direkten Mainboard-Modbus beschränkt.
- Gezielter asynchroner Cloud-Autoload für AT, SG, sichtbare Parameterblöcke und
  Störungsdecoder. Editorentwürfe, Geräte-/Accountkontext und Abbruch bei Schließen geschützt.
- Störungsdecoder liest elf aktuelle Cloudwörter gemeinsam, dekodiert BINARY/Dezimal,
  verwendet Fault1→2081 bis Fault10→2090 und zeigt fehlende Daten ausdrücklich an.
- Cloud-Schreibtest und Wertefinder samt exklusiven Helfern/Threads entfernt;
  bekannte Mapping-Exporte, Cloud ↔ Lokal, SIM und generischer API-Debugger bleiben erhalten.
- LTE: automatische Readbacks mit 800 ms Settle und 12 s Timeout ab tatsächlichem TX;
  ein Deadlinebesitzer. Nach verlorenen FC03-Antworten kontrollierte TCP-Neuverbindung
  nach 2 s Wartephase, maximal drei Versuche (1/2/4 s). Alte Verbindungsgenerationen
  werden verworfen; Scheduler und Hintergrund-Polling laufen auf dem frischen Stream
  weiter. Kein Write-Replay; manueller Abbruch, Capture und App-Ende stoppen die Wiederherstellung.

- Display-Modbus: DWIN-Version/RTC, Anzeigeobjekte und Sichtbarkeitsflags anhand V1.7 präzisiert;
  Unit-1-Telemetrie mit korrekten Skalierungen und eigener virtueller Browsergruppe.
- Display-Parametersynchronisation erfordert alle sechs frischen, gültigen Pflichtpakete;
  Teilstände und fehlende Pakete bleiben sichtbar. MAIN1017 ist kein Logo und wird nicht automatisch restauriert.

- Register-Audit: MAIN2080/2109/2139/2152 mit kompakten aktiven Statusbits,
  ausführlichen Tooltips und eigenen Tabs im System-/I/O-Dialog; RAW/HEX/Binär bleiben verfügbar.
- INV1-Rohwerte 2026–2028 und optionales Frostschutzfeld 2056 präzisiert.
- Bestätigte Cloud-Aliasse T49/T50/T51 ergänzt; Überhitzungen bleiben Kelvin,
  lokale T-Diag-Codes und bisherige Cloud-Zuordnungen erhalten.
- Diagnoseantworten und Timeouts korrigiert; keine zusätzlichen Schreibfreigaben.

## 0.3.4

- WP- und AT-Steuerung nutzen einen gemeinsamen Steuertransport mit **Modbus vor Cloud**.
- Cloud-only: WP Ein/Aus, Modus und Solltemperaturen sowie AT-H36 können über bestätigte WarmLink-Codes gesteuert werden.
- Cloud-Geräte lassen sich per Doppelklick auswählen und das Polling direkt starten.
- Haupttabelle verbessert: Spaltenbreiten sind einstellbar und werden gespeichert; lange Cloud-Werte bleiben kompakt.
- Cloud-Button zeigt aktives Polling mit einem animierten grünen Rahmen.
- **Hauptfenster leeren** entfernt jetzt auch Cloud-Werte, ohne Verbindung oder Polling zu beenden.
- Neuer System-/I/O-Statusdecoder für MAIN 2146/2147; Registerwissen und FAQ aktualisiert.

## 0.2.67

- Warmlink-/Service-Register im 8xxx-Bereich werden bei Empfang oder explizitem Lesen direkt in der normalen Hauptregistertabelle angezeigt.
- Bekannte Werte 8001, 8004, 8006, 8021–8028 und 8055 verwenden dort ihre Reverse-Engineering-Namen und Datentypen; unbekannte 8xxx-Werte bleiben als RAW-Werte sichtbar.
- FC10-Serviceframes aktualisieren die enthaltenen Einzelregister über den normalen Änderungs- und Tabellenpfad, ohne Schreibfreigaben oder automatische Abfragen zu ergänzen.
- Separaten Warmlink-Service-/Engineering-Dialog aus den Programmeinstellungen entfernt.

## 0.2.66

- Verzögerung beim Schließen der Programmeinstellungen behoben.
- Theme, Tabellenfilter, Gerätemodell und Kommunikationsparameter werden nur noch bei tatsächlicher Änderung neu angewendet.
- Mehrfache Settings-Speichervorgänge beim Bestätigen reduziert.

## 0.2.65

- V3.5-Warmlink-Serviceparameter auf den aktuellen Reverse-Engineering-Stand gebracht; 8021–8023 als Cooling-/Heating-/DHW-Frequenzcaps und 8027/8028 mit Heiz-/Kühlvorzeichen dokumentiert.
- 8055 als RAM-only ohne eigenen TTL sowie MAIN:1430/1492 inklusive Persistenz, Byteaufteilung und Gates präzisiert; irreführende harte 6-Hz-Quantisierung entfernt.
- Engineering-Parameter lassen sich optional in den Programmeinstellungen einblenden; neue read-only Service-/Engineering-Diagnose für 8021–8028 und 8055.
- Rollen des internen FoxAir-Boardbusses und des getrennten Warmlink/LTE-Busses im Busadressdialog aktualisiert.


### V3.5 Remote-Regelwertkorrektur
- MAIN:1540 als V3.5+-Gate fuer extern eingespeiste, zeitbegrenzte Warmlink-Korrekturen und MAIN:1557 als effektiven Heiz-Wassersollwert ergaenzt (historische Fehlzuordnung, jetzt auf MAIN:2017 korrigiert); die fruehere adaptive/AI-Arbeitshypothese wurde auf den bestaetigten Remote-Pfad praezisiert.
- Warmlink-Servicewerte 8021–8028 am Slave `0x63` getrennt von den normalen MAIN-Registern dokumentiert, einschließlich gruppenbezogener TTL, Cooling-/Heating-/DHW-Caps und bestätigter Heiz-/Kühlvorzeichen.
- MAIN:1492 und MAIN:1430 als optional sichtbare Engineeringparameter aufgenommen; Warmlink 8055 bleibt in der read-only Diagnose sichtbar und für Schreibzugriffe gesperrt.

### SG Ready / SG01
- SG01/MAIN:1334 um AI Saving / Remote Energy Control (`4`) und die erweiterte SG/PV-Familie `5/6/7` ergänzt.
- SG-Ready-Editor unterstützt alle bekannten SG01-Modi und unterscheidet klassischen Vier-Zustands-Pfad, AI Saving sowie Low/Neutral/High-Pfad.
- Register 8801 wird im Editor nur bei SG01 `3` oder `7` am direkten User-/Mainboard-Modbus angeboten und geschrieben.
- Statische Bestätigung, Live-Verifikation und offene Herstellerbezeichnung der erweiterten Familie sind getrennt dokumentiert.

### Register-Mapping und Schreibschutz
- Offene Erkenntnisse aus #117, #138, #139 und #140 ergänzt: DIAG-Register, Statusbitfelder, Heiz-/Sommerabschaltung, A38-Niederdruckbegrenzer und C13–C15-PID-Regler.
- C14/MAIN:1349 wird zentral unmittelbar vor jedem normalen Register-Write auf mindestens 1 validiert, damit auch manuelles Schreiben und Backup-Restore keinen ungeschützten Divisor 0 an die Firmware übertragen können.
- Unsichere Zählerzuordnungen, Reservepfade und weiterhin offene Bit-/Statussemantik sind ausdrücklich als wahrscheinlich beziehungsweise offen gekennzeichnet.

### Geräte-Info und Registerdaten
- Die drei direkten Geräte-Info-Reads werden mit jeweils einer Sekunde Buspause entzerrt.
- Cloud-Sonderfunktion im Dialog dezent hervorgehoben und oberhalb der direkten Abfrage angeordnet.
- Temperatur-/Feuchtesensor und Taupunkt (2178–2180) sowie die Warmwasser-Energiezähler-Wortpaare (2125–2128) dokumentiert.

## 0.2.61

### Geräte-Info
- Reguläres FC03-Auslesen über 200/1, 2001/8 und C544 50500/13 ergänzt.
- Cloud-Sonderfunktion eindeutig benannt, mit MQTT-Hinweis und Sicherheitsabfrage versehen.
- Wartezeit auf 180 Sekunden erhöht und scrollbare Fortschrittsanzeige stabilisiert.
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
