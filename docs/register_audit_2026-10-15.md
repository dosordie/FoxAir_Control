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

## Nachtrag: Display-Modbus und virtuelle Unit-1-Telemetrie

Basis dieses Nachtrags ist `work` bei `e1bbed8` einschließlich des inzwischen
gemergten PR #186. Das private Reverse-Engineering-Repository bleibt unverändert.
Die berechnete Verdichter-Auslastung bleibt weiterhin ausgeschlossen.

### DWIN:3001–3021

| Register | Bedeutung / Darstellung |
| --- | --- |
| 3001–3010 | Anzeige-/Statuswörter, Einzelbedeutungen offen; unsigned RAW |
| 3011 / 0x0BC3 | Eigenständige Parameter-Synchronisations-/Änderungsmaske; BITFIELD, kein Enum und keine Gleichsetzung mit MAIN2109 |
| 3012 / 0x0BC4 | Display-Softwarecode; der V1.7-Writer setzt 463 |
| 3013 / 0x0BC5 | Display-Firmwareversion; V1.7-Writer setzt RAW 17; dynamische Anzeige RAW/10, auch für andere Versionen |
| 3014/3015 | Kennungs-/Statusfelder, Bedeutung offen |
| 3016 / 0x0BC8 | RTC-Wochentag, Export 1..7: RTC-Byte 0x23 wird um 1 erhöht; keine unbewiesene Zuordnung „0=Sonntag“ |
| 3017 / 0x0BC9 | RTC-Jahr relativ zu 2000, z.B. RAW 26→2026 |
| 3018–3021 | RTC-Monat, Tag, Stunde, Minute; BCD wird durch DWIN in Dezimalwerte konvertiert |

463/17 sind Beispiele der untersuchten Display-V1.7, keine festen Gerätewerte.
Der Wochentag bleibt numerisch; der betreffende ASM-Pfad belegt keine Namen
für die sieben Tage. `Time_2Protocol` steht in
[DEMONS.ASM, Zeilen 17820–17895](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L17820-L17895),
die Versionswriter in [Zeilen 395–404](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L395-L404).

3011-Bits: Bit 1/0x0002→ Paket 1001, Bit 2/0x0004→1091,
Bit 3/0x0008→1181, Bit 4/0x0010→1271, Bit 5/0x0020→1361,
Bit 6/0x0040→1451, Bit 7/0x0080→ optionales Paket 1541,
Bit 15/0x8000→ Initialisierung/Parameter neu laden. Kombinierte Masken bleiben
vollständig sichtbar; andere Bits erhalten keine erfundenen Namen.

### Anzeigevariablen und Objektwörter

| DWIN / FoxAir-ID | Bestätigte Einordnung |
| --- | --- |
| 0x11C0 / 4544 | Abtau-Icon: 0 ausgeblendet, 1 sichtbar; kein eigener Hardwarezustand |
| 0x1270 / 4720 | Bereits invertierter Mischventil-Anzeigewert `100 − MAIN2163`; keine belegte physikalische Öffnungsrichtung und keine zweite Invertierung |
| 0x1272–0x1275 / 4722–4725 | WW-Tank-, Puffer-, Einlass- und Auslasswassertemperatur als Displayanzeige, TEMP1 |
| 0x1276/0x1277 / 4726/4727 | Zone 1/2: 0 anzeigen, 1 ausblenden |
| 0x1278/0x1279 / 4728/4729 | AT-kompensierte Wassersollwerte aus MAIN2164/2165, TEMP1 |
| 0x127A/0x127B / 4730/4731 | Für Z01=7/8/9: 0 ausgeblendet, 1 Stop/kein Bedarf, 2 Run/Bedarf; keine universelle Heizkreisfreigabe |
| 0x127C / 4732 | Allgemeiner AT-kompensierter Wassersollwert aus MAIN2014, TEMP1 |
| 0x127D/0x127E / 4733/4734 | Temperaturkompensation für die jeweilige Zonenanzeige aktiv/inaktiv |
| 0x1280–0x1287 / 4736–4743 | Sichtbarkeitsflags für System 2-Kompressor, Hochgeschwindigkeitslüfter, Lüfter 1, Niedriggeschwindigkeitslüfter, Lüfter 2, System 1-EVI, System 2-Ventil, System 2-EVI |
| 0x1720/0x1730 / 5920/5936 | Betriebsart-/Sonderbetriebszustand-Textzeiger, unsigned Objektwörter statt MAIN-Modus-Enum |
| 0x1800/0x1880/0x1A00 / 6144/6272/6656 | Sensorfehler-Anzeigeobjekte T01/T02/T03, keine Temperaturen |

