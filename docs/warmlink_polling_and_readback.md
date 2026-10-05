# WarmLink: responsives Cloud-Polling und Warmlink-FC03

Ausgangspunkt ist der `work`-Stand nach PR #161 und #162 (`f5359e9`). Die dortigen
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

### App-Heartbeat für echte Live-Aktualisierung

Am **05.10.2026** wurde nach dem Reverse Engineering von WarmLink Android
3.0.5 (`DeviceDetail416Activity`, GL9/Softwarefamilie 644) an einer realen
FoxAir GL9 experimentell bestätigt:

```text
app_heartbeat=23205
→ Mainboard-Traffic
→ FC16 ab 1191 (63 10 04 A7 …)
→ vollständiger FC16-Liveblock 2001–2090 (63 10 07 D1 00 5A B4 …)
```

Der dedizierte API-Aufruf `send_app_heartbeat(device_code)` sendet über die
bestehende CRM-Verbindung exakt `POST app/device/control` mit:

```json
{
  "param": [
    {
      "deviceCode": "<deviceCode>",
      "protocolCode": "app_heartbeat",
      "value": "23205"
    }
  ]
}
```

Dieser Payload enthält **kein `appId`** und verwendet nicht den allgemeinen
Cloud-Schreibpfad. Authentifizierung und Token-Erneuerung laufen unverändert
über `WarmLinkCloudApi.post()` in derselben API-Instanz.

Ein `READING_LIVE`-Zyklus einer gescannten Session sendet einmal den Heartbeat,
wartet nach Erfolg `WARMLINK_APP_HEARTBEAT_SETTLE_S = 1.0` Sekunden und liest
anschließend ausschließlich `session.live_codes`. Das gilt auch für **Jetzt
abrufen**, wenn die Session bereits gescannt ist. Die Wartezeit läuft im Worker
und wartet auf dessen Stop-Event; Stop beendet sie sofort. Ein statischer
Reload-Wake verkürzt diese Settle-Zeit nicht. Fortschritt, Merge, Overlay,
Historie und der Countdown verwenden weiterhin den bestehenden Pollpfad.

Initialscan, reines Konfigurationsnachladen, Discovery-only, Gerätecode-
Validierung, API-Debugger und Einzelread-/Schreib-Readback-Worker senden keinen
automatischen Heartbeat. Die Live-/Static-/Other-Klassifikation bleibt erhalten.
Ein normaler IoT-/Cloudfehler des Heartbeats wird einmal knapp geloggt; der
Live-Read läuft ohne Settle-Zeit trotzdem weiter. Authentifizierungsfehler
verwenden die bestehende Session-Invalidierung und Retry-Behandlung.
Erfolgreiche Heartbeats erzeugen keine zusätzliche Logzeile pro Zyklus.

Ein vorgelagerter Request `63 03 00 06 00 01 6C 49` ist als Zusammenhang
wahrscheinlich, wurde beim isolierten Heartbeat-Test aber **nicht direkt
mitgeschnitten**. Der bestätigte Ablauf oben behauptet diesen Zwischenschritt
daher nicht als beobachtet. Die Hardwarebeobachtung stammt aus dem gemeldeten
GL9-Test; die Implementierung wurde hier mit API-/Worker-Mocks geprüft.

## Session und Bedienung

`MainWindow.cloud_session` hält den Pollingzustand unabhängig vom Dialog. Ein neu
geöffneter Dialog übernimmt die entdeckten Geräte, die Auswahl, Code-Gruppen
und gecachten Zeilen sofort. Das Öffnen löst weder Discovery noch Registerscan
aus. Zusätzlich werden nur die vollständigen gemergten Geräte-Metadaten unter
`warmlink_cloud.cached_devices` gespeichert, gebunden an
`cached_devices_username`. Beim Programmneustart wird dieser Cache sofort
angezeigt und die gespeicherte Auswahl wiederhergestellt. Werte, Code-Gruppen,
Pollingzustand und Session-Validierung werden nicht persistiert.

