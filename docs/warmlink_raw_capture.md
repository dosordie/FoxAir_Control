# Warmlink RAW Langzeit-Capture

## Zweck

Der Warmlink RAW Langzeit-Capture ist eine Experten-/Forschungsfunktion, um den Warmlink-/Modbus-Datenstrom über längere Zeit möglichst vollständig mitzuschneiden. Er funktioniert sowohl mit dem Warmlink-Backend über TCP/IP/ser2net als auch über `Serial / COM-Port`.

Ein wichtiges Forschungsziel ist die Frage, ob über den RS485-Bus zwischen Wärmepumpen-Mainboard und Warmlink-/LTE-Modem (DTU) irgendwann Firmwaredaten, Update-Handshakes oder andere bisher unbekannte Übertragungen sichtbar werden.

> **Experimentell / reine Forschung:** Es ist nicht bekannt und wird ausdrücklich **nicht garantiert**, dass eine Mainboard-Firmware überhaupt über diesen Bus übertragen wird. Ebenso ist nicht garantiert, dass während eines Langzeit-Captures jemals ein Update stattfindet, dass ein mögliches Update eindeutig erkannt wird oder dass sich aus einem Mitschnitt später ein nutzbares Updateverfahren ableiten lässt. Ein Capture kann deshalb Tage, Wochen oder länger laufen, ohne jemals relevante Firmware-Daten zu erfassen.

Der Langzeit-Capture ist **kein Firmware-Updater**. Es gibt keine Firmware-Schreib-, Replay- oder Update-Funktion.

## Aktuelles Programmverhalten

Im aktuellen FoxAir Control gibt es im Hauptfenster einen eigenen Button:

**`Langzeit-Capture ...`**

Dieser öffnet das separate Fenster **Warmlink Langzeit-Capture**. Die Capture-Funktion befindet sich damit nicht mehr primär in den allgemeinen Programmeinstellungen.

Der Capture ist ausschließlich mit der Kommunikationsart **`Modbus Warmlink LTE`** verfügbar. Ist ein anderes Backend ausgewählt, zeigt das Capture-Fenster einen Hinweis und der Start-Button bleibt deaktiviert.

Die Kommunikationsart wird unter **Programm-Einstellungen → Verbindung** eingestellt.

## Die zwei Capture-Modi

### Normaler Langzeit-Capture

Der Modus **`Normaler Langzeit-Capture`** zeichnet den Warmlink-Datenverkehr über längere Zeit auf.

Dabei bleiben die normalen Lese- und Schreibfunktionen von FoxAir Control grundsätzlich erlaubt. Das bedeutet: FoxAir Control kann weiterhin eigene Telegramme senden.

Dieser Modus ist für normale Diagnosezwecke geeignet, aber **nicht die bevorzugte Wahl für einen rein passiven Parallelabgriff**, wenn das originale LTE-Modem weiterhin als Modbus-Master am gleichen RS485-Bus angeschlossen ist.

### Firmware-Langzeit-Capture (streng passiv)

Der Modus **`Firmware-Langzeit-Capture (streng passiv)`** ist speziell für einen möglichst unbeeinflussten Langzeitmitschnitt gedacht.

FoxAir Control aktiviert dabei eine zentrale TX-Sperre bereits auf Worker-/Sendeebene. Zusätzlich werden aktive Funktionen, die eigene Telegramme erzeugen könnten, gestoppt oder verhindert:

- Schreibfunktionen werden deaktiviert.
- Init-/Basisregister-Lesevorgänge werden verhindert bzw. abgebrochen.
- Livewerte-Auto-Polling wird gestoppt.
- Wartende Leseanforderungen werden verworfen.
- Eine aktive Warmlink-Diagnose über den Dual-Bus-Logger wird gestoppt.
- Neue Sendeversuche werden blockiert und können als `passive_tx_blocked` im Event-Log erscheinen.

