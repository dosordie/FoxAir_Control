# PHNIX Board-OTA – dynamische Validierung mit V3.3 und Live-Warmlink

Stand: 23. August 2026

Dieses Dokument fasst die dynamischen Versuche zusammen, die zusätzlich zur statischen Analyse von `phnixIot4G` und der Mainboard-Firmware `82400644 / V3.3` durchgeführt wurden.

> **Korrigierter Mainboardbezug:** Die bekannte V3.3-Datei ist für `0x08050000` gelinkt. Die dynamisch beobachteten 1712 C5A8-Blöcke rekonstruieren exakt diese Datei. Damit bestätigt die Transportanalyse unabhängig, dass kein separates vorgeschaltetes Phase-A-IAP-Image nötig ist, um den beobachteten C5A8-Strom zu erklären.

## 1. Referenzdatei V3.3

```text
Dateigröße: 287598 Byte
MD5:        CEB6A4BF386FF644E23E410023E74673
SHA-256:    6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
Software:   82400644 / intern 0033 / Anzeige V3.3
SSID:       0063
Imagebasis: 0x08050000
Initial MSP:    0x2000EB90
Reset Handler:  0x080927D1
```

Die Vector-/Rebasing-Analyse ist separat dokumentiert in [`FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md`](FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md).

## 2. Cache-Lebenszyklus

Die Datei `/cache/phnixIot_device_OTA` bleibt nach einem erfolgreichen Board-OTA auf dem LTE-Modem erhalten. Erst ein später angenommenes Cloudkommando `0033` löscht die Cachedatei und leert `/data/phnixIot_device_OTA_INFO`, bevor ein neuer Download beginnt.

Damit konnte die echte V3.3-Referenzdatei nachträglich vom LTE-Modem gesichert werden.

## 3. Isolierte Ausführungsumgebung

Das originale ARM-Programm `phnixIot4G` wurde unter QEMU in einem separaten Netzwerk-Namespace ausgeführt. Es gab keine IPv4-/IPv6-Defaultroute.

Lokal ersetzt wurden:

- SIMCom-AT-Port
- QMI/QMUX/NAS/UIM
- Credential-HTTP
- TLS/MQTT
- Firmware-HTTP
- RS485-Mainboard über PTY-Emulator

Damit konnte der originale OTA-Codepfad ohne reale Cloud, reales LTE-Modem oder reale Wärmepumpe ausgeführt werden.

## 4. Dynamisch bestätigter C350-Request

Der originale Prozess sendet für V3.3 die interne Version `0033`:

```text
63 10 C3 50 00 07 0E 00 63
38 32 34 30 30 36 34 34
30 30 33 33
59 4D
```

Damit sind SSID `0063`, Softwarecode `82400644` und interne Version `0033` bytegenau bestätigt.

## 5. Kontrollierter Downloadtest

Ein lokaler synthetischer `0033`-Datensatz enthielt die echten V3.3-Metadaten und eine Loopback-HTTP-Adresse.

Ablauf:

```text
C350
→ synthetische C350-Bestätigung
→ C36E Status 1
C357
→ synthetische C357-Bestätigung
→ C36E Status 2
→ lokaler HTTP-Download
→ interne MD5-Prüfung
→ board_ota_step 6
```

Der erste Lauf stoppte unmittelbar vor `set_update_board_bin_by_485()`. Die heruntergeladene Datei war bytegleich zur V3.3-Referenz.

## 6. Vollständiger C5A8-Labortest

Ein zweiter isolierter Lauf ließ den originalen LTE-Prozess alle Firmwareblöcke an den Emulator senden.

Der Emulator prüfte:

- Modbus-CRC
- SSID `0x0063`
- Gesamtblockzahl `1712`
- lückenlose Blocknummern
- Blockgröße 168 Byte
- Nutzdaten bytegleich zur Referenzdatei

Ergebnis:

```text
C5A8-Frames:              1712
rekonstruierte Nutzbytes: 287598
SHA-256:                  6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Der letzte Block:

```text
offset_before:    287448
echte Nutzdaten:  150 Byte
Padding:          18 × FF
Blockrahmen:      168 Byte
```

### Konsequenz aus statischer + dynamischer Analyse

Der C5A8-Datenstrom ist **exakt** die bekannte V3.3-Datei. Da diese Datei nach korrigierter statischer Analyse für `0x08050000` gelinkt ist und dort eine gültige Vector Table besitzt, ist der beobachtete Transport vollständig konsistent mit:

```text
C5A8
→ Staging ab 0x080A1000
→ direkte Copy nach 0x08050000
→ MD5
→ Chain-Jump über Vector Table 0x08050000
```

Die frühere Annahme eines zwingend separaten kleinen Phase-A-IAP-Images ist damit nicht mehr erforderlich.

## 7. Finalblock und ACK-Abgrenzung

Ein absichtlicher LTE-Handler-Grenztest verwendete auch am letzten Block `ackB=1`:

```text
offset_after_ack = 287448 + 168 = 287616
```

Das war ein synthetischer Boundary-Test.

Der echte Mainboardpfad sendet am letzten Block:

```text
ackB = 2
```

Dadurch setzt das LTE-Modem den persistenten Endoffset direkt auf:

```text
fileSize = 287598
```

Die Werte 287616 und 287598 sind deshalb keine widersprüchlichen Beobachtungen.

## 8. C36E-Wireformat

Die echte V3.3-Mainboard-Firmware baut C36E mit zwei Registern bzw. vier Nutzbytes:

```text
SSID_BE16
status_BE16
```

Die im Labor zusätzlich verwendete 6-Byte-Variante war eine handler-kompatible synthetische Erweiterung und kein behauptetes echtes Mainboard-Wireformat.

## 9. Reales C544

Ein Live-Read auf Register `0x0004` führte später zu einem echten C544:

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
Softwareversion:    0033 / V3.3
```

LTE-Antwort:

```text
63 10 C3 7B 00 02 04 00 63 00 07 B5 A8
```

Mainboard-ACK:

```text
63 10 C3 7B 00 02 05 D7
```

Damit sind C544-Layout und C37B/status-7 dynamisch bestätigt.

## 10. Mainboard-Flashpfad – dynamische Einordnung

Die statische Mainboardanalyse ergibt inzwischen:

```text
C5A8-Daten → Flash-Staging ab 0x080A1000
letzter Block → MD5 #1
Descriptor 0x080A0000
Image-Copy → 0x08050000
MD5 #2 → Candidate-/Commitzustände
C36E 5 → später Handoff
```

Die bekannte BIN besitzt:

```text
[0x08050000] = 0x2000EB90
[0x08050004] = 0x080927D1
```

und ist deshalb unverändert bei `0x08050000` ausführbar.

Ein direkter Jump nach `0x08080000` wurde in der V3.3-App nicht gefunden.

## 11. Persistenz auf LTE-Seite

Ein angenommenes `0033` verändert:

```text
/data/phnixIot_device_statisic
/data/phnixIot_device_OTA_INFO
```

Die ursprüngliche `OTA_INFO` wurde nach den Labortests wiederhergestellt.

## 12. Unabhängiger Sender

[`devtools/phnix_ota_sender.py`](../../devtools/phnix_ota_sender.py) erzeugt offline den V3.3-Bytestrom.

Alle 1714 Requests – C350, C357 und 1712 C5A8-Frames – wurden bytegenau und in gleicher Reihenfolge im Originalcapture gefunden.

Der Sender öffnet standardmäßig keine reale Verbindung und stoppt absichtlich vor der Abschluss-/Commitphase.

## 13. Sicherheitsgrenze

Die dynamische Transportvalidierung beweist die Bytefolge, aber nicht die vollständige Recovery-Sicherheit eines echten Schreibupdates.

Weiter offen bleibt vor allem der residente Loader bei `0x08000000`:

- Power-Loss-Recovery
- genaue Role-State-Bootentscheidung
- Verhalten bei unterbrochener Erase/Copy-Phase
- automatischer Recovery-/Fallbackpfad

Daher bleibt ein unbeaufsichtigter echter OTA-Test ohne Hardware-Recovery nicht als sicher bestätigt.

## 14. Zugehörige Dokumente

- [`FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md`](FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md)
- [`FW3.3-OTA-ERKENNTNISSE.md`](FW3.3-OTA-ERKENNTNISSE.md)
- [`FW3.3-OTA-VORTEST-SICHERHEIT.md`](FW3.3-OTA-VORTEST-SICHERHEIT.md)
- [`PHNIX_OTA_WORKCHAT_UEBERGABE.md`](PHNIX_OTA_WORKCHAT_UEBERGABE.md)