Passwort und Token bleiben im bestehenden asynchronen Keyring-System;
Authentifizierungsgeheimnisse werden auch aus verschachtelten Gerätefeldern
entfernt. Der Zugangsdaten-Cache im Hauptfenster bleibt im Arbeitsspeicher.
Ein Gerätecache bestätigt keine Anmeldung: Erst die normalen authentifizierten
API-Aufrufe validieren die neue Session.

Stop/Start mit gleichem Account verwendet die Device-Liste und den Wertcache
weiter. Beim Neustart kann der Gerätecache auch ohne Token verwendet werden;
der erste Werteabruf führt dann den regulären Login aus. Token bleiben in der
laufenden Session nutzbar, auch ohne aktivierte Keyring-Speicherung.

Discovery findet ohne passenden Gerätecache, nach Accountwechsel, bei einem
echten Geräte-/Zugriffsfehler oder ausdrücklich über **Geräte neu suchen**
statt. Gerätewahl aus dem Cache sowie Passwort-/Token-Erneuerung erfordern
keine erneute Gerätesuche. Ein Accountwechsel verwirft die bisherige Auswahl,
angezeigte Cloudwerte und den Gerätecache. Erfolgreiche neue Discovery ersetzt
den persistenten Cache. Die manuelle Geräteverwaltung entfällt; alte
`known_device_codes`-Settings bleiben lesbar, dienen der GUI aber nicht mehr
als Gerätequelle. Der Button verwendet `discovery_only=True`: nur Token/Login,
`get_devices`, `get_houses`, `get_house_devices`, Merge und Geräteauswahl.
Es folgen weder `getDataByCode` noch Status oder Fault-History. Die bestehende
Auswahl und ihr Cache bleiben erhalten, soweit das Gerät weiterhin verfügbar
ist; bei einem neuen Gerät wird der alte Wertcache verworfen. Erst **Jetzt
abrufen** oder **Polling starten** liest Werte. Gerätesuche bleibt bei
laufendem Polling gesperrt.

Ein erneuerter Login invalidiert den Konfigurationssnapshot; der nächste
Werteabruf führt einen Initialscan aus. Discovery-only selbst liest dabei
keine Register. Ein vorübergehender Poll-Timeout
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

## Cloud-Historie in der Haupttabelle

Die Spalten heißen **Cloud Wert**, **Cloud vorher**, **Cloud Code**, **Cloud
Abruf**. `cloud_previous_value_by_reg` speichert den vorherigen formatierten
Cloudwert, beispielsweise `55 °C`, ohne daraus einen Modbus-Rohwert `550` zu
erzeugen. Die erste Beobachtung zeigt `--`; identische Werte erhalten die
bisherige Historie. `cloud_values_equal()` vergleicht die gelieferten Werte
unabhängig von Metadaten; auch `8.4` und `"8.40"` gelten als identisch.

Nur eine tatsächliche Änderung nach der ersten Beobachtung ruft die vorhandene
`flash_register_row()`-Animation auf. Zeitstempel, Stale-Status sowie Unit-,
Range- und Typ-Metadaten lösen keinen Flash aus. Der dauerhafte Cloud-Change-State
liegt separat in `cloud_change_highlights`; lokale
`register_change_highlights`, `last_values` und `previous_value_texts` werden
dadurch nicht verändert.

Cloud-only-Zeilen verwenden zusätzlich **Letzter Wert** für denselben
Cloud-Anzeigewert. Sobald ein echter lokaler Wert vorhanden ist, gehört diese
Spalte ausschließlich zur lokalen Historie. **Cloud vorher** bleibt unabhängig
davon verfügbar. Livepoll, statisches Nachladen, Einzelread und beide
Cloud-Schreib-Readback-Pfade verwenden denselben Overlay-/Historiepfad.

## Geräteübersicht

