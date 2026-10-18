# WarmLink: Einheiten, Bereiche, Einzelreads und Wertequellen

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

## Automatischer Metadaten-Audit

Ausführen mit `python tools/audit_cloud_units.py`. Der Audit prüft bestätigte,
auflösbare Zuordnungen gegen `data/foxair_phnix_registers.json` und beendet sich
bei widersprüchlichen vorhandenen Einheiten oder belegten Range-Konflikten mit
einem Fehlercode. Fehlende lokale Einheiten oder Bereiche sind keine Konflikte.
Der zusätzliche Berichtsteil `ranges` nennt geprüfte Mappings, bestätigte lokale
Bereiche, Konflikte und unbestätigte statische Hints.

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

## Bereichsauflösung und Range-Audit

Beim Prüfen von PR #161 waren die Bereiche im Knowledge-Bestand überwiegend
Freitext. Das einzige bestehende Register mit numerischen `min`/`max` (2163)
hat kein bestätigtes Cloud-Mapping. 64 eindeutige Angaben wurden deshalb manuell
geprüft und in `foxair_phnix_knowledge.json` als `range` strukturiert: `min`, `max`,
`unit`, `representation="engineering"`, `confidence="confirmed"`, `source` und
wörtliche `evidence`. Die bestehenden Texte bleiben erhalten. Zur Laufzeit werden
keine Zahlen aus Beschreibungen, Defaults, Beispielwerten oder Namen extrahiert;
ein einzelner `write_min` ist keine vollständige Engineering-Range.

`resolve_cloud_range()` verwendet zuerst explizite Live-Grenzen, dann geprüfte
strukturierte lokale Grenzen (Registerdefinition vor Knowledge), danach einen
**unbestätigten** statischen Hint oder leere Felder. Ein partieller Live-Bereich
bleibt partiell; die fehlende Grenze wird nicht aus einer anderen Quelle ergänzt.
Ungültige Zahlen und umgekehrte Grenzen liefern keine Range-Evidenz. Bei einer
abweichenden Live-Einheit werden lokale Grenzen in einer anderen Einheit nicht
verwendet. Die Auflösung verändert weder die Originalantwort noch Schreiblimits,
Skalierung, Unit-Auflösung oder Worker-Abläufe.

Cloud-Datentabelle, CSV und Mapping-Kandidaten verwenden dieselbe Range-Auflösung.
Tooltips und Export-Hinweise zeigen, ob der Bereich aus der Live-Antwort, dem
bestätigten lokalen Wissen oder einem unbestätigten statischen Hint stammt.

Alle **262 bestätigten Mappings** wurden verglichen. Für **64** existieren jetzt
strukturierte, geprüfte lokale Bereiche; dabei wurden **34 statische Konflikte**
gefunden und korrigiert:

| Code | Register | Hint vorher | bestätigter Engineering-Bereich danach |
| --- | ---: | --- | --- |
| A27 | 1056 | -20 … 95 | -20 … 20 °C |
| C04 | 1221 | 0 … 100 | 0 … 99  |
| D03 | 1107 | 10 … 90 | 30 … 90 min |
| D13 | 1118 | 0 … 360 | 0 … 240 min |
| D17 | 1122 | -37 … 80 | -37 … 45 °C |
| D18 | 1123 | -37 … 80 | -37 … 45 °C |
| D19 | 1124 | 0 … 300 | 0 … 20 min |
| D20 | 1125 | 0 … 4 | 30 … 90 Hz |
| D23 | 1128 | 0 … 10 | 0 … 240 min |
| E08 | 1138 | 0 … 60 | 0 … 500 N |
| E10 | 1140 | 0 … 3 | 0 … 500 N |
| E13 | 1143 | -10 … 50 | -20 … 20 °C |
| E14 | 1144 | -10 … 50 | 0 … 500 N |
| F02 | 1060 | -37 … 60 | -15 … 60 °C |
| F03 | 1062 | -37 … 90 | -15 … 60 °C |
| F05 | 1066 | 0 … 3 | -15 … 60 °C |
| F06 | 1068 | 0 … 30 | -15 … 60 °C |
| F18 | 1081 | 20 … 250 | 10 … 1300 rpm |
| F19 | 1083 | 0 … 999 | 10 … 1300 rpm |
| F23 | 1089 | 30 … 90 | 10 … 1300 rpm |
| F25 | 1103 | -20 … 50 | 10 … 1300 rpm |
| F26 | 1104 | 1 … 30 | 10 … 1300 rpm |
| G01 | 1152 | 0 … 1 | 60 … 70 °C |
| G02 | 1153 | 0 … 255 | 0 … 60 min |
| G03 | 1154 | 0 … 255 | 0 … 23 h |
| G04 | 1155 | 0 … 255 | 1 … 30 days |
| H29 | 1034 | 0 … 2 | 0 … 20  |
| P02 | 1198 | 0 … 250 | 0 … 120 min |
| P03 | 1199 | 0 … 250 | 0 … 30 min |
| P09 | 1203 | 0 … 250 | 0 … 30 days |
| P10 | 1205 | 0 … 250 | 0 … 100 % |
| P11 | 1432 | 0 … 250 | 0 … 10 °C |
| P13 | 1435 | 0 … 250 | 0 … 30 days |
| P14 | 1436 | 0 … 250 | 0 … 300 s |

