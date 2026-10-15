# Register-Audit 15.10.2026

Implementierungsbasis: `work` bei `638b0b833ce2dc7e57d24cf94371bd394ed737c3`.
PR #181/#183 sind darin bereits enthalten. Die folgende Pflege ergänzt diesen
Stand; `main` und Releases werden nicht geändert. Die berechnete
Verdichter-Auslastung wurde auf Nutzerwunsch aus dem Auftrag gestrichen und
erhält weder Berechnung, Anzeige noch Tests.

## Register und Anzeige

| MAIN | Bestätigte Umsetzung | Offene Grenze |
| --- | --- | --- |
| 2026/2027 | INV1:2113 High-/Low-Byte, `storage_type=uint8`, kompatible unsigned UINT16-Anzeige für 0..255 | Physikalische Bedeutung/Einheit |
| 2028 | INV1:2118, signed INT16, einschließlich negativer Werte | Physikalische Bedeutung/Einheit |
| 2056 | Optionales Frostschutz-Exportfeld, Kurzname ohne T?, neutrale UINT16-Rohwertanzeige | V3.5 ohne gefundenen direkten Writer; kein Beweis einer Sensorquelle oder generellen Ungültigkeit |
| 2080 | Inverter-/Driverstatus INV1:2099, BITFIELD, Bits7/14 neutral | Driver-Bitnamen; genaue V3.5-Displaybus-/91099-Dispatcherzuordnung |
| 2109 | Parameterblock-Änderungs-/Synchronisationsmaske, BITFIELD, sechs 90er-Blöcke | Clear/ACK, Persistenz, Bits6–15 |
| 2139 | Schutz-/Frequenzbegrenzungsstatus, ergänzt um Bits0/2/9 | OEM-Namen und State2 für Bits0/2; gemeldeter Zustand allein beweist keine aktuelle Kappung |
| 2152 | EMS Strategy Command State, aktualisierte Bits3–7 | OEM-Namen/finale Aktoren für Bits3/5 und vollständige Consumerketten |

2056 bleibt als Originalregister erhalten. DWIN V1.3 bezeichnet es als TEMP1
„System 1 Frostschutztemperatur 2“. Die V3.5-Export-XREF lässt aber den
Public-Buffer-Offset zwischen 2055 und 2057 aus: **starkes Indiz** für ein
optionales/unbelegtes Feld, keine bestätigte Temperaturmessung. Die bisherige
Temperaturskalierung wird deshalb nicht als Messwert präsentiert. T06_1 ist
kein belegter Cloud-Alias.

### MAIN:2109

| Bit | Maske | Parameterblock |
| --- | --- | --- |
| 0 | 0x0001 | 1: 1001–1090 |
| 1 | 0x0002 | 2: 1091–1180 |
| 2 | 0x0004 | 3: 1181–1270 |
| 3 | 0x0008 | 4: 1271–1360 |
| 4 | 0x0010 | 5: 1361–1450 |
| 5 | 0x0020 | 6: 1451–1540 |

Der Vergleich umfasst 540 Positionen in zwei Parameterabbildern. MAIN1016 ist
von der regulären Markierung ausgenommen; ein separater Hilfsflagpfad kann Bit0
setzen. `0x0021` zeigt die Blöcke 1 und 6. Keine Aussage „Flash gespeichert“.

### MAIN:2139

| Bit | Kompakte Bedeutung |
| --- | --- |
| 0/2 | Temperaturabhängiger Schutz-/Frequenzregelzustand 1/2 |
| 1 | Wasserspreizung A24 |
| 3 | Temperaturdifferenz A27 |
| 4 | Niederdruck A38 |
| 5 | AC-Eingangsstrom T35 |
| 6 | Heißgastemperatur T12 |
| 8 | SG-/Zusatzheizungs-Frequenzlimit |
| 9 | Remote-/WarmLink Mode 4 |
| 10 | Dreiphasiger Strom-Soft-Limiter |

Für Bits0/2 sind die T02-bezogenen Producer `0x20016D50+0x0A/+0x0C` bestätigt.
Ihr **interner Zustand 1** begrenzt den neuen Frequenzkandidaten nach oben auf die
bestehende T30-Sollfrequenz MAIN2071. Das exportierte Bit unterscheidet die
internen Zustände 1/2 nicht. Bit9 kommt von `0x20016A54+0x0E` Klasse 1/2 und
entspricht 2152 Bit6; es ist kein Inverterfehler. Kein allgemeiner Pumpenoverride
wird aus diesen Bits abgeleitet. Die bisherige **A38-spezifische** Notiz zu
MAIN2115=100% und Reset der 10-min-Auto-PWM-Qualifizierung bleibt erhalten.

### MAIN:2152