`deviceList` bleibt führend; House-Datensätze ergänzen nur fehlende, `None`-
oder leere Felder. Bestehendes `false` und `0` werden nicht überschrieben.
Doppelte Geräte aus House-Area-/Room-Listen ergänzen sich ebenfalls.

Es gibt eine einzige Tabelle mit einer Zeile pro Gerät. Vorne stehen
`deviceNickName`, `deviceName`, `model`, `custModel`, `deviceStatus`, `isFault`,
`dtuSoftwareVer`, `dtuSignalIntensity`, `isShared`, `houseName`, `houseRoleType`
und `discoverySource`; danach folgen alle tatsächlich gelieferten übrigen Keys
alphabetisch. Auch bisher unbekannte House-Gerätefelder bleiben erhalten.
Fehlende oder leere Angaben erscheinen als `—`; `false` und `0` bleiben sichtbar.

Device-Code, Device-ID, SN, ICCID, Produkt- und House-/Room-/Area-IDs werden
vollständig angezeigt. Die separate Detailtabelle und **IDs anzeigen** entfallen.
Passwort, Token und andere Authentifizierungsgeheimnisse werden weder angezeigt
noch im Gerätecache gespeichert. Log-/Debug-Maskierung bleibt separat bestehen.

## Parametereinstellungen und Cloud-Schreiben

`MainWindow.register_value_sources()` liest die bestehenden lokalen Register,
letzten lokalen Rohwerte und das Cloud-Overlay zentral und quellengetrennt.
Die Parametertabelle zeigt lokale Werte einschließlich App-/Value-Mapping wie
bisher; die zusätzliche Spalte **Cloud** zeigt den übersetzten Cloudwert.
Ohne lokalen Wert steht der Cloudwert auch unter **aktueller Wert**, während
**Rohwert (lokal)** leer (`--`) bleibt. Cloudwerte werden nicht zurück in
Modbus-Rohwerte skaliert.

`apply_cloud_rows_to_main()` benachrichtigt offene Parametereinstellungen über
`update_from_cloud_register(reg_no)`. Initialscan, Livepoll, statisches Nachladen,
Einzelread und Schreib-Readback aktualisieren die betroffene sichtbare Zeile
sofort, auch bei sortierter Tabelle. WP-Steuerung, Timer und SG-Editor erhalten
keine neue Cloud-Logik. Cloud-only öffnet die Parametertabelle ohne Display-
Snapshot und sendet keine lokalen automatischen Blockreads.

Normale **Cloud schreiben**-Aktionen senden nach der bestehenden Werteingabe/
-auswahl direkt. Der zusätzliche Bestätigungsdialog entfällt. Allowlist,
Wertevalidierung, Firmware-Capture-Sperre, Sperre paralleler Schreibbefehle,
Fehlerbehandlung und automatischer Readback bleiben erhalten. Der separate
Experten-/Dry-Run-Schreibtest behält seine eigenen Bestätigungen.

## Alle bekannten Register lesen

Der Hauptfenster-Button bevorzugt eine aktive lokale Verbindung: Standard-
Modbus und Warmlink verwenden weiterhin ihre bisherigen Init-Controller;
Modbus Display verwendet weiterhin den Display-Reboot-Fake-Snapshot.
Auch bei gleichzeitig verbundenem Cloudgerät bleibt dieser lokale Pfad führend.

Ohne lokale Verbindung, aber mit gültiger Cloud-Verbindung und ausgewähltem
Gerät, fordert der Button alle `WARMLINK_644_DISCOVERY_CODES` an: Live, Static,
Other, Raw-Fault-Wörter und bisher nicht unterstützte Kandidaten. Bei laufendem
Polling wird derselbe Worker per `request_full_scan()` geweckt; bei gestopptem
Polling startet ein einmaliger Vollscan mit derselben Session/API-Architektur.
Es wird keine zusätzliche Discovery angefordert. Die Cloud-Leiste zeigt
`INITIAL_SCAN` und Batch-Fortschritt; HTTP läuft weiter außerhalb der GUI.