Bei **18 weiteren Codes** wurden zweifelhafte oder dynamische statische Grenzen
entfernt. Es wurden keine neuen Grenzen geschätzt:

| Code | Grund für unknown/leere statische Grenzen |
| --- | --- |
| D22 | Knowledge 1127 nennt 0 bis 50 mit Skalierung; Raw-/Engineering-Zahlenraum nicht eindeutig. |
| D30 | Knowledge 1437 bestätigt Minuten, aber keine Grenzen. |
| P08 | Knowledge 1204 bestätigt Watt, aber keine Grenzen. |
| P12 | Knowledge 1433 nennt Einheit/Schritte, aber keine bestätigten Grenzen. |
| P15 | Knowledge 1438 nennt einen Beispielwert, aber keine Grenzen. |
| P16 | Knowledge 1444 nennt 0.5 bar als Beispielwert, aber keine Grenzen. |
| C12 | Knowledge 1347 nennt C03 als dynamische Obergrenze, keinen konstanten Bereich. |
| R01 | Knowledge 1157 nennt R36 bis R37 als konfigurierbare Grenzen. |
| R02 | Knowledge 1158 nennt R10 bis R11 als konfigurierbare Grenzen. |
| R03 | Knowledge 1159 nennt R08 bis R09 als konfigurierbare Grenzen. |
| R08 | Knowledge 1162 nennt R09 als konfigurierbare Obergrenze. |
| R09 | Knowledge 1163 nennt R08 als konfigurierbare Untergrenze. |
| R10 | Knowledge 1164 nennt R11 als konfigurierbare Obergrenze. |
| R11 | Knowledge 1165 nennt R10 als konfigurierbare Untergrenze. |
| R29 | Knowledge 1167 nennt R30 als konfigurierbare Untergrenze. |
| R30 | Knowledge 1168 nennt R29 als konfigurierbare Obergrenze. |
| R32 | Knowledge 1170 nennt R33 als konfigurierbare Obergrenze. |
| R33 | Knowledge 1171 nennt R32 als konfigurierbare Untergrenze. |

Abschluss: **0 belegte Range-Konflikte**. Für 198 Mappings fehlt weiterhin ein
geprüfter konstanter lokaler Bereich; 165 davon besitzen noch einen statischen,
unbestätigten Hint. Diese verbleibenden Hints sind ausdrücklich keine bestätigten
Bereiche und werden ohne belastbare lokale Evidenz nicht als Konflikte gewertet.
Explizite aktuelle Live-Grenzen werden auch für die bewusst offen gelassenen
Codes angezeigt. Ein Live-Bereich `0 … 250` bei unbekanntem lokalem Bereich wird
nicht als Fehler bewertet. Es wurde kein neuer Live-Cloud-Abruf durchgeführt.

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

`python -m pytest -q`: **412 bestanden**. Die Tests prüfen unter anderem die
Unit-Priorität, alle bestätigten lokalen Einheiten gegen widersprüchliche Hints,
optionale Live-Metadaten, mehrere skalierte Typen, die R02-Vorbelegung und beide
Schreibrepräsentationen, direkte API-Aufrufe, Session-/Geräteauswahl, Relogin,
GUI-Thread-Rückmeldung, Fehler-/Leerantworten und Thread-Freigabe.
Zusätzliche Range-Tests prüfen Live-/lokale Priorität, Zahlenformat-Unterschiede,
unbekannte und partielle Grenzen, strukturierte Engineering-Evidenz, die 18
bewusst geleerten Ranges und die gemeinsame Anzeige-/Export-Auflösung.
`python -m compileall -q .` und `git diff --check` waren erfolgreich.

Drei bereits im unveränderten Ausgangsstand fehlschlagende Tests hatten
unvollständige Fixtures: der Backup-Test erwartete einen geänderten Wert trotz
identischem Istwert; zwei Capture-Stubs enthielten benötigte Methoden nicht.
Diese Fixtures wurden korrigiert, ohne die zugehörige Produktlogik zu ändern.

Cloud-Session, geteiltes Polling, GUI-Fortschritt und Warmlink-FC03-Readback
werden zusätzlich in [WarmLink-Polling und Readback](warmlink_polling_and_readback.md)
beschrieben und getestet.


