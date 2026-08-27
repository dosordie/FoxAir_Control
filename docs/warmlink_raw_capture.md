# Warmlink RAW Langzeit-Capture

## Zweck

Der Warmlink RAW Langzeit-Capture ist eine Experten-/Forschungsfunktion, um den Warmlink-/Modbus-Datenstrom über längere Zeit möglichst vollständig mitzuschneiden. Er funktioniert sowohl mit dem Warmlink-Backend über TCP/IP/ser2net als auch über `Serial / COM-Port`.

Der **eigentliche Firmware-Datenstrom wurde im Projekt bereits auf dem Display-Modbus beobachtet und dieser Übertragungsweg damit bestätigt**. Das Forschungsziel des Warmlink-Langzeit-Captures ist daher nicht mehr die Frage, ob Firmware grundsätzlich übertragen wird, sondern was auf dem Warmlink-/LTE-Bus **vor und während eines gezielt ausgelösten Firmwareupdates** passiert.

Interessant sind insbesondere mögliche:

- Update-Auslöser
- Handshakes
- Steuertelegramme
- Versions- oder Statusinformationen
- zeitliche Zusammenhänge mit dem bestätigten Firmwaretransfer auf dem Display-Modbus

> **Experimentell / reine Forschung:** Nach bisherigem Kenntnisstand führt FoxAir **keine automatischen Firmwareupdates** durch. Ein Firmwareupdate muss bei **Kensol** beauftragt bzw. angefordert und von dort angestoßen werden. Ohne einen solchen gezielt ausgelösten Updatevorgang ist daher auch bei einem sehr langen Warmlink-Capture kein Updateverkehr zu erwarten.
>
> Nicht garantiert ist, dass der eigentliche Update-Auslöser auf dem Warmlink-/LTE-RS485-Bus überhaupt sichtbar ist oder dass sich aus einem Mitschnitt später ein reproduzierbarer eigener Update-Trigger ableiten lässt.

Der Langzeit-Capture ist **kein Firmware-Updater**. Es gibt keine Firmware-Schreib-, Replay- oder Update-Funktion.

## Was bereits bestätigt ist – und was noch untersucht wird

### Bestätigt

- Der Firmware-Datenstrom wurde auf dem **Display-Modbus** beobachtet.
- Der Display-Modbus ist damit als tatsächlicher Übertragungsweg der Firmware bestätigt.
- Firmwareupdates erfolgen nach bisherigem Kenntnisstand **nicht automatisch**.
- Ein Update muss bei **Kensol** beauftragt bzw. angefordert und von dort angestoßen werden.

### Noch offen / Forschungsziel

- Welche Kommunikation auf dem Warmlink-/LTE-Bus einen Updatevorgang vorbereitet oder auslöst.
- Ob dort ein eindeutiger Update-Befehl oder Handshake sichtbar wird.
- Welche Status- oder Versionsinformationen rund um den Updatevorgang übertragen werden.
- Ob sich Warmlink-Ereignisse zeitlich eindeutig dem Firmwaretransfer auf dem Display-Modbus zuordnen lassen.
- Ob sich aus diesen Daten jemals ein reproduzierbarer eigener Update-Auslöser ableiten lässt.

Der Warmlink-Capture ist deshalb vor allem als **begleitender Logger für einen gezielt bei Kensol angestoßenen Updatevorgang** zu verstehen.

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

## Gezielter Mitschnitt eines beauftragten Firmwareupdates

Da FoxAir-Updates nach bisherigem Kenntnisstand nicht automatisch stattfinden, ist ein gezielter Mitschnitt am aussagekräftigsten, wenn der Logger **vor** der Update-Anforderung gestartet wird.

Empfohlenes Vorgehen:

1. Warmlink-Capture starten und **Firmware-Langzeit-Capture (streng passiv)** aktivieren.
2. Wenn möglich gleichzeitig einen Mitschnitt des **Display-Modbus** vorbereiten bzw. starten.
3. Erst danach das Firmwareupdate bei **Kensol** beauftragen bzw. anstoßen lassen.
4. Beide Mitschnitte während des gesamten Updatevorgangs weiterlaufen lassen.
5. Zeitpunkt der Beauftragung bzw. Auslösung notieren.
6. Beginn und Ende des sichtbaren Firmware-Datenstroms auf dem Display-Modbus notieren.
7. Änderungen von Register 2104 und andere auffällige Warmlink-Ereignisse zeitlich dazu vergleichen.

Der Warmlink-Capture ist hierbei vor allem für den **Steuer- und Auslöseverkehr** interessant. Der eigentliche Firmware-Datenstrom wird nach dem bisherigen bestätigten Stand auf dem **Display-Modbus** erwartet.

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

## PHNIX-LTE-Logger- und OTA-Sonderregister

### Fehlerursache und Korrektur

