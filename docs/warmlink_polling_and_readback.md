# WarmLink: responsives Cloud-Polling und Warmlink-FC03

Ausgangspunkt ist der `work`-Stand nach PR #161 (`915da1b`). Die dortigen
Unit-/Range-Regeln, Cloud-Single-Reads und Cloud-/Modbus-Skalierungen bleiben
bestehen.

## Befund zur GUI

Die HTTP-Abfragen liefen bereits außerhalb des GUI-Threads. Im GUI-Thread
lagen jedoch Passwort-/Token-Keyring-Aufrufe, Token-Speicherung nach Polls,
Settings-Speicherung beim Overlay sowie komplette Neubauten von Daten-,
Compare- und Finder-Ansichten. Der Daten-Refresh erzeugte für jede Zeile neue
Items und maß alle Spalten erneut aus. Dazu kam eine Neuberechnung der
Namensspaltenbreite für jede neue Cloud-Zeile im Hauptfenster.

Das sind im Quellcode belegte Blockierungsquellen. Der Windows-„keine
Rückmeldung“-Fall wurde hier nicht auf einem Windows-System reproduziert.
Die 20–25 Sekunden für den bisherigen Vollpoll sind außerdem Netzwerkzeit;
sie müssen die GUI nicht blockieren.

Jetzt laden Worker die Zugangsdaten. Keyring-Schreib-/Löschaufgaben laufen
seriell in einem separaten Executor; ihre Ergebnisse erreichen die GUI über
Qt-Signale. Die UI verwendet nur Zugangsdaten aus dem Arbeitsspeicher.
Wiederholte unveränderte Token werden nicht erneut gespeichert.

Teilupdates ändern vorhandene Items, lassen statische Zeilen und deren
Zeitstempel stehen und bauen keine vollständige Tabelle neu auf. Größere
Daten-/Overlay-Updates werden in Batches von maximal 40 Zeilen mit Qt-Timern
verarbeitet. Haupttabelle und Datenansicht messen Spalten nur bei
Strukturänderungen aus. Der Poll speichert keine Settings mehr.
Compare/Finder werden als dirty markiert und erst bei sichtbarem Tab bzw.
expliziter Aktion aktualisiert. Compare-Items werden ebenfalls wiederverwendet.

## Initialscan und Livepoll

Die Klassifikation verwendet `resolve_cloud_register()` und ausschließlich
bestätigte Mappings des aktuellen lokalen Registerbestands:

| Gruppe | Regel | Aktualisierung |
| --- | --- | --- |
| Live | bestätigtes Register 2000–2999 | zyklisch, standardmäßig alle 30 s |
| Statisch | bestätigtes Register 1000–1999 | initial, Einzelread, Schreib-Readback oder manuelles Nachladen |
| Other | kein bestätigtes Mapping oder Register außerhalb dieser Gruppen | initial; danach gecacht |

Explizit autorisierte Ausnahme: Die zehn Cloud-Live-Wörter `Fault1` bis
`Fault10` werden ebenfalls zyklisch gelesen. Ihre Modbus-Mapping-Confidence
bleibt **candidate**. Es gibt keine Klassifikation anhand eines Code-Präfixes.
Raw-Fault-Werte benötigen keine Fault-History-Abfrage.

Der aktuelle Katalog enthält **420 Kandidaten**: **214 statisch**, **58 live**
(48 bestätigte Registermappings plus zehn Raw-Fault-Wörter) und **148 other**.
Das sind Katalogzahlen. Wie viele davon das konkrete Gerät unterstützt,
entscheidet erst seine Cloud-Antwort. Danach meldet das Log die tatsächlichen
Zahlen und cached `supported_codes`, `live_codes`, `static_codes`, `other_codes`.
Nicht unterstützte Kandidaten werden bei Folgepolls nicht erneut getestet.

Die 48 bestätigten Livecodes sind:

```text
O01~023 O15 O17 S01~S10
T01 T02 T03 T04 T05 T06 T07 T08 T09 T10 T11 T12 T15
T27 T28 T29 T30 T31 T32 T33 T34 T35 T36 T37 T38 T39 T40
T41 T42 T43 T44 T46 T47 T48
SG Status, ModeState, code_version, MainBoard Version, InputCurrent1,
2029, 2030, 2031, 2014, 2146
```

Dazu kommen `Fault1` bis `Fault10`, soweit vom Gerät unterstützt.

Ein Livepoll liefert nur seine aktualisierten Codes. `CloudSession.merge()`
und die Dialog-UI erhalten alle anderen Werte samt letztem Abrufzeitpunkt.
Fehlende Werte ersetzen keinen letzten gültigen Wert, sondern markieren ihn
als stale. Metadaten bleiben Teil der jeweiligen Zeile; Unit-/Range-Prioritäten
aus PR #161 gelten weiter. Ein Fehler im Livepoll markiert die betroffenen
Livewerte veraltet, ohne statische Grenzen oder Werte neu zu erfinden.