Der Vollscan klassifiziert anhand seiner frischen Antwort erneut. Ein zuvor
gültiger, nun fehlender Wert bleibt als stale im Wertcache, gilt aber nicht
weiterhin als aktuell unterstützt. Danach läuft Polling wieder mit den
aktualisierten Gruppen. Unit-/Range-Prioritäten und Skalierungen bleiben
unverändert. Ohne gültige Verbindung wird nur ein Status ins Log geschrieben;
Firmware-Capture sperrt auch diesen aktiven Cloudscan.

## Countdown im Hauptfenster

`WarmLinkCloudWorker.timing_updated` liefert unveränderliche
`CloudTimingState`-Snapshots. Zustände sind `INITIAL_SCAN`, `POLL_RUNNING`,
`STATIC_RELOAD`, `DISCOVERY`, `POLL_WAIT`, `RETRY` und `IDLE`; dazu kommen die
Startphasen. Ein Snapshot enthält Batch-Zähler, `polling_active` und für
Wartezeiten eine monotone `deadline` mit `duration`.

Nach Initial-/Livepoll einschließlich Statusabfrage beginnt das volle
eingestellte Intervall, z. B. `next_poll_at = monotonic() + 30`. Ein statischer
Reload weckt den Worker, ohne den zuvor geplanten Livepolltermin zu verschieben.
Retry verwendet die tatsächliche Backoff-Deadline des Workers.

Die schmale Hauptfenster-Leiste verwendet die Gestaltung der vorhandenen
Init-Leseleiste. Ein 250-ms-Qt-Timer zeigt Restzeit und herunterlaufenden Balken;
er führt keine Requests aus und verändert den Zeitplan nicht. HTTP-/House-
Batches zeigen ihren Fortschritt, unbekannte Fortschritte laufen unbestimmt.
Bei `IDLE` wird die Leiste ausgeblendet und der Anzeigetimer gestoppt. Der
Cloudbutton behält seine bisherigen Verbindungszustände.

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

`tests/test_cloud_history_discovery_countdown.py` prüft getrennte Historien,
Cloud-only- und lokale Zeilen, identische Werte/Metadaten, alle Readback-Pfade,
tatsächliches Schließen und Neuöffnen des Dialogs, Discovery-only ohne Wert-/
Statusaufrufe, Device-Merge, fehlende Shared-Felder, Maskierung, Worker-Deadlines,
statisches Nachladen sowie Countdown ohne zusätzliche API-Aufrufe.

`tests/test_cloud_app_heartbeat.py` prüft den exakten appId-freien Payload,
POST-/Relogin-Wiederverwendung, Heartbeat→Settle→Live-Read, einen Heartbeat je
Livezyklus, isolierte andere Worker/Abfragemodi, Fehler-Fallback, Tokenwechsel
und reaktionsfähigen Stop während der echten Settle-Zeit.

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

Ein realer Windows-/Wärmepumpentest dieser Implementierung steht noch aus.
Die Heartbeat-Hardwarebeobachtung oben stammt aus dem gemeldeten GL9-Test.
Mock-/Protokolltests
belegen die Read-/ACK-Zuordnung und Skalierung, nicht die tatsächliche
Antwortlatenz eines konkreten LTE-Modems.

Abschlussprüfung: `python -m pytest -q` — **433 bestanden**;
`python -m compileall -q .` und `git diff --check` erfolgreich.
Im ersten Gesamtlauf fiel ein unveränderter FC03-Timertest an seiner
530-ms-Wartegrenze aus; er bestand isoliert und der zweite vollständige Lauf
war grün. Scheduler und seine Tests wurden für den Heartbeat nicht geändert.
Der Metadaten-Audit meldet weiterhin keine belegten Unit-/Range-Konflikte.