| Bit | Nachgewiesene Funktion |
| --- | --- |
| 0/1/2 | Thermische Abschalt-/Überschussseite / Hystereseband / Bedarfsseite |
| 3 | Eingriff in vier thermische Sollwert-/Hysteresepfade; OEM-Name und finale Aktoren offen |
| 4 | Remote-Frequenzobergrenze über MAIN1422 aktiviert; kein Beweis aktuell greifender Kappung |
| 5 | Verhindert unter den nachgewiesenen Zusatzbedingungen das Setzen von `0x20016E2C+4 Bit1`; physische Funktion offen |
| 6 | Mode-4-Frequenzregelzustand, gleiche Bedingung wie 2139 Bit9 |
| 7 | Qualifizierter Remote-/Runtimezustand nach 3600 × 500ms = 30min |

Bit7 und MAIN2085 Bit0 teilen den Producer. Normaler Abbruch löscht Aktivflag,
Zähler und Qualifizierungsbit. Das Kommunikations-/Spezialtelegramm-Sperrflag
`0x200144D1` setzt im speziellen Zweig **nur den Zähler** zurück; ein bereits
gesetztes Bit kann während der Sperre stehen bleiben. Nach Wegfall der Sperre
und regulärer Auswertung wird es bis zur erneuten Qualifizierung gelöscht.
Der separate Kommunikationszähler 30000 erhält keine erfundene Zeiteinheit.
Bit7 ist keine gewöhnliche Fehleranzeige und kein schlichtes „AI Saving aktiv“.

### MAIN:2080

V3.5 bestätigt die unveränderte RX-/Exportkette `0x01:2099 → MAIN2080`.
Bits7/14 setzen im jeweiligen Prioritätszweig den internen Wert `0x200152F4`
auf 100. Sein normaler Rechenpfad nutzt die Istfrequenz relativ zu C03; die
Sonderwerte belegen weder tatsächlichen 100%-Betrieb noch Pumpen-PWM. Direkter
Consumer/Public-Export des RAM-Werts und die OEM-Bedeutungen der 19 internen
Bedingungen von `0x0808876C` bleiben offen. Die ältere Livegleichheit mit
Displaybus91099 bleibt als historischer Vergleich dokumentiert; die V3.5-Kopie
nach `0x200119A6` allein schließt den Dispatcher nicht. MAIN2081/2082 bleiben
separate Fehlerwörter.

## Hauptfenster und Diagnose

Für2080/2109/2139/2152 verwendet die Haupttabelle die zentrale
`format_value_by_type()`/`_decode_bit_map()`-Mechanik im kompakten Modus.
Alle aktiven Bits werden unterstützt; unbekannte bleiben als `Bn (unbekannt)`
sichtbar. Null zeigt „Keine aktiven Bits“, fehlender Wert „–“. RAW/HEX bleiben
in der Rohwertspalte, die 16-Bit-Binärmaske und ausführlichen aktiven
Bitbeschreibungen im Tooltip der Wertspalte.

Der System-/I/O-Dialog hat getrennte Tabs für 2146/2147, 2139, 2152, 2109, 2080.
Die vier neuen Tabellen zeigen sämtliche 16 Bits samt Zustand und Detailtext.
Der 2146/2147-Decoder und seine HYD61-/S10-Darstellung bleiben bestehen.
Manuelles Lesen und optionales Polling betreffen **nur den ausgewählten Tab**:
2146/2147 als gemeinsamen Zweierread, die übrigen als Einzelread. So werden
keine unbenötigten Lücken oder dauerhaften zusätzlichen Pollzyklen abgefragt.
Alle Reads nutzen `send_read_request()` und den vorhandenen Scheduler.
Öffnen/Tabwechsel startet keine Anfrage. Schließen stoppt den Polltimer.

Antworten werden dem passenden Request zugeordnet; ein Timeout zeigt den
letzten Wert mit Timeoutstatus. Der fehlerhafte vorhandene Timeoutpfad mit
Zugriff auf eine nicht vorhandene Antwortvariable wurde bereinigt; erfolgreiche
Antworten werden im Antwortpfad verarbeitet. Cloudprojektionen und Werte
anderer Busadressen werden im lokalen Diagnosedialog nicht übernommen.
„Hauptfenster leeren“ leert auch die Diagnosewerte.

## Cloud und Erhaltung des vorhandenen Stands

T49→2065 (°C), T50→2066 (K), T51→2067 (K) sind bestätigte read-only-Aliasse
aus dem Betreiber-Livevergleich vom 14.10.2026. T-Diag1/2/3 bleiben lokale Codes.
Cloudwerte sind bereits skaliert; lokale signed TEMP1-Wörter benötigen `/10`.
Das Cloudmetadatum TEMP ändert Temperaturdifferenzen nicht in °C.

Lokale Cloud-Aliasse/Provenienz wurden auch für T57→2023, T14→2050,
H41→1346, R40/R41→1193/1194, 1250/CP1-1 und 1256–1269 ergänzt, ohne bestehende
Kennungen zu verdrängen. Alle 505 ALL-Codes und 530 Discovery-Codes bleiben
erhalten, einschließlich der 108 iOS-Ergänzungen. T58=0 bleibt ein gültiger
Wert mit offener Bedeutung; leer/null bleibt davon getrennt und retryfähig.
Die negativen PWM-Livetests bei aktiver WP sind erledigte Beobachtungen,
keine offene Implementierungspflicht und kein dauerhafter Unsupported-Beweis.