Der frühere Capture fand zwar vollständige `frame_complete`-Frames, behandelte
FC `0x10` für die sichtbare Ausgabe aber nur als generisches Sonderregister.
Die GUI erhielt absichtlich keine Nutzdaten und konnte daher Angebot, kurzes
Echo-ACK und Board-Antwort weder fachlich dekodieren noch miteinander
korrelieren. Außerdem klassifizierte die separate Chunk-Vorschau jeden
Eingangsblock für sich; TCP-/Seriell-Blockgrenzen sind jedoch keine
Framegrenzen. Die Korrektur verlegt Dekodierung und GUI-Weitergabe hinter den
zustandsbehafteten Stream-Indexer und dessen erfolgreiche CRC-Prüfung.

Nur der passive **Modbus Warmlink LTE** Raw-Capture erkennt zusätzlich die
Loggerregister `4`, `6`, `200–215` (ProductKey ab `200`) und `500` sowie die
OTA-Kommandos `50000`, `50007`, `50026`, `50028`, `50030`, `50033`, `50037`,
`50040`, `50043`, `50500` und `50600`. Vollständig CRC-validierte Frames werden
weiterhin unverändert in den RX-/TX-Binärdateien gespeichert und zusätzlich als
`phnix_lte_special_register` in der JSONL-Ereignisdatei indexiert. Das Ereignis
enthält Loggername, Kategorie, Adresse, Quantity, Dateioffsets und – soweit
bekannt – die erwartete Richtung zwischen DTU und Board.

Im Modus **Normaler Langzeit-Capture** erscheint jedes vollständig erkannte
Sonderframe außerdem als kompakte Zeile im Log des Hauptfensters. Angezeigt
werden Name, Adresse, Function Code, tatsächliche beziehungsweise erwartete
Quantity, Richtung und Framelänge. Binäre Nutzdaten – insbesondere Firmware und
ProductKey – werden aus Sicherheits- und Performancegründen nicht ins GUI
kopiert; sie bleiben vollständig in den Capture-Dateien. Der streng passive
Firmware-Capture schreibt dieselben Indexevents, hält das Hauptfenster aber wie
bisher ruhig.

FC `0x10` wird dabei anhand der CRC-validierten Gesamtlänge unterschieden: Ein
Schreibauftrag enthält Bytecount und Nutzdaten, das acht Byte lange Echo ist
das Schreib-ACK, und eine bekannte Board-Adresse mit Bytecount ist eine
fachliche PHNIX-Antwort. Der zustandsbehaftete Decoder ordnet ACK und Antwort
dem vorausgehenden Auftrag zu. `C350` wird als OTA-Angebot (Gerätekennung,
achtstelliger Softwarecode, vierstellige Version) und `C36E` als Board-Status
ausgegeben. Status `0` bedeutet laut Protokoll „angenommen/erlaubt“; unbekannte
Werte bleiben rein numerisch. Die angezeigte Richtung ist ausdrücklich die
**erwartete/semantische Richtung**, nicht eine im passiven Mitschnitt elektrisch
gemessene Senderichtung. Adressen erscheinen stets dezimal und hexadezimal.

Der Stream-Indexer puffert unvollständige Anfänge über beliebige serielle
Eingangsblöcke hinweg. Weder ein einzelnes Unit-Byte `63` noch ein sieben Byte
langer Frameanfang erzeugt deshalb eine Sondermeldung. Erst vollständige Frames
mit gültiger Modbus-CRC gelangen ins JSONL-Event und in die sichtbare Anzeige;
ein Schreib-ACK wird nicht nochmals als Angebot behandelt. Beim Capture-Ende
fasst der Decoder eine erfolgreiche Folge `C350 → ACK → C36E/Status 0` zusammen
und nennt, ob die dokumentierten Folgeschritte `C357 / 50007` (`OTA_FILE_INFO`)
oder `C5A8 / 50600` (`OTA_FIRMWARE_BLOCK`) im Mitschnitt vorkamen.

`50600 / 0xC5A8` (`OTA_FIRMWARE_BLOCK`) besitzt kein normales FC10-Bytecount-
Layout. Der Capture bestimmt sein Ende deshalb über die Modbus-CRC, behält auch
große, auf mehrere TCP-Chunks verteilte Frames im Indexpuffer und schreibt die
Nutzdaten ohne Interpretation oder Kürzung mit. Diese Sonderbehandlung wird
bewusst nicht auf Standard- oder Display-Modbus übertragen.

## Firmware-/Update-Watch Register 2104
Register `2104 / 0x0838` ist als Hauptsoftwareversion bekannt. Eine Änderung von Register 2104 gilt als starkes Indiz für ein abgeschlossenes oder laufendes Firmwareupdate. Ob der Wert numerisch höher wird, hängt vom Versionsformat ab; daher wird jede Änderung erfasst.

in `events.jsonl` geschrieben werden.

Zusätzlich dokumentiert die `summary.txt` die Gesamtzahl der Drops.