## Kontakt-/Lastausgangsdecoder und Silentmodus-Timer

Die bestätigten Cloudcodes `S01~S10` (2034) und `O01~023` (2019) werden beim
Öffnen gezielt frisch über `CloudSnapshotRequest` / `getDataByCode` geladen.
Manuelles Lesen und optionales Polling verwenden denselben Worker. Der gemeinsame
Translator interpretiert vollständige 16-stellige BINARY-Wörter sowie dezimale
Werte als uint16; leere, ungültige und unvollständige Antworten bleiben unbekannt.
Die Bitbeschriftungen und Kontakt-Bitänderungsanimation bleiben erhalten.
Beide Decoder bleiben read-only. Cloud-only bevorzugt keine alten lokalen Werte;
mit lokaler Verbindung bleibt die lokale Modbus-Priorität erhalten.

| Register | Cloudcode | Bedeutung | Werte |
| --- | --- | --- | --- |
| 1244 | Timer_Mute_On_En | Start aktiv | 0/1 |
| 1245 | TimerMuteOnHour | Start Stunde | 0–23 |
| 1246 | TimerMuteOnMinute | Start Minute | 0–59 |
| 1247 | Timer_Mute_Off_En | Stop aktiv | 0/1 |
| 1248 | TimerMuteOffHour | Stop Stunde | 0–23 |
| 1249 | TimerMuteOffMinute | Stop Minute | 0–59 |

Alle sechs Lesezuordnungen sind bestätigt. Die sechs Cloud-Schreibfreigaben sind
**neu implementiert und noch nicht live verifiziert**; es wird kein Livenachweis
behauptet. Sie sind regulär nutzbar, ohne experimentelle Checkbox, zusätzliche
Cloud-Schreibbestätigung oder verpflichtende Live-Testphase.

Der Silent-Editor lädt alle sechs Werte gemeinsam und benötigt eine vollständige,
gültige Antwort als Schreibbasis. Nur tatsächlich geänderte Werte werden gesendet.
Das zentrale Verfahren aus PR #189 (`WarmLinkCloudCommandWorker`,
`write_control_batch`, `appId: "16"`, `param[]`) bildet höchstens drei Stufen:

1. Geänderte Freigaben auf 0 gemeinsam schreiben und frisch bestätigen.
2. Geänderte Stunden/Minuten in einem gemeinsamen Batch schreiben und alle Codes
   dieses Batches gemeinsam zurücklesen und einzeln prüfen.
3. Geänderte Freigaben auf 1 gemeinsam schreiben und frisch bestätigen.

Unveränderte Zeiten werden nicht erneut geschrieben; sie stammen aus dem frischen
vollständigen Snapshot. Wenn nur eine Freigabe geändert wurde, entsteht ein Batch
mit einem Parameter. Scheitert eine Stufe, folgen keine weiteren Schreibstufen.
Ein Batch ist keine zugesicherte atomare Serveroperation. Readbacks werden begrenzt
nachgelesen, Writes niemals automatisch wiederholt; es gibt keinen Rollback.
API-Erfolg und frische Wertbestätigung werden getrennt berichtet. Fehlende,
abweichende oder als `cached`, `stale` beziehungsweise `currentEmpty` markierte
Readbacks lassen die betroffenen Änderungen offen. Neuere Eingaben werden durch
alte Schreibantworten nicht bereinigt. Statusmeldungen nennen Erfolg, unvollständige
Antworten, Timeout und Schreibabweichungen.

Geräte-/Account-/Transportwechsel und geschlossene Dialoge verwerfen verspätete
Antworten und stoppen Folgeschritte. Autoload wartet bei laufenden Cloudaufträgen.
HTTP bleibt vollständig im vorhandenen Worker; Polling, Account-Sperre und
LTE-Recovery bleiben bestehen. Der WP-Ein/Aus-Timer-Einstieg öffnet bei Cloud-only
denselben Silent-Editor. Bereits offene kombinierte Dialoge verweisen für Cloud
ebenfalls dorthin. Andere WP-Timer, Backup/Restore und unbekannte Register erhalten
keinen neuen Cloud-Schreibweg. Lokale Modbus-, Display-Paket- und Pausenmechanismen
bleiben unverändert; Cloud-only wartet nicht auf Display-Parameterblöcke.

Offene Praxisprüfungen (keine Nutzungssperre): tatsächliche Übernahme der sechs
Silent-Werte am Zielgerät, Aktivierung/Deaktivierung samt Zeitgrenzen, serverseitige
Teilübernahme, Readback-Latenz und Gerätekontextwechsel während einer Sequenz.
Die automatisierten Tests verwenden ausschließlich synthetische Geräte-/Accountdaten.