EMS2151–2158, deren nichtlineare 800x-Quellen, der separate Schwellwert 1427
und die GoHeating-Pro-OEM-Metadaten bleiben erhalten. Keine neue
Modbus-/Cloud-Schreibfreigabe, keine 800x-Servicewrites, keine Gerätesteuerung
und keine Hardware-Schreibtests. Alle Ergänzungen sind Metadaten/Anzeige/Reads.

## Historische Aussagen und Primärbelege

Ältere V3.3-Texte „2139=Mehrzonen-Runtime“, „2109 Einzelbits unbekannt“ oder
„2152=Zone1“ sind überholt. `runtime_registers_2xxx.md` liegt nicht im
öffentlichen FoxAir-Control-Repository; das private RE-Repository wurde nicht
verändert. Die öffentlichen Register-/Knowledge-Texte und diese Übersicht
halten den neueren Stand fest. Die hier genannten direkten ASM-Beweise gelten
für V3.5/Softwarecode 82400644, soweit nicht ausdrücklich anders bezeichnet.

- [V3.5-Registeraudit: RX/Export, Bytes, 2056, 2109](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/open_registers_audit_2026-10-14.md)
- [Follow-up mit aktuellen Nachträgen 7–10](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/open_registers_followup_2026-10-15.md)
- [Frühere XREF-Untersuchung; offene Aussagen durch Follow-up ergänzt](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/variable_200152F4_2139_2152_followup_2026-10-15.md)
- [INV1:2099/MAIN2080](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/inverter_status_2080.md)
- [Adaptive Inverterregelung/EMS/MAIN1422](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/adaptive_inverter_control.md)
- [2139: historische Analyse mit neueren Nachträgen](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/FW3.3-MAIN-2139-FREQUENZLIMITIERUNGEN.md)
- [Unit1-Protokoll: Herkunft der Rohwörter](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/FW3.3-UNIT1-INVERTER-PROTOKOLL.md)
- Direkte ASM-Belege: [2109:chunk0040](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/disassembly/chunks/chunk-0040.s) (`0x080714A4–0x0807157C`), [2139:chunk0046](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/disassembly/chunks/chunk-0046.s) (`0x080760D6–0x08076140`), [2152 Bit3:chunk0015](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/disassembly/chunks/chunk-0015.s), [Bit5:chunk0023](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/disassembly/chunks/chunk-0023.s), [Bit7:chunk0064](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/disassembly/chunks/chunk-0064.s), [2080-Verbraucher:chunk0066](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/disassembly/chunks/chunk-0066.s).
- [#185 einschließlich aller Nachträge vom 15.10.](https://github.com/dosordie/FoxAir_Control/issues/185), [#178 mit Livevergleichen](https://github.com/dosordie/FoxAir_Control/issues/178).

## Geänderte Dateien und Prüfung

| Bereich | Dateien |
| --- | --- |
| Register/Knowledge | `data/foxair_phnix_registers.json`, `data/foxair_phnix_knowledge.json` |
| Zentrale Formatierung | `core/foxair_phnix_core.py` |
| Cloud-Aliasse | `cloud/warmlink_codes.py` |
| Hauptfenster/Kommunikation | `foxair_phnix_control.py` |
| Diagnose-Tabs | `dialogs/decoder_dialogs.py` |
| Tests | `tests/test_register_audit_20261015.py`, `tests/test_register_mapping_integrity.py`, `tests/test_ios308_registers_and_codes.py`, `tests/test_fault_decoder.py`, `tests/test_csv_register_logger.py` |
| Dokumentation | `CHANGELOG.md`, `docs/warmlink_ios308_ems.md`, diese Übersicht |

Die neuen Integrationstests verwenden die tatsächliche Haupttabelle,
Cloudprojektion und Scheduler-/FC03-Antwortzuordnung mit simuliertem Transport.
Sie prüfen Mehrfach-/unbekannte Bits, Null/fehlend, signed/unsigned Grenzen,
Kelvin und Cloud-Engineering-Skalierung, alle fünf Diagnosegruppen, manuelles
Lesen/Polltimer/Timeout, Cloud-/Bus-Trennung und das MAIN-Mapping am Displaybus.
Bestehende Tests sichern zusätzlich Katalogumfang, Discovery/Retry und
800x-Schreibsperren. Die Oberfläche wurde mit simulierten Werten visuell geprüft.

Ein struktureller Vergleich mit der `work`-Basis bestätigt: kein Register oder
lokaler Code verloren; `mode`, `function`, `write_allowed`, Schreibgrenzen,
Servicequellen und GoHeating-Pro-OEM-Metadaten sind unverändert. Der aktuelle
`main`-Katalog enthält noch ältere EMS-Definitionen; deren Unterschiede wurden
nicht in diesen auf `work` basierenden PR zurückübernommen.