Für einen USB-RS485-Adapter, der parallel zum weiterhin angeschlossenen LTE-Modem auf A/B aufgelegt ist, ist dieser Modus die empfohlene Variante.

> Die TX-Sperre gilt für **FoxAir Control**. Andere Programme, andere Rechner oder andere Teilnehmer auf dem RS485-Bus können dadurch nicht am Senden gehindert werden.

## Langzeit-Capture starten

### 1. Warmlink-Verbindung vorbereiten

Unter **Programm-Einstellungen → Verbindung** muss als Kommunikationsart gewählt sein:

**`Modbus Warmlink LTE`**

Für einen direkt am PC angeschlossenen USB-RS485-Adapter typischerweise:

- Transport: `Serial / COM-Port`
- COM-Port: z. B. `COM3`
- Baudrate: `9600`
- Parität: `None / N`
- Datenbits: `8`
- Stopbits: `1`

Für den untersuchten Warmlink-/LTE-Bus gilt damit **9600 8N1**.

Bei aktiver Verbindung sind die Kommunikationsparameter gesperrt. Zum Ändern von Backend, Transport oder COM-Port deshalb zuerst trennen.

Die Hardwarebeschreibung für den parallelen RS485-Abgriff steht in [HowToWarmlink_Modbus.md](HowToWarmlink_Modbus.md).

### 2. Capture-Fenster öffnen

Im Hauptfenster:

**`Langzeit-Capture ...`**

Das Fenster zeigt oben einen Live-Status mit lokalen Capture-Werten und darunter die Einstellungen für Modus, Aufzeichnung, Rotation und Speicherlimits.

### 3. Capture-Modus wählen

Für einen rein passiven Forschungs-Mitschnitt am parallelen LTE-/DTU-Bus:

**`Firmware-Langzeit-Capture (streng passiv)`**

Für allgemeines Logging, bei dem FoxAir Control weiterhin aktiv lesen oder schreiben darf:

**`Normaler Langzeit-Capture`**

### 4. Aufzeichnung einstellen

Im Bereich **Aufzeichnung** stehen zur Verfügung:

- Capture-Verzeichnis
- effektiver Ordner
- `RX aufzeichnen`
- `TX aufzeichnen`
- `Events/Index schreiben`
- `Standby während Capture verhindern`

Für Forschungs-Captures sollten mindestens **RX** und **Events/Index** aktiviert bleiben.

`TX aufzeichnen` kann auch im Firmware-Modus aktiviert bleiben. Im streng passiven Betrieb sollten durch FoxAir Control trotzdem **0 TX-Bytes** entstehen. Gerade dadurch kann der Status zusätzlich als Kontrolle dienen, dass FoxAir Control selbst nichts gesendet hat.

### 5. Starten

Im normalen Modus lautet der Start-Button:

**`Verbinden & Capture starten`**

Im Firmware-Modus:

**`PASSIV verbinden & Firmware-Capture starten`**

Ist FoxAir Control noch nicht verbunden, wird die Verbindung hergestellt und danach der Capture gestartet. Besteht bereits eine passende Warmlink-Verbindung, startet der Capture direkt.

Jeder neue Capture-Start erzeugt ein **neues freies Segment**. Vorhandene Tagessegmente werden nicht überschrieben oder fortgesetzt.

## Live-Status

Das Capture-Fenster aktualisiert seinen Status laufend und zeigt unter anderem:

- **Warmlink-Verbindung**
- **Capture** aktiv/inaktiv
- **Modus**
- **TX-Sperre**
- **Energiespar-Sperre**
- aktuelles Segment
- RX-Bytes
- **TX durch FoxAir Control**
- letzter RX-Zeitpunkt
- letzter TX-Zeitpunkt
- Drops
- Anomalien
- Fehler

Im streng passiven Firmware-Modus sollten insbesondere sichtbar sein:

- **`FIRMWARE-CAPTURE AKTIV – STRENG PASSIV`**
- **`TX-SPERRE AKTIV – streng passiv`**
- **`TX durch FoxAir Control: 0 B ✓`**

