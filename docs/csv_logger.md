# CSV Logger: PHNIX-Liveblock 2001–2090

Im Hauptfenster unter **Funktionen → CSV Logger ...** (direkt unter
**Langzeit-Capture ...**) eine Datei wählen,
das Intervall einstellen und **Start** drücken. Das Intervall reicht von 5 bis
3600 Sekunden, Standard ist 30 Sekunden. Intervall und zuletzt verwendetes
Verzeichnis werden gespeichert; der Logger startet niemals automatisch.
**Stop** oder das Schließen des Loggerdialogs beendet die Aufnahme und schließt
die Datei. Die Geräteverbindung und normales Cloudpolling bleiben bestehen.

Der Dialog übernimmt das Fenstericon und den Qt-Stil des Hauptfensters.
**Aufzeichnung** enthält Dateipfad, Dateiauswahl, Intervall und den kurzen
Wertehinweis. **Status** zeigt Quelle, Aufnahmezustand, letzten erfolgreichen
Datensatz und Zeilenanzahl. **Start** und **Stop** stehen links in der
Buttonleiste, **Schließen** rechts. Der Schließen-Button verwendet denselben
`closeEvent()`-Pfad wie das Fenster-X: Aufnahme stoppen, den eigenen
Snapshotauftrag abbrechen und Datei flushen/schließen. Eine bereits laufende
normale Modbus-Abfrage oder das Cloudpolling bleibt bestehen.

Eine aktive lokale Verbindung hat beim Start Vorrang. Standard-Modbus und
Warmlink-Modbus verwenden den vorhandenen zentralen Readpfad für genau
`2001/90`; es wird keine zweite Socket-/ser2net-Verbindung geöffnet. Ohne lokale
Verbindung verwendet der Logger ein gültig verbundenes, ausgewähltes
WarmLink-Cloudgerät. Die Quelle und das Gerät bleiben während der Aufnahme
fest. Bei Verbindungsverlust wird der aktuelle Zyklus gegebenenfalls teilweise
abgeschlossen und die Aufnahme beendet; es gibt keine automatische Umschaltung.
Stoppen und neu starten wählt die dann verfügbare Quelle.

Display-Modbus ist zunächst **nicht verfügbar**, auch bei zusätzlich verbundener
Cloud. Der direkte Qty90-Read ist dort im bestehenden Code noch experimentell;
der Logger löst keine Reboot-Fakes oder Parameter-Snapshots aus.

## Datei und Werte

Die Datei verwendet **UTF-8** (neue Dateien mit BOM für deutsches Excel),
Semikolon als Trennzeichen und einen stabilen Header mit genau 90 Registerspalten:

```text
timestamp;source;device;2001;2002;...;2090
```

`timestamp` enthält den lokalen Abschlusszeitpunkt als `YYYY-MM-DD HH:MM:SS`,
ohne `T` und ohne Zeitzonenoffset. `source` ist
`standard_modbus`, `warmlink_raw` oder `cloud`; `device` nennt das Modell bzw.
den Cloud-Gerätenamen. Engineering-Zahlen werden ohne Einheiten gespeichert:
beispielsweise Modbus `TEMP1 raw=453` als `45.3`. Cloudwerte werden mit der
bestehenden Übersetzung übernommen und nicht nochmals als Modbus skaliert.
Bit-/Statuswörter können als numerische Rohwerte erscheinen, z. B. `4096`.
Fehlende oder nicht frisch verfügbare Werte bleiben **leer**, niemals ersatzweise
`0`. Der Zahlenwert `0` bleibt als tatsächliche Messung erhalten.

Neue/leere Dateien erhalten einmalig den Header ohne `R`. Bestehende Dateien
mit exakt passendem neuen Header oder dem alten `R2001`…`R2090`-Header aus
Version 0.3.2 werden ergänzt. Der vorhandene Header und alte ISO-Zeitstempel
werden nicht umgeschrieben; ein inkompatibler Header wird mit einer
Fehlermeldung abgelehnt. Jede Zeile wird geflusht. Schreibfehler stoppen die
Aufnahme und erscheinen im Dialog. Die Zeilenanzahl zählt die aktuelle Aufnahme.

## Frische Snapshots und Zeitplan