Bei 4722–4725 setzt der Sensorfehlerpfad Ersatzanzeige 0. Der Wert allein belegt
somit keine gemessenen 0 °C; Name und Tooltip kennzeichnen die Displayanzeige.
Die Temperaturdarstellung bezieht sich auf die dokumentierte Celsiusdarstellung;
die DWIN-Routine enthält auch Fahrenheitpfade. Es wird keine automatische
Einheitenumrechnung aus einem unbekannten Displayzustand behauptet.

Für 4736–4743 gilt 0 = Objekt sichtbar, 1 = ausgeblendet, abhängig von Fan-Typ/-Anzahl
und Systemkonfiguration. Die genauen XRAM-Prädikate stehen als
`visibility_condition` in den Metadaten. System 1-EVI/4741 wird in beiden
untersuchten Systemzweigen auf 0 gesetzt; daraus folgt keine reale EVI-Aktivität.
Quelle: [Status_Show_Hide_Load](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L19640-L19860).

23 individuell belegte Sensor-/Fanfehler-Objektbasen aus
`Fault_Status_Display_T01` bis `T28` sind als unsigned Objektwörter erfasst,
jeweils mit dem durch ASM beschriebenen Objektbereich. Nicht vorhandene
T13/T14-/T16/T17-/T25-Writer wurden nicht erfunden. Es erfolgt keine pauschale
Ausweitung auf sämtliche Wörter der Pointerblöcke und keine Klassifizierung
des übrigen Bereichs 4744–4863 als Temperaturen.
Quelle: [Fault_Status_Display](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L16760-L16980).
Die Zonenanzeige steht in [Zeilen 730–815](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L730-L815),
[1230–1465](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L1230-L1465)
und [11970–12120](https://github.com/dosordie/FoxAir_private/blob/main/DisplayFW/V1.7_original/DEMONS.ASM#L11970-L12120).

### Unit 1:2099–2149 und virtuelle IDs 91099–91149

Die 51 Kompatibilitäts-IDs bleiben erhalten und bilden eine eigene
Browsergruppe **Unit-1-Telemetrie**. `virtuell = INV1-Adresse + 89000` ist eine
interne FoxAir-Projektion, kein direkt adressierbarer Modbusbereich und kein
DWIN-Speicher. Quelle, virtuelle ID und optionale MAIN-Bezüge stehen getrennt
in Metadaten und Tooltips. Die MAIN-Werte werden durch die Projektion nicht
aktualisiert. MAIN8801 bleibt davon unabhängig.

| Virtuell | INV1 | Anzeige / MAIN-Bezug |
| --- | --- | --- |
| 91099 | 2099 | Driverstatus-Bitfeld / MAIN2080 |
| 91100 | 2100 | Driver-Fehlerwort 1 / MAIN2081; lokales MAIN-Kommunikationsbit 15 wird nicht als Driverbezeichnung übernommen |
| 91102 | 2102 | Low-Byte-Frequenz in Hz / MAIN2072; High-Byte bleibt im Rohwort sichtbar |
| 91103 | 2103 | Maximalfrequenz vom Driver, Hz / MAIN2073 |
| 91104 | 2104 | IPM-Hochfehler-Temperatur `RAW − 55 °C` / MAIN2061 |
| 91105 | 2105 | AC-Spannung in V / MAIN2062 |
| 91106/91107 | 2106/2107 | AC-/Phasenstrom `RAW/10 A` / MAIN2057/2042 |
| 91108 | 2108 | DC-Zwischenkreisspannung in V / MAIN2043 |
| 91109 | 2109 | Driver-Fehlerwort 2 / MAIN2082; MAIN-Kopie kann versionsabhängig bearbeitet sein |
| 91110 | 2110 | IPM-Temperatur `(RAW.lowbyte − 55) °C` / MAIN2044 |
| 91113 | 2113 | Gepacktes Wort mit getrenntem High-/Low-Byte / MAIN2026/2027 |
| 91118 | 2118 | Signed int16 / MAIN2028 |
| 91130/91142 | 2130/2142 | Fan 1-/Fan 2-Istwert in rpm / MAIN2074/2075 |

Beispiele für 91110: RAW 95→40 °C,100→45°C,107→52°C.
MAIN2044 enthält dagegen `(RAW.lowbyte−55)×10`. Die speziellen Offset-/Low-Byte-
Formatter gelten nur für die Unit-1-Metadaten; bestehende MAIN-TEMP1-Werte
werden dadurch nicht verändert. Unbekannte Wörter bleiben unsigned RAW.

Bedingt belegte Fan-Driver-Wörter 2123, 2133, 2135, 2136 werden mit expliziter
Profil-/Config4-Abgrenzung benannt. MAIN-Bezüge 2132/2130/2131 sind dokumentiert,
aber keine unbewiesene A-/W-/Temperaturskalierung für andere Profile übernommen.
Quellen: [Unit1-RX-Tabelle und Kodierungen](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/FW3.3-UNIT1-INVERTER-PROTOKOLL.md#12-rx-tabelle-20992149).

Aktive und passive Unit-1-Antworten verwenden dieselben Metadaten wie die
virtuelle Gruppe. Nur ein vollständiger CRC-gültiger 51-Wort-Block von Unit 1
wird projiziert; Teilblöcke und andere Units bleiben außerhalb der MAIN-Liste.
Die Projektion erfolgt auch bei einer zugeordneten manuellen Antwort vor der
allgemeinen MAIN-Übernahme. Read-/Write-Aktionen für 91xxx sind im Browser und
Kontextmenü gesperrt; die zentralen Sendewege verhindern direkte Drahtzugriffe.
Verlauf und Export behalten die bisherigen virtuellen IDs und Originalrohwörter.

### Ergänzte MAIN-Parameter

| Register | Änderung / gesicherte Grenze |
| --- | --- |
| 1017 | „Unbekannter Parameter“; aus automatischem Backup/Restore ausgeschlossen, auch beim Laden alter Backup-Dateien. Logoauswahl ist 1026/H39. Vorhandene manuelle Schreibrechte werden nicht erweitert. |
| 1193/1194 | Temperaturparameter R40/R41, Funktion unbekannt; TEMP1 und historischer60 °C-Grenzhinweis bleiben erhalten |
| 1381–1386 | „AT-Kurve Zone 2 – Stützpunkt 1–6“, bestätigt als gemeinsame Kennlinienfamilie; endgültige AT-Stützstellen und versionsabhängige Skalierung offen, daher unsigned RAW ohne Einheit |
| 1422 | Remote-Kompressor-Frequenzobergrenze (%), Default 70; wirksam im durch 2152 Bit 4 aktivierten Pfad. 0/>100 werden dort wie 100 % behandelt; keine neuen Schreibgrenzen |
| 1424 | Remote-Preset Heiz-Wassersollwert-Anhebung; RAW 20 beobachtet, physische Skalierung offen |
| 1430 | Freigabe Warmlink-8055-Heizboost; 0 sperrt dieses zusätzliche Gate. Engineering-Metadaten bleiben erhalten. |
| 1466 | Erweiterter Konfigurationsparameter, Funktion unbekannt; RAW 300 beobachtet, keine belegte Einheit |
| 1476 | R-/Temperaturregelparameter, Funktion unbekannt; RAW 5 beobachtet, spezielle Reglerfamilie nur Hinweis |

Die sechs Zone 2-Werte mit LTE/Warmlink-RAW 350 und Display-RAW 0 sind Beobachtungen
unterschiedlicher Datenpfade. Daraus folgen keine Unbenutztheit und keine
automatischen Synchronisations-/Schreibkorrekturen. Die endgültige lokale
Kennlinienfunktion ist laut zusätzlichem Registeraudit bestätigt, die sechs
AT-Stützstellen und Skalierungsdetails sind ausdrücklich nicht festgelegt.
Die ergänzende Beobachtung 2152=2 vor Start und 1 beim Anlaufen ist dokumentiert,
ändert die thermischen Bitnamen nicht und aktiviert in beiden Fällen Bit 4 nicht.
Remote-Belege: [V3.5 adaptive Inverterregelung](https://github.com/dosordie/FoxAir_private/blob/main/docs/reverse_engineering/firmware/V3.5/adaptive_inverter_control.md).

### Display-Parameter synchronisieren

Der bewährte ACK-gesteuerte Ablauf bleibt bestehen: FC16 an Unit 3,
`0x5112=0`, danach `0x0BC3=0x8000`, anschließend die vom Master gelieferten
Parameterpakete abwarten. Keine parallelen aktiven 90-Wort-Reads und keine
automatischen Teil-Syncs aus MAIN2109.

„Vollständig synchronisiert“ erfordert jetzt **alle sechs Pflichtpakete**
1001, 1091, 1181, 1271, 1361, 1451. Paket 1541 wird getrennt als optional gemeldet.
Jedes gezählte Paket muss seit dem aktuellen Trigger frisch eingegangen sein:
CRC gültig, Unit 3, exakt 90 Wörter, vollständige Payload, WF-Headerformat,
Marker 0x0210 und zum Start passende interne Startadresse. FC03-Antworten und
die bestehende FC16-/Word-Frame-Darstellung werden mit ihren jeweiligen
Payloadlängen berücksichtigt. Der Headerprüfer wird mit dem bisherigen
Displaydecoder geteilt, nicht durch ein neues Busprotokoll ersetzt.

Cachewerte und reine Sichtungszeitstempel reichen nicht. 4/6 bleibt Teil-Erfolg,
auch mit optionalem 1541; ein Timeout listet die fehlenden Pakete einzeln und
behält den tatsächlichen Fortschritt statt 100 %. Der erfolgreiche Sync-Cooldown
wird nur nach vollständig validiertem Empfang gesetzt. Laufende Parametrierung,
Restore-/Schreibwarteschlangen und Firmware-Capture verhindern den Start;
normale Parameterwrites werden während des Syncs blockiert. Ein Backendwechsel
verwirft den alten Sync-Zustand. Andere Backends behalten ihren bisherigen
Leseknopf und ihre Kommunikationswege.

### Dateien, Tests und Kompatibilität

Geändert: beide Registerkataloge und Knowledge-Datei, `.github/workflows/ci.yml`,
`core/foxair_phnix_core.py`, `core/bus_address_info.py`,
neu `core/display_protocol.py`, `foxair_phnix_control.py`,
`dialogs/offline_register_browser_dialog.py`, `ui/context_menu_helpers.py`,
`dialogs/backup_restore_policy.py`, `dialogs/backup_restore_dialog.py`,
`tests/test_backup_restore_policy.py`, neu `tests/test_display_register_audit.py`,
dieser Bericht, die Modbus-/Backup-FAQ und das Changelog.

Die Integrationstests verwenden synthetische FC03-/FC16-Frames und einen
simulierten Transport: Skalierungen, Fehlerwort-/Unittrennung, vollständige und
manuelle Unit-1-Projektion, DWIN-Masken/Enums/Objekte, virtuelle Adresssperren,
Header/CRC/Länge/Unit/Frische, 4/6 gegenüber 6/6, optionales Paket 1541, Teil-Timeout,
Schreib-/Capture-Sperren, Backendwechsel und 1017 in alten Backups.
Kein physischer Hardwarezugriff. Python-/JSON-Syntax und vorhandene
Regressionstests werden ebenfalls geprüft.
Der Zeitrahmen des vollständigen CI-Testschritts beträgt mit den zusätzlichen
GUI-Integrationstests jetzt 600 statt 300 Sekunden; einschließlich Installation
und vorbereitender Tests ist der Job auf 15 Minuten begrenzt.

Lokale Ergebnisse mit Python 3.12.14, PySide6 6.11.2 und Offscreen-Qt:

- Vollständiger wiederholter Lauf: **1487 bestanden in 492,78 Sekunden**.
- Abschließender Lauf von `tests/test_display_register_audit.py` auf dem finalen
  Stand einschließlich des zusätzlichen Header-Regressionstests:
  **44 bestanden in 45,51 Sekunden**.
- Zusätzlich nach der abschließenden Kompatibilitätskorrektur: Der gemeinsam
  genutzte Headerprüfer behält bei kurzen Diagnoseblöcken die tatsächliche
  Endadresse bei, verlangt für die Sync-Wertung aber weiterhin 90 Wörter;
  der neue gezielte Regressionstest besteht.
- Der erste Gesamtlauf endete mit einem nativen Qt-Segfault im bestehenden
  SIM-Gerätewechseltest. Dessen Modul bestand anschließend isoliert mit
  **18 Tests**, ebenso der vollständige wiederholte Lauf. Die Ursache des
  einmaligen nativen Absturzes wurde damit nicht abschließend bestimmt.
- Python-Kompilierung, JSON-/Katalogvalidierung und `git diff --check`: bestanden.
  Kein bestehendes Register entfernt, keine MAIN-/DWIN-Adresskollision und
  keine Änderung bestehender Schreibrechte oder Schreibgrenzen.

Sichtbare Änderungen: 1017 wird nicht mehr automatisch gesichert/restauriert;
die virtuellen IDs zeigen jetzt bestätigte Engineering-Werte bei unverändertem
Rohwort; Sync-Erfolg wird strenger bewertet. Externe Auswertungen, die die alte
falsche 91110-RAW-Anzeige als Temperatur oder 4/6 als vollständigen Upload
behandelten, müssen diese Korrekturen berücksichtigen. OEM-Namen unbekannter
Driverbits, restliche DWIN-Wörter, RTC-Tagesnamen, Zone 2-Stützstellen/-Skalierung
sowie Funktionen 1466/1476 bleiben offen.