Der Button im Hauptfenster zeigt während eines aktiven Firmware-Captures ebenfalls:

**`● Firmware-Capture AKTIV`**

Beim normalen Langzeit-Capture wird daraus:

**`● Langzeit-Capture AKTIV`**

## Einstellungen während eines laufenden Captures

Während ein Capture aktiv ist, werden die Capture-Einstellungen im Fenster gesperrt. Damit wird verhindert, dass Dateipfade, Modus oder Rotationsparameter mitten in einem laufenden Segment verändert werden.

Verfügbar bleiben insbesondere:

- **`Capture stoppen`**
- **`Neues Segment starten`**
- Capture-Ordner öffnen

Nach dem Stoppen können die Einstellungen wieder geändert werden.

## Energiespar-Sperre

Im **Firmware-Langzeit-Capture** wird die Energiespar-Sperre automatisch aktiviert. Unter Windows verwendet FoxAir Control dafür eine Systemanforderung, damit der Rechner während des laufenden Forschungs-Captures möglichst nicht automatisch in Standby geht.

Im normalen Langzeit-Capture kann **`Standby während Capture verhindern`** separat ein- oder ausgeschaltet werden.

Die Energiespar-Sperre verhindert keinen manuellen Shutdown und ist kein Ersatz für eine zuverlässige Stromversorgung des Capture-Rechners.

## Capture beenden / Verbindungsverlust

Mit **`Capture stoppen`** wird der Logger sauber beendet und die Einstellung `enabled` wieder deaktiviert.

Wird die Warmlink-Verbindung getrennt oder geht sie verloren, beendet FoxAir Control den aktiven Capture ebenfalls. Ein späterer Reconnect startet dadurch nicht automatisch dasselbe Segment weiter.

## Capture-Verzeichnis

Das Standardverzeichnis ist:

`captures`

Relative Pfade werden unter dem FoxAir-Control-Benutzerdatenordner abgelegt, unter Windows typischerweise z. B. unter:

`%APPDATA%\FoxAir Phnix Control\captures`

Absolute Pfade können ebenfalls verwendet werden.

Im Capture-Fenster werden sowohl der eingestellte Pfad als auch der **effektive Ordner** angezeigt.

- **`Auswählen ...`** wählt einen Ordner.
- **`Öffnen`** legt den effektiven Ordner bei Bedarf an und öffnet ihn im Dateimanager.

## Dateiformate

Pro Segment werden – abhängig von den aktivierten Optionen – Dateien nach folgendem Schema erzeugt:

- `warmlink_capture_YYYY-MM-DD_NNN.rx.bin` – rohe empfangene Bytes
- `warmlink_capture_YYYY-MM-DD_NNN.tx.bin` – rohe von FoxAir Control gesendete Bytes
- `warmlink_capture_YYYY-MM-DD_NNN.events.jsonl` – Chunk-, Frame-, Status-, Anomalie- und Firmware-Events
- `warmlink_capture_YYYY-MM-DD_NNN.summary.txt` – Segment-Zusammenfassung
- `warmlink_capture_YYYY-MM-DD_NNN.UPDATE_DETECTED.txt` – Marker, wenn eine relevante Änderung der beobachteten Firmwareversion erkannt wurde

Die `.bin`-Dateien sind echte Binärdateien und kein Hex-Text.

`events.jsonl` ist ein Hilfsindex. Die Binärdateien bleiben die Quelle der Rohdaten.

Zusätzlich schreibt der Capture `frame_complete`-Events für vollständig und plausibel erkannte Warmlink-/Modbus-Frames. Diese enthalten – soweit sicher bestimmbar – unter anderem:

- Richtung RX/TX
- zugehörige Binärdatei
- Dateioffset Start/Ende
- Frame-Länge
- Busadresse
- Function Code
- Registeradresse
- Registermenge
- Payloadbereich
- CRC-Status