Das Liveintervall ist im Dialog von **10 bis 3600 s** einstellbar. Bestehende
zulässige Einstellungen bleiben erhalten. Es gibt keinen zyklischen Vollpoll
der Konfigurationsgruppe. `getDeviceStatus` läuft beim Initial-/Livepoll;
Konfigurationsnachladen ruft weder Status noch House-/Device-Discovery ab.
Fault-History wird nicht automatisch bei jedem Poll angefordert.

## Session und Bedienung

Eine erfolgreiche Geräteabfrage validiert die Session. Stop/Start mit gleichem
Account, gültigem Token und validiertem Gerät verwendet die Device-Liste und
den Code-Cache wieder. Token bleiben in der laufenden Session nutzbar, auch
wenn keine Keyring-Speicherung aktiviert ist.

Discovery findet beim ersten Start, Account-/Geräte-/Zugangsdatenwechsel,
fehlender gültiger Session, Geräte-/Zugriffsfehler oder über **Geräte neu
suchen** statt. Ein erneuerter Login invalidiert den Konfigurationssnapshot
und löst erneut einen Initialscan aus. Ein vorübergehender Poll-Timeout
verwirft die Discovery nicht. Gerätedaten verschiedener Sessions werden nicht
vermischt; alte Cloud-only-Zeilen werden beim Quellenwechsel entfernt, lokale
Modbus-Werte bleiben erhalten.

**Konfigurationswerte neu laden** verwendet nur die unterstützten statischen
Codes. Während Polling läuft, weckt der Button den Worker für diesen Abruf.
Einzelreads und Cloud-Schreib-Readbacks aktualisieren außerdem den Dialogcache
und das Overlay; eine parallele spätere Live-Snapshot-Mitteilung setzt einen
neueren statischen Wert nicht zurück.

Die nicht modale Fortschrittsleiste zeigt technische Startphasen
`CONNECTING`, `LOADING_TOKEN`, `DISCOVERING`, anschließend
`READING_INITIAL`/`READING_STATIC`/`READING_LIVE`. Login ist unbestimmt,
House-Fortschritt und Code-Batches zeigen Zähler. Nach dem Initialscan wird
die Zahl unterstützter Werte angezeigt. Stop wird über Thread-Events
angefordert; nach dem laufenden OS-/HTTP-Aufruf folgt kein weiterer Batch.
Es gibt keine Sleeps oder `processEvents()` im Cloud-GUI-Pollpfad.
Ausblenden lässt Polling im Hintergrund weiterlaufen.

Der Hauptbutton wird zentral über `set_cloud_ui_state()` gestaltet:

| Zustand | Darstellung |
| --- | --- |
| DISCONNECTED | grau |
| CONNECTING | orange; Aufbau/erneuter Abruf |
| CONNECTED | grün |
| POLLING | grün mit zusätzlichem Aktivindikator |
| ERROR | rot bei tatsächlichem Verbindungs-/Authentifizierungsfehler |

Der Tooltip zeigt Verbindungsstatus, Polling, Gerätename und letzten
erfolgreichen Abruf. Device-Code, Seriennummer und andere IDs erscheinen
nicht. Ein einzelner temporärer Poll-Timeout setzt CONNECTING/Retry; ein
folgender Erfolg setzt wieder POLLING. Stop lässt eine gültige Verbindung
als CONNECTED bestehen. Hauptfenster-Schließen wartet per Signal auf das
Ende des Cloud-Pollworkers, ohne den GUI-Thread synchron zu blockieren.

## Warmlink-FC03 und Quickwrite

Bisher wurden Pending-Einträge schon beim Enqueue angelegt. `ReaderWorker`
konnte mehrere FC03-Requests aus der gemeinsamen Queue senden. Eine
FC03-Antwort enthält keine Startadresse; gleicher Slave und gleiche Wortzahl
reichten deshalb zur Zuordnung irgendeines offenen Pending-Reads.
Ein identischer alter Pending-Eintrag unterdrückte zudem legitime Readbacks.
Die Timeout-Uhr lief schon während der Wartezeit in der Sendewarteschlange.

Für `warmlink_raw` verwenden Hauptfenster, Quickwrite, manuelles
Lesen/Schreiben, Dialoge, Hintergrundpoll und Init nun den zentralen
`WarmlinkRequestScheduler`:

1. Genau ein Read darf in-flight sein. Weitere Reads bleiben im Scheduler.
2. `ReaderWorker.read_sent` startet die **5-s-Timeout-Uhr erst nach dem TX**.
3. Nur der aktive, tatsächlich gesendete Request wird über Slave und
   ByteCount zugeordnet; seine bekannte Startadresse wird normal dekodiert.
4. Antwort oder Timeout beendet den Request. Der nächste Dispatch erfolgt
   über einen Qt-Timer, nach Abschluss der aktuellen Frame-Verarbeitung.
5. Nach Timeout gibt es eine **500-ms-Ruhephase** für späte Antworten.
   Nicht zuordenbare FC03-Antworten innerhalb dieser Phase verlängern sie.
   Da RTU-FC03 keine Transaktions-ID trägt, kann eine beliebig stark verspätete
   Antwort nach einer neuen Übertragung grundsätzlich nicht sicher erkannt
   werden; die Ruhephase reduziert dieses Protokollrisiko.
6. Disconnect/Firmware-Capture cancelt den Scheduler; Sendefehler lassen
   keinen Request ohne Deadline dauerhaft aktiv.

Priorität: **Readback → manueller Einzelread/Quickwrite → Dialogread →
Hintergrundpoll → Init**. Ein laufender Read wird nicht abgebrochen. Nach
seiner Antwort kommt der priorisierte Readback vor den weiteren
Hintergrundreads. Queued identische alte Reads werden ersetzt; eine ältere
in-flight-Anfrage bleibt bis zu ihrer Antwort/ihrem Timeout aktiv, danach
folgt der frische Readback. Legacy-Pending-Einträge können den neuen Read
nicht unterdrücken oder seine Antwort übernehmen.

Nach adressgenauem FC16-ACK erzeugt Quickwrite einen Readback mit der benannten
Konstante `WARMLINK_READBACK_DELAY_MS = 200`. Der Scheduler reserviert den
nächsten Read-Slot während dieser Pause. R02 bleibt ein gewöhnlicher
Registerfall: Cloud 55 bedeutet 55 °C; lokal 550 ebenfalls 55 °C;
Cloud-Write 52 sendet `"52"`, Modbus-Write 52 sendet 520.

Die Wertverarbeitung bleibt im bestehenden Framepfad: `latest_regs`, Tabelle,
Decoder und offene Dialoge erhalten den dekodierten Wert. Die Standard- und
Display-Modbus-Pending-/Snapshot-Pfade bleiben erhalten. Der besondere
Register-4-MQTT-Trigger wird im Warmlink-Scheduler transportiert, erwartet
aber weiterhin keine normale Read-Response.

## Validierung

`tests/test_cloud_polling.py` prüft Gruppen, Teilupdates, Session-Wiederverwendung,
Rediscovery, manuelles Nachladen, Token-Erneuerung, Batch-Fortschritt,
Qt-Heartbeat bei langsamem Keyring, nicht modale Progresszustände, zentrale
Buttonzustände, inkrementelle Items und Quellenwechsel.

`tests/test_warmlink_request_scheduler.py` verwendet echte FC03-/FC16-Frames,
den echten `ReaderWorker`-Sendepfad und die normale Hauptfenster-Dekodierung.
Prüffälle: zwei qty=1-Reads, richtige Adresszuordnung, Readback-Priorität,
Stale-Pending, 200-ms-Pause, tatsächlicher TX als Timeoutbeginn, späte Antwort
während Timeout-Ruhephase, Sendefehler, Quickwrite-Einzelread,
Write→ACK→FC03 sowie unveränderter Standard-Modbus-Pfad.

Der lokale Benchmark ist ohne Cloud-/Busverkehr reproduzierbar:

```bash
python tools/benchmark_cloud_tables.py --baseline 915da1b
```

Bei 420 Zeilen, fünf Läufen und 58 geänderten Livecodes ergab er hier im
Median **686 ms** für den früheren vollständigen Daten-Refresh und **56 ms**
für das neue Live-Update; der größte einzelne neue GUI-Batch lag im Median
bei **48 ms**. Gemessen wird die Datenansicht, nicht die gesamte Windows-GUI
oder Cloud-Latenz. Die Zahlen sind keine plattformübergreifende Zeitgarantie.

Ein realer Windows-/Wärmepumpentest steht noch aus. Mock-/Protokolltests
belegen die Read-/ACK-Zuordnung und Skalierung, nicht die tatsächliche
Antwortlatenz eines konkreten LTE-Modems.

Abschlussprüfung: `python -m pytest -q` — **389 bestanden**;
`python -m compileall -q .` und `git diff --check` erfolgreich.
Der Metadaten-Audit meldet weiterhin keine belegten Unit-/Range-Konflikte.
