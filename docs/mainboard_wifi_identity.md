# Mainboard-WiFi-ID / Kommunikationsmodul-ID (Issue #115)

Diese gefährliche Servicefunktion ändert die Kommunikations-ID des Mainboards
**dauerhaft**. Eine falsche ID kann Hersteller-Service, Diagnose und Cloudfunktionen
beeinflussen. Sie ist keine allgemeine Register-Schreibfunktion.
Technische Grundlage: [Issue #115](https://github.com/dosordie/FoxAir_Control/issues/115)
mit den dort verlinkten Firmwareanalysen aus FoxAir_updater.

## Freischaltung und Transport

In den vorhandenen Programmeinstellungen **Engineering-Parameter anzeigen**
einschalten. Erst dann erscheint unter **Geräte-Info** der Button
**Mainboard-WiFi-ID ändern …**. Ohne Freischaltung bleibt die normale Geräte-Info
wie bisher. Die Freischaltung wird zusätzlich vor Vorbereitung, Schreibaktion
und tatsächlicher Übertragung geprüft; normale Register-Schreibrechte ändern sich nicht.

Ausschließlich `warmlink_raw`, aktiver lokaler Worker, tatsächlicher Slave `0x63`.
Standard-/User-Modbus, Display-Modbus und Cloud sind ausgeschlossen. Es gibt keinen
Transport-Fallback. Firmware-Capture mit Sendesperre bleibt gesperrt.

## Ablauf

1. **Aktuelle ID lesen**: frische FC03-Abfrage `0x63 / 2001 / 8`, keine Cachewerte.
   2001–2006 sind zwölf ASCII-Bytes; 2007/2008 werden separat als Reserve angezeigt.
2. Neue ID eingeben: exakt `WF` und zehn ASCII-Ziffern (`^WF[0-9]{10}$`).
   Synthetisches Beispiel: `WF2403150123`.
3. **Änderung vorbereiten** liest frisch und zeigt alle zehn Schreibwörter:
   `7001=00AA`, `7002=005A`, sechs Big-Endian-ID-Wörter und die frisch gelesenen
   Reservewörter für 7009/7010.
4. Den Gefahrenhinweis lesen und die Ziel-ID im Bestätigungsfeld erneut eingeben.
   **ID dauerhaft schreiben** liest unmittelbar vorher noch einmal 2001–2008.
   Ändert sich dabei der Block, wird nur die Vorschau aktualisiert: die Ziel-ID
   muss erneut bestätigt werden. Ein sensibles lokales JSON-Backup muss erfolgreich
   gespeichert sein, bevor das einzige FC10-Telegramm gesendet werden darf.
5. Genau ein FC10-Block: `Slave 0x63 / Start 7001 / Quantity 10 / Bytecount 20`.
   ACK muss Slave, Funktion, Start, Menge und CRC exakt bestätigen. Kein Retry.
6. Direkt danach FC03 `2001 / 8`: ID und beide Reservewörter müssen exakt stimmen.
   Erst dann ist die **Änderung im Mainboard-RAM bestätigt**.

Der vorhandene ReaderWorker, FC10-Builder und Sendewarteschlangenpfad werden genutzt.
Während der Vorbereitung/Bestätigung/Prüfung reserviert der Dialog den Worker:
konkurrierende normale Lese-/Schreibanfragen werden nicht gesendet. Vor Beginn
müssen laufende/queued normale Abfragen abgeschlossen sein; bei belegtem Bus später
erneut versuchen. Normales Polling kann anschließend weiterarbeiten.

FC03-RTU-Antworten enthalten keine Startadresse. Deshalb gibt es nur eine ausstehende
Serviceabfrage. Bei Übertragungsfehlern, falschem ACK, unvollständiger/abweichender
Antwort oder Timeout wird die Verbindung geschlossen; verspätete Antworten dürfen
nicht einem neuen Versuch zugeordnet werden. Neu verbinden und den Befund prüfen,
**niemals automatisch erneut schreiben**. Ein Fehler nach FC10 kann eine bereits
ausgeführte Änderung bedeuten; das Ergebnis ist dann unsicher.

## EEPROM und Neustartprüfung

Die Firmware persistiert asynchron. Nach Rückleseprüfung (auch bei abweichendem
Befund nach einem Write) zeigt der Dialog mindestens **60 Sekunden** Wartezeit an.
Bei ausbleibendem ACK/Rückleseergebnis ebenfalls mindestens 60 Sekunden warten.
Vor Ablauf weder ausschalten noch neu starten. Der Dialog/App-Abschluss ist während
des Ablaufs und der Wartezeit gesperrt. FoxAir Control löst keinen Neustart aus.

Erst nach Wartezeit und einer später neu verbundenen lokalen Verbindung kann
**Nach Neustart erneut prüfen** verwendet werden. Zusätzlich muss der Benutzer
bestätigen, das Mainboard tatsächlich neu gestartet zu haben: eine getrennte und
neu verbundene TCP-/COM-Verbindung beweist allein keinen Neustart.
Die erneute FC03-Rückleseprüfung vergleicht ID und Reservewörter. Erst ein passender
Befund zusammen mit der bestätigten manuellen Neustartaktion wird als Persistenz
nach Neustart angezeigt. Das Programm kann den physischen Neustart nicht selbst beweisen.

## Sensibles Backup und Restore

Unter `user_data_dir/device_identity_backups/` wird vor jedem Write ein separates
JSON-Backup mit Zeitstempel, Transport, Slave, alter/erwarteter ID, kompletten acht
Rohwörtern und Reservewörtern gespeichert. Die Prüfergebnisse werden atomar ergänzt.
Auf POSIX werden neue Dateien mit Modus `0600` angelegt. Backups enthalten bewusst
vollständige Gerätekennungen: sicher aufbewahren, nicht ungeprüft als Supportlog teilen.
Normale Logs zeigen nur maskierte IDs. Service-Rohtelegramme werden nicht in normale
RAW-/TX-Captures oder die Haupttabelle eingespeist; es wird keine Capture-Konfiguration geändert.

**Alte ID wiederherstellen …** erscheint nur bei einem gültigen Backup. Der ausgewählte
alte ID-Wert geht durch dieselbe Vorbereitung, erneute Bestätigung, frische Abfrage,
Backup-Erstellung, FC10-, ACK- und Rückleseprüfung. Reservewerte aus einem alten
Backup werden **nie** geschrieben: ausschließlich die aktuell neu gelesenen
2007/2008 werden übernommen. Es gibt keine generische Backup-Schreibfunktion und
keine neuen normalen Schreibmasken/Freigaben für 7001ff.

Alle Beispiele und Tests verwenden synthetische IDs. Keine Prüfung an echter
Hardware wurde im Rahmen der automatisierten Tests vorgenommen.