Auch diese Frame-Events sind nur ein Analyseindex und ersetzen die Rohdaten nicht.

## Segmentierung und Rotation

Segmentnamen verwenden das Datum und eine laufende Nummer:

`warmlink_capture_YYYY-MM-DD_001`

Existiert `_001` bereits, wird automatisch `_002`, `_003` usw. gewählt.

Ein neuer Capture-Start verwendet immer ein neues freies Segment. Alte Dateien werden nicht angehängt.

Ein neues Segment kann außerdem manuell über **`Neues Segment starten`** erzeugt werden.

Weitere Grenzen im Capture-Fenster:

- Inaktivitätsrotation
- maximale Einzeldateigröße
- maximaler Gesamtspeicher
- Aufbewahrungsdauer

Die Standardwerte des aktuellen Programms sind:

- Inaktivitätsrotation: **5 Minuten**
- maximale Einzeldateigröße: **1024 MB**
- maximaler Gesamtspeicher: **10240 MB**
- Aufbewahrung: **14 Tage**

Erreicht eine Einzeldatei ihr Größenlimit, wird ein neues Segment begonnen. Speicher- und Aufbewahrungsgrenzen dienen dazu, alte abgeschlossene Segmente zu bereinigen bzw. den Capture bei nicht lösbaren Speicherproblemen sicher zu stoppen. Aktive Dateien werden nicht als alte Segmente gelöscht.

## Drops und Vollständigkeit

Die Capture-Queue ist absichtlich begrenzt, damit ein langsames Laufwerk oder ein Schreibproblem nicht die normale Kommunikation der Wärmepumpe blockiert.

Wenn die Queue voll wird, werden Drops gezählt. Sobald wieder Platz vorhanden ist, kann ein Event vom Typ:

`capture_drop`

in `events.jsonl` geschrieben werden.

Zusätzlich dokumentiert die `summary.txt` die Gesamtzahl der Drops.

> **Drops > 0 bedeuten:** Ab diesem Zeitpunkt kann der Rohmitschnitt unvollständig sein. Für eine spätere Protokoll- oder Firmwareanalyse sollte ein Capture mit Drops nicht als vollständig betrachtet werden.

## Anomalie-Erkennung und Firmware-Verdacht

Die optionale Anomalie-Erkennung verwendet bewusst nur Heuristiken. Sie soll interessante Bereiche für eine spätere manuelle Analyse markieren, aber **keine sichere Firmware-Erkennung vortäuschen**.

Beispiele für auffällige Situationen:

- unbekannte Function Codes in plausiblen neuen Frames
- ungewöhnlich große RX-Datenmengen
- viele FC16-/Write-Multiple-Register-Frames
- fortlaufende Adressbereiche
- unbekannte Datenfolgen
- Reconnects in zeitlichem Zusammenhang mit anderen Auffälligkeiten

`unknown_function` wird nur dann als auffällig gewertet, wenn ein plausibler neuer Frame mit erwarteter Busadresse und unbekanntem Function Code erkannt wurde.

Partial-, Chunk- und Continuation-Daten größerer Warmlink-Statusblöcke sollen nicht fälschlich als neue unbekannte Frames gelten.

Bekannte normale FC16-Statusblöcke wie:

- `0x0443`, 90 Register
- `0x07D1`, 90 Register
- `0x082B`, 90 Register

werden nicht allein deshalb als Firmware-Verdacht bewertet.

## Firmware-/Update-Watch: Register 2104

Register **`2104 / 0x0838`** ist im Projekt als Hauptsoftwareversion bekannt.

Der Logger beobachtet dieses Register **passiv**. Es wird für den Firmware-Capture nicht aktiv zyklisch abgefragt.

Taucht Register 2104 im normalen Warmlink-Datenstrom auf, kann FoxAir Control unter anderem folgende Events erzeugen:

- `firmware_version_seen` – Baseline beim ersten Erfassen
- `firmware_version_changed` – Wert oder Darstellung hat sich geändert
- `firmware_version_increased` – Rohwert ist numerisch sicher höher
- `firmware_update_suspected` – heuristischer Firmwareverdacht in Verbindung mit anderen Auffälligkeiten

Eine Änderung von Register 2104 ist ein starkes Indiz dafür, dass sich die Mainboard-Softwareversion geändert hat. Sie beweist aber nicht, **wie** die Firmware übertragen wurde und ob die Übertragung selbst im Capture enthalten ist.

Wenn eine relevante Änderung erkannt wird, kann zusätzlich eine Datei mit der Endung:

`.UPDATE_DETECTED.txt`

angelegt werden.

## Was ein „erfolgreicher“ Langzeit-Capture bedeutet

Ein technisch sauberer Capture bedeutet zunächst nur:

- RX-Daten wurden aufgezeichnet,
- im Firmware-Modus blieb die TX-Sperre aktiv,
- idealerweise stehen `TX durch FoxAir Control` auf `0 B`,
- es gab keine Queue-Drops,
- es gab keinen Schreibfehler.

Das bedeutet **nicht**, dass ein Firmwareupdate erkannt wurde.

Auch wenn über Wochen keinerlei `UPDATE_DETECTED`, ungewöhnliche Frames oder Versionsänderungen erscheinen, kann der Logger trotzdem korrekt funktionieren. Möglich ist beispielsweise, dass:

- im Beobachtungszeitraum schlicht kein Update stattfindet,
- Firmware nicht über diesen RS485-Bus übertragen wird,
- nur ein anderer Bootloader-/Servicemodus Firmwaredaten empfängt,
- die Übertragung über einen anderen Kommunikationsweg erfolgt,
- die Daten zwar übertragen werden, aber mit den heutigen Heuristiken noch nicht eindeutig erkannt werden.

Genau deshalb ist der Langzeit-Capture als **Forschungswerkzeug** zu verstehen und nicht als zugesagte Firmware-Lösung.

## GUI-Log

Das normale GUI-Log enthält nur kurze Statusmeldungen wie:

- Capture Start/Stop
- Segmentwechsel
- blockierter Sendeversuch
- Anomalie
- Speicherlimit
- Schreibfehler
- Änderung von Register 2104

Die vollständigen Rohbytes werden nicht in das sichtbare GUI-Log geschrieben. Dafür dienen die `.rx.bin`- und `.tx.bin`-Dateien.

## Datenschutz

RAW-Captures können unter anderem enthalten:

- Device-IDs
- Tokens oder Protokollkennungen
- Betriebszustände
- Temperaturen und Einstellungen
- unbekannte herstellerspezifische Daten

Captures deshalb nicht ungeprüft öffentlich hochladen. Vor einer Weitergabe prüfen, ob sensible Informationen enthalten sind.

## Wichtige Empfehlung für den Forschungsbetrieb

Für einen möglichst aussagekräftigen Langzeitmitschnitt am parallel angeschlossenen LTE-/DTU-Bus:

1. **Modbus Warmlink LTE** als Backend verwenden.
2. Bei direktem USB-RS485: **Serial / COM-Port, 9600 8N1**.
3. **Firmware-Langzeit-Capture (streng passiv)** wählen.
4. RX und Events/Index aktiviert lassen.
5. Auf **TX-SPERRE AKTIV** und **TX durch FoxAir Control: 0 B ✓** achten.
6. Drops und Fehler regelmäßig kontrollieren.
7. Capture-Daten bis zur späteren Analyse vollständig aufbewahren.
8. Nicht davon ausgehen, dass ein fehlender Treffer einen Fehler des Loggers bedeutet.

Der Zweck ist, über lange Zeit genügend echte Busdaten zu sammeln, damit bislang unbekannte Abläufe später untersucht werden können. Ob daraus jemals eine reproduzierbare Firmware-Update-Methode entsteht, ist offen.