> **Drops > 0 bedeuten:** Ab diesem Zeitpunkt kann der Rohmitschnitt unvollständig sein. Für eine spätere Protokoll- oder Firmwareanalyse sollte ein Capture mit Drops nicht als vollständig betrachtet werden.

## Anomalie-Erkennung und Update-Verdacht

Die optionale Anomalie-Erkennung verwendet bewusst nur Heuristiken. Sie soll interessante Bereiche für eine spätere manuelle Analyse markieren, aber **keinen sicheren Update-Auslöser vortäuschen**.

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

werden nicht allein deshalb als Firmware-/Update-Verdacht bewertet.

## Firmware-/Update-Watch: Register 2104

Register **`2104 / 0x0838`** ist im Projekt als Hauptsoftwareversion bekannt.

Der Logger beobachtet dieses Register **passiv**. Es wird für den Firmware-Capture nicht aktiv zyklisch abgefragt.

Taucht Register 2104 im normalen Warmlink-Datenstrom auf, kann FoxAir Control unter anderem folgende Events erzeugen:

- `firmware_version_seen` – Baseline beim ersten Erfassen
- `firmware_version_changed` – Wert oder Darstellung hat sich geändert
- `firmware_version_increased` – Rohwert ist numerisch sicher höher
- `firmware_update_suspected` – heuristischer Firmwareverdacht in Verbindung mit anderen Auffälligkeiten

Eine Änderung von Register 2104 ist ein starkes Indiz dafür, dass sich die Mainboard-Softwareversion geändert hat.

Der eigentliche Firmware-Datenstrom wurde im Projekt bereits auf dem **Display-Modbus** bestätigt. Register 2104 ist im Warmlink-Capture deshalb vor allem für die **zeitliche Korrelation** interessant: Wann ändert sich die gemeldete Softwareversion im Verhältnis zu einem von Kensol angestoßenen Update und zum sichtbaren Firmwaretransfer auf dem Display-Modbus?

Eine Änderung von 2104 beweist nicht, dass der Update-Auslöser selbst über den Warmlink-Bus übertragen wurde.

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

Das bedeutet **nicht**, dass ein Update-Auslöser auf dem Warmlink-Bus erkannt wurde.

Auch wenn über Tage oder Wochen keinerlei `UPDATE_DETECTED`, ungewöhnliche Frames oder Versionsänderungen erscheinen, kann der Logger trotzdem korrekt funktionieren. Dabei ist zu beachten:

- Ohne bei **Kensol** beauftragtes bzw. angestoßenes Firmwareupdate ist nach bisherigem Kenntnisstand überhaupt kein Updatevorgang zu erwarten.
- Der eigentliche Firmware-Datenstrom wird auf dem **Display-Modbus** erwartet; große Firmware-Datenblöcke müssen daher nicht auf dem Warmlink-Bus auftauchen.
- Ein möglicher Auslöse- oder Steuerbefehl könnte sehr kurz sein und nur zu einem bestimmten Zeitpunkt erscheinen.
- Der relevante Auslöser könnte intern im LTE-Modem, in der Cloud-Kommunikation oder auf einem anderen Weg verarbeitet werden und auf dem abgegriffenen RS485-Bus nicht eindeutig sichtbar sein.
- Relevante Steuertelegramme könnten zwar vorhanden sein, mit den heutigen Heuristiken aber noch nicht automatisch als Updateverkehr erkannt werden.

Genau deshalb ist der Warmlink-Langzeit-Capture als **Forschungswerkzeug für den Steuer- und Auslöseweg** zu verstehen und nicht als zugesagte Firmware-Lösung.

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

Für einen möglichst aussagekräftigen Mitschnitt eines gezielt ausgelösten Firmwareupdates:

1. **Modbus Warmlink LTE** als Backend verwenden.
2. Bei direktem USB-RS485: **Serial / COM-Port, 9600 8N1**.
3. **Firmware-Langzeit-Capture (streng passiv)** wählen.
4. RX und Events/Index aktiviert lassen.
5. Auf **TX-SPERRE AKTIV** und **TX durch FoxAir Control: 0 B ✓** achten.
6. Wenn möglich gleichzeitig den **Display-Modbus** mitschneiden.
7. Erst nach Start der Logger das Update bei **Kensol** beauftragen bzw. anstoßen lassen.
8. Zeiten von Beauftragung/Auslösung, Display-Firmwaretransfer und Register-2104-Änderung dokumentieren.
9. Drops und Fehler kontrollieren.
10. Capture-Daten bis zur späteren Analyse vollständig aufbewahren.

Der bereits bestätigte Firmwaretransfer auf dem Display-Modbus liefert dabei die Referenz. Ziel des Warmlink-Captures ist es herauszufinden, **welcher vorgelagerte Steuer- oder Auslöseverkehr dazu gehört**. Ob sich daraus jemals ein eigener reproduzierbarer Update-Trigger ableiten lässt, bleibt offen.