Jeder Zyklus hat eine eigene Generation. Lokal wartet der Logger vor seinem
Read auf ältere Qty90-Anfragen und verwendet nur die zu seinem Request
gehörenden CRC-gültigen, frisch decodierten Register. Er liest niemals einfach
den Inhalt von `latest_regs`. Der Warmlink-FC03-Scheduler bleibt unverändert.
Bei einem lokalen Timeout nach 15 Sekunden wird trotzdem eine Zeile mit den
frisch empfangenen Werten und Leerfeldern geschrieben; ein verlorener Zyklus
beendet den Logger nicht. Beschädigte oder nicht eindeutig zuordenbare Antworten
werden nicht als Messwerte verwendet.

Cloud-Snapshots werden beim vorhandenen Cloudworker angefordert und seriell
mit dessen API-Objekt gelesen: **App-Heartbeat `app_heartbeat=23205` → kurze
Settle-Zeit im Worker → getDataByCode**. Der Heartbeat verwendet den dedizierten
Pfad ohne zusätzliches `appId`. Falls kein Worker läuft, verwendet der bestehende
Cloud-Dialog denselben zentralen Worker für einen einmaligen Snapshot. Login,
Token, Keyring, Session und Geräteauswahl bleiben in der vorhandenen Architektur.
Es gibt keinen zusätzlichen periodischen Cloudworker. Einzelread/Schreiben,
der gerade im Hauptfenster läuft, lässt den CSV-Zyklus mit einer entsprechenden
Meldung aussetzen statt einen weiteren Request zu starten.

Verwendet werden ausschließlich bereits bekannte Cloudcodes mit **bestätigtem**
Mapping nach 2001–2090. Aktuell sind das 51 Codes für 50 Registerplätze; bestätigte
Aliasse können dasselbe Register betreffen, wobei der erste frisch verfügbare
Wert verwendet wird. Seit Version 0.3.3 ist `Fault1`…`Fault10` → MAIN 2081…2090
praktisch an der GL9 bestätigt und wird auch im CSV genutzt. Faults bleiben
unsigned rohe 16-Bit-Wörter ohne TEMP-/DIGI-Skalierung: `Fault8=512` ergibt
CSV-Spalte `2088=512`. Fehlende/stale/cached Fault-Werte bleiben leer, echte
Nullwerte werden als `0` geschrieben. Ungemappte Register, beispielsweise 2078,
bleiben im Cloudbetrieb leer.
Kein numerischer Cloudcode wird aus einer Registeradresse erfunden.

Nur die **ungecachte Antwort dieses Zyklus** wird in die CSV übernommen; ein
fehlender Cloudwert wird durch keinen früheren Overlaywert ersetzt. Das normale
Overlay darf nach dem Snapshot aktualisiert werden. Der Cloud-Zyklus hat eine
60-Sekunden-Grenze einschließlich möglicher Wartezeit; verspätete Antworten
werden nicht einem späteren Datensatz zugeordnet.

CSV-Intervall und normales Pollintervall sind unabhängig. Ein Logger-Wunsch
weckt den bestehenden Worker, verschiebt dessen normalen Polltermin aber nicht.
Solange ein Zyklus läuft, werden zusätzliche CSV-Ticks ausgelassen. Es entsteht
weder eine Queue alter Messzeitpunkte noch ein konkurrierender FC03-/HTTP-Lauf.
Die Statusanzeige nennt Quelle, erhaltene Werte, Zeilenanzahl und letzten
erfolgreichen Datensatz. Normale Erfolge werden nur auf hohem Debuglevel geloggt;
Fehler und Timeouts erscheinen im Hauptlog.

## Prüfung am realen Gerät

Die Tests prüfen Dateiformat/Append, Engineering-Skalierung, Generationen,
Teiltimeouts, feste Quelle, echte zentrale FC03-Decodierung für Standard und
Warmlink, sowie Heartbeat/Settle/Serialisierung im Cloudworker. Zusätzlich sind
Tests an einer GL9 mit Modbus und Cloud sinnvoll, insbesondere bei gleichzeitigem
Polling, langsamer Verbindung, Stop und anschließendem Datei-Append. Ein
Windows-Test kann die Excel-Erkennung und den Dateidialog zusätzlich bestätigen.
