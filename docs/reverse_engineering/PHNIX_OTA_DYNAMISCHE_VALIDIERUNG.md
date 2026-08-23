# PHNIX Board-OTA – dynamische Validierung mit V3.3 und Live-Warmlink

Stand: 23. August 2026

Dieses Dokument fasst die dynamischen Versuche zusammen, die zusätzlich zur statischen Analyse von `phnixIot4G` und der Mainboard-Firmware `82400644 / V3.3` durchgeführt wurden. Eindeutige Cloud-/Geräteidentitäten und Zugangsdaten sind bewusst nicht enthalten.

## 1. Referenzdatei V3.3

Die vom LTE-Modem gesicherte Mainboard-Firmware besitzt:

```text
Dateigröße: 287598 Byte
MD5:        CEB6A4BF386FF644E23E410023E74673
SHA-256:    6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
Software:   82400644 / intern 0033 / Anzeige V3.3
SSID:       0063
```

Die Datei wird nach einem erfolgreichen Board-OTA nicht automatisch aus
`/cache/phnixIot_device_OTA` entfernt. Erst ein später angenommenes Cloudkommando
`0033` löscht die alte Cachedatei und leert `/data/phnixIot_device_OTA_INFO`, bevor
der neue Download beginnt. Das erklärt, warum die V3.3-Datei nach dem früheren
Update noch vom LTE-Modem kopiert werden konnte.

## 2. Isolierte Ausführungsumgebung

Das originale ARM-Programm `phnixIot4G` wurde unter QEMU in einem separaten
Linux-Netzwerk-Namespace ausgeführt. Innerhalb dieses Namespace existierten nur
Loopback und lokale Ersatzdienste; es gab keine IPv4-/IPv6-Defaultroute.

Ersetzt wurden ausschließlich die externen Gegenstellen:

- SIMCom-AT-Port,
- QMI/QMUX einschließlich NAS-Registrierung und UIM/USIM-Status,
- Linked-Go-Credential-HTTP,
- TLS/MQTT,
- Firmware-HTTP-Server,
- RS485-Mainboard durch einen PTY-basierten Emulator.

Damit lief der originale OTA-Codepfad, ohne PHNIX-Cloud, reales LTE-Modem oder
reales Mainboard zu erreichen.

## 3. Dynamisch bestätigter C350-Request

Der originale Prozess sendet für V3.3 nicht `"V3.3"`, sondern die interne
Vierzeichendarstellung `"0033"`:

```text
63 10 C3 50 00 07 0E 00 63
38 32 34 30 30 36 34 34
30 30 33 33
59 4D
```

Das vollständige Frame ist damit bytegenau dynamisch bestätigt.

## 4. Kontrollierter Downloadtest

Ein lokales synthetisches `0033` enthielt die echten V3.3-Metadaten und eine
Loopback-HTTP-Adresse. Der originale Prozess durchlief:

```text
C350
 -> synthetische C350-Bestätigung
 -> synthetisches C36E Status 1
C357
 -> synthetische C357-Bestätigung
 -> synthetisches C36E Status 2
 -> lokale HTTP-Anfrage
 -> Download
 -> interne MD5-Prüfung
 -> board_ota_step 6
```

Der erste Lauf stoppte bei `0x1D9E8` vor `set_update_board_bin_by_485()`.
Die heruntergeladene Datei war bytegleich zur Referenzdatei; Größe, MD5 und
SHA-256 stimmten überein. Es wurde noch kein C5A8 gesendet.

## 5. Vollständiger C5A8-Labortest

Ein weiterer isolierter Lauf ließ den originalen LTE-Prozess alle Firmwareblöcke
an den Emulator senden. Der Emulator akzeptierte einen Block nur, wenn folgende
Werte korrekt waren:

- Modbus-CRC,
- SSID `0x0063`,
- Gesamtblockzahl `1712`,
- lückenlose aktuelle Blocknummer,
- Blockgröße 168,
- Nutzdaten bytegleich zur V3.3-Referenz einschließlich Final-Padding.

Ergebnis:

```text
C5A8-Frames:              1712
rekonstruierte Nutzbytes: 287598
SHA-256:                  6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Der letzte Block wurde dynamisch beobachtet als:

```text
offset_before:    287448
echte Nutzdaten:  150 Byte
Padding:          18 × FF
Blockrahmen:      weiterhin 168 Datenbytes
```

### 5.1 Abgrenzung des getesteten End-ACKs

Der Emulator sendete im dokumentierten Grenztest auch für Block 1712 ein
`C371 ackB=1`. Dadurch führte der LTE-Handler aus:

```text
offset_after_ack = 287448 + 168 = 287616
```

Im genau nächsten Worker-Durchlauf erkannte `set_board_update_bin()`
`file_len <= file_offset`, lieferte 0 und erreichte den Guard `0x1D9F8`
unmittelbar vor `board_ota_step 6 -> 12`:

```text
board_ota_step:       6
persistierter Offset: 287616
persistierte Länge:   287598
```

Dieser Wert `287616` ist ein bewusster `ackB=1`-Grenztest des LTE-Handlers und
**nicht der inzwischen statisch bewiesene normale Endpfad des echten V3.3-Mainboards**.
Die Mainboard-Firmware sendet beim letzten Block `ackB=2`; der LTE-Handler setzt
dann den Offset direkt auf `fileSize`, also `287598`.

Der Guard stoppte vor Step 12. Der Emulator sendete kein C36E Status 5. Es gab
daher weder C37B-Abschluss, Step 5, MQTT-Code 0053, Installation noch Neustart.

## 6. Synthetische und echte C36E-Länge

Für die Laborhandshakes wurden handler-kompatible C36E-Frames mit sechs
Nutzbytes verwendet. Dadurch wurde die optionale Blockgröße 168 explizit in
`data[4:5]` übertragen.

Die später analysierte Mainboard-Firmware V3.3 baut C36E dagegen mit zwei
Registern beziehungsweise vier Nutzbytes. Sie setzt sicher SSID-low und Status;
eine Blockgröße ist in diesem Builder nicht enthalten. Im echten Zusammenspiel
verwendet das LTE-Modem daher voraussichtlich seinen Default 168.

## 7. Einmaliger Live-Read 0x0004 über ser2net

Auf dem realen Warmlink-/LTE-Bus wurde nach einem fünf Sekunden langen
Ruhefenster exakt einmal und ohne Retry gesendet:

```text
63 03 00 04 00 01 CD 89
```

Darauf folgten die acht bekannten 90-Register-Paketblöcke des Mainboards:

```text
03E9, 0443, 049D, 04F7, 0551, 05AB, 07D1, 082B
```

Das LTE-Modem bestätigte die FC10-Blöcke jeweils mit dem passenden acht Byte
langen FC10-Responseframe. Rund 49 Sekunden nach dem Read folgte ein echtes
C544. Damit ist `0x0004` auf dem untersuchten Mainboard praktisch als Trigger
für einen vollständigen Device-Info-/Paketzyklus einschließlich späterem C544
belegt; nicht nur als isolierter Ein-Register-Wert.

## 8. Bytegenaues reales C544

Das live empfangene C544 lautet:

```text
63 10 C5 44 00 0D 1A
00 63
38 32 33 30 30 33 31 34
30 30 30 30
38 32 34 30 30 36 34 34
30 30 33 33
CC F0
```

Dekodiert:

```text
SSID:               0063
Hardwarecode:       82300314
Hardwareversion:    0000
Softwarecode:       82400644
Softwareversion:    0033 / Anzeige V3.3
```

Das LTE-Modem antwortete unmittelbar mit dem statisch vorhergesagten
C37B/status-7-Frame:

```text
63 10 C3 7B 00 02 04 00 63 00 07 B5 A8
```

Das Mainboard bestätigte dieses FC10-Frame anschließend mit:

```text
63 10 C3 7B 00 02 05 D7
```

Damit sind C544-Layout, interne Version `0033`, Anzeigeableitung `V3.3` und die
C37B/status-7-Quittung dynamisch bestätigt. Der daraus folgende MQTT-Report
`0003` ist aus dem LTE-Code statisch bewiesen, wurde bei diesem reinen
RS485-Mitschnitt aber nicht gleichzeitig auf MQTT aufgezeichnet.

Der zu diesem C544 gehörende Original-`0003`-Datensatz ist damit inhaltlich:

```text
deviceSoftwareCode: 82400644
deviceSoftwareVer:  V3.3
ssid:               0063
```

Die Zeichenfolge `0033` bezeichnet hier die interne Softwareversion und zugleich
den MQTT-Antwortcode für ein Firmwareangebot; sie ist nicht die SSID dieses
Boards.

### 8.1 Kontrollierte aktive Cloudtests

Manuelle, syntaktisch gültige `0003`-Versionsberichte wurden während der
vorangegangenen Liveanalyse aktiv auf `OTA_UPDATE` gesendet. In den
kontrollierten Beobachtungsfenstern kam keine `OTA_GET`-/`0033`-Antwort zurück.
Damit wurde weder eine V3.4-Zuweisung noch eine Download-URL beobachtet. Das
negative Ergebnis beweist nicht, dass kein Paket existiert; es zeigt nur, dass
die Cloud dem verwendeten Geräteprofil bei diesen Anfragen keines anbot.

## 9. Nachbeobachtung und OTA-Abgrenzung

Nach dem Live-C544 wurde weitere 120 Sekunden ausschließlich passiv mitgehört.
Es kamen keine weiteren RS485-Bytes. Insbesondere erschienen keine Frames für:

```text
C350, C357, C36E, C371 oder C5A8
```

Der einmalige `0x0004`-Read löste somit den Informations-/C544-Pfad aus, aber
keinen beobachtbaren OTA-Start.

## 10. Persistenz und Laborbereinigung

Ein angenommenes `0033` verändert zwei getrennte Dateien:

```text
/data/phnixIot_device_statisic   # unter anderem OTA-SSID
/data/phnixIot_device_OTA_INFO   # MD5, Zielcode/-version, Offset, Länge, CRC
```

Nach den isolierten Tests wurde die gesicherte ursprüngliche `OTA_INFO`
bytegenau wiederhergestellt; ihr SHA-256 lautet:

```text
F5E31095C7366C4245A97F2EEAFEF76B2A4774405F589D0E8D5578A5B62136BB
```

Die im Labor erzeugte Cachedatei wurde entfernt. Für die Statistikdatei lag
keine ursprüngliche Vor-Test-Kopie vor; sie wurde deshalb nicht mit geratenen
Werten überschrieben. Ihr Laufzeitzustand ist nicht Teil des Firmwareartefakts.

## 11. Konsequenz für einen echten OTA-Test

Die Transportseite ist weitgehend dynamisch bestätigt. Das beweist jedoch noch
nicht die Sicherheit einer echten Installation. Die Mainboardanalyse zeigt,
dass C371 erst nach dem Flash-Commit eines Blocks gesendet wird und dass nach der
Datenphase weitere MD5-, Descriptor-, Slot-/Copy- und Bootloaderpfade folgen.

Vor einem echten OTA bleiben deshalb der Loaderdump, Backup der relevanten
Flashbereiche und ein funktionierender Hardware-Recoveryweg die zentralen
Sicherheitsvoraussetzungen. Außerdem läuft das reale Board bereits mit
`82400644 / 0033`; ein erneuter V3.3-Transfer ist aufgrund des C350-Vergleichs
kein sicher bestätigter normaler Upgradefall.

## 12. Zugehörige Detailanalysen

- [`FW3.3-OTA-ERKENNTNISSE.md`](FW3.3-OTA-ERKENNTNISSE.md)
- [`PHNIX_phnixIot4G_C544_softcode_resume.md`](PHNIX_phnixIot4G_C544_softcode_resume.md)
- [`PHNIX_phnixIot4G_ota_rs485_frames.md`](PHNIX_phnixIot4G_ota_rs485_frames.md)
- [`PHNIX_phnixIot4G_board_ota_http_download.md`](PHNIX_phnixIot4G_board_ota_http_download.md)
- [`PHNIX_phnixIot4G_ota_persistence.md`](PHNIX_phnixIot4G_ota_persistence.md)
- [`PHNIX_phnixIot4G_board_ota_completion.md`](PHNIX_phnixIot4G_board_ota_completion.md)
