# WarmLink: Einheiten, Einzelreads und Wertequellen

Die gemeinsame Unit-Auflösung liegt in `cloud/metadata.py`. Sie verwendet in
dieser Reihenfolge eine explizite, nicht leere Unit-Zeichenfolge aus der aktuellen
API-Antwort, die lokale Einheit eines bestätigten Mappings, einen statischen
Cloud-Hint oder keine Einheit. `TEMP` ist ausschließlich ein Transporttyp und
erzeugt keine physikalische Einheit. Kandidaten und unbestätigte Zuordnungen
liefern keine lokale Unit-Evidenz.

`normalize_data_values()` erhält alle tatsächlich gelieferten Metadaten,
einschließlich optionaler Felder wie `unit`, `dataTypeAi` und `tmJson`, sowie den
Originaleintrag unter `raw`. Diese Felder werden nicht vorausgesetzt. Im
Repository ist `dataTypeAi=binary` für reale Fault-Antworten dokumentiert; dieser
Änderung liegt kein zusätzlicher Live-Abruf zugrunde.

## Automatischer Unit-Audit

Ausführen mit `python tools/audit_cloud_units.py`. Der Audit prüft bestätigte,
auflösbare Zuordnungen gegen `data/foxair_phnix_registers.json` und beendet sich
bei widersprüchlichen vorhandenen Einheiten mit einem Fehlercode. Fehlende
lokale Einheiten sind keine Konflikte.

Ausgangspunkt: aktueller Branch `work`, Commit `bd6b28c`.

| Code | Register | Hint vorher | bestätigte Einheit danach |
| --- | ---: | --- | --- |
| D22 | 1127 | °C | m³/h |
| D23 | 1128 | °C | min |
| D30 | 1437 | °C | min |
| E14 | 1144 | °C | N |
| F23 | 1089 | °C | rpm |
| F25 | 1103 | °C | rpm |
| F26 | 1104 | °C | rpm |
| P02 | 1198 | °C | min |
| P03 | 1199 | °C | min |
| P08 | 1204 | °C | W |
| P09 | 1203 | °C | days |
| P10 | 1205 | °C | % |
| P13 | 1435 | °C | days |
| P16 | 1444 | °C | bar |

Vorher und nachher wurden alle 262 bestätigten Mappings geprüft. Alle 14
Konflikte sind bereinigt, kein Unit-Konflikt bleibt offen. Bei 131 Mappings fehlt
eine lokale Unit, darunter `T09`. Diese Metadatenlücken bleiben bewusst offen;
vorhandene Cloud-Hints bleiben nutzbar und fehlende Einheiten werden nicht anhand
von Namen oder `TEMP` erfunden.

## Einzelread und Dialog

`WarmLinkCloudReadWorker` liest einen oder wenige Codes über `getDataByCode`.
Er übernimmt das bereits ausgewählte Gerät und verwendet vorhandene Tokens.
Nur die bestehende API-Authentifizierung darf bei fehlendem Token einloggen oder
bei einer abgelaufenen Session erneut einloggen. Device-/House-Discovery, Status
und Fault-History gehören weiterhin zum normalen Polling-Worker.

Das Ergebnis wird vor der Token-Speicherung an einen Qt-Slot des Hauptfensters
geliefert. Der Slot aktualisiert Overlay, Tabelle und offene Registerdialoge.
Erfolg, leere Antworten, API-Fehler und unmittelbare Validierungsfehler beenden den
Dialogstatus. Während eines Reads sind weitere Reads gesperrt; Worker und Thread
werden mit `deleteLater` freigegeben und Referenzen nach Thread-Ende geleert.
Ein Schließen während des Reads wird bis zum Ende des Threads zurückgestellt.
Dialog-Refreshes prüfen nur passende Cloud-Codes über den bestehenden Resolver,
statt jedes Mal den gesamten Katalog aufzulösen.

## Engineering-Werte und Modbus-Rohwerte

Cloud-only-Zeilen tragen `value_source="cloud"` und einen separaten `cloud_value`.
Das Overlay erhält zusätzlich `engineering_value` und Live-Metadaten. Skalare
Cloudwerte haben keinen lokalen Modbus-Rohwert (`local_raw_value=None`);
Rohwert- und Signed-Spalten zeigen dafür `--`. Das bisherige numerische Feld
`raw_value` bleibt für bestehende Projektionen kompatibel, ist bei einer
Cloudquelle jedoch kein lokaler Rohwert und wird nicht für Quickwrite dekodiert.
`cloud_value` erhält auch Nachkommastellen und Vorzeichen ohne 16-Bit-Begrenzung.
Bestehende Fault-/Kontakt-Bitwörter behalten ihre unveränderten Rohbits.
Echte lokale Register behalten ihren Modbus-Rohwert, Cloud bleibt ein Overlay.
Neue Cloudwerte aktualisieren dieselbe synthetische Zeile einschließlich Anzeige,
Zeitstempel und Cloud-Spalten. Ein Einzelread erhält andere gecachte Cloudcodes.

Quickwrite übernimmt Cloud-Engineeringwerte direkt. Lokale Rohwerte werden wie
bisher über den Registertyp dekodiert. Benutzeränderungen im Eingabefeld werden
bei eintreffenden Cloudwerten erhalten. Für `R02` verwendet die aktuelle lokale
Definition Register **1158**: lokal `550` und Cloud `55` belegen beide mit `55`
vor. Eingabe `52` ergibt lokal `520`, über Cloud weiterhin `"52"`. Die
Schreibbestätigung zeigt den Engineering-Wert mit der zentral aufgelösten Unit.
Die bestehende Cloud-Control-/Write-/Readback-Implementierung bleibt erhalten.

## Validierung

`python -m pytest -q`: **291 bestanden**. Die Tests prüfen unter anderem die
Unit-Priorität, alle bestätigten lokalen Einheiten gegen widersprüchliche Hints,
optionale Live-Metadaten, mehrere skalierte Typen, die R02-Vorbelegung und beide
Schreibrepräsentationen, direkte API-Aufrufe, Session-/Geräteauswahl, Relogin,
GUI-Thread-Rückmeldung, Fehler-/Leerantworten und Thread-Freigabe.
`python -m compileall -q .` und `git diff --check` waren erfolgreich.

Drei bereits im unveränderten Ausgangsstand fehlschlagende Tests hatten
unvollständige Fixtures: der Backup-Test erwartete einen geänderten Wert trotz
identischem Istwert; zwei Capture-Stubs enthielten benötigte Methoden nicht.
Diese Fixtures wurden korrigiert, ohne die zugehörige Produktlogik zu ändern.
