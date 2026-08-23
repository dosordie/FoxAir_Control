# PHNIX/FoxAir LTE- und Mainboard-OTA – Workchat-Übergabe

Stand: 23. August 2026

Repository: `dosordie/FoxAir_Control`

Diese Datei fasst den aktuellen, korrigierten Arbeitsstand der LTE-/Mainboard-OTA-Analyse zusammen. Frühere Annahmen einer Mainboard-Linkbasis `0x08080000` und eines zwingend separaten Phase-A-IAP-Images sind überholt.

## 1. Wichtigste Korrektur

Die bekannte V3.3-Datei:

```text
Größe:          287598 Byte
MD5:            CEB6A4BF386FF644E23E410023E74673
SHA-256:        6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
Softwarecode:   82400644
Version intern: 0033
Anzeige:        V3.3
```

ist **für `0x08050000` gelinkt**.

Vector Table:

```text
BIN+0x00 = 0x2000EB90
BIN+0x04 = 0x080927D1
```

Mit Basis `0x08050000` liegt der Reset Handler bei Datei-Offset `0x427D0`; dort befindet sich tatsächlich der Startupcode.

Weitere Belege:

- BIN-Offset `0xB0` enthält `0x08053747`, passend zur Basis `0x08050000`.
- `824006440033` liegt bei BIN-Offset `0x42780` = Adresse `0x08092780`; genau diese Adresse nutzt der C544-Code.
- die Firmware setzt `SCB->VTOR = 0x08050000`.
- ein direkter Chain-Jump lädt MSP/PC aus `0x08050000/0x08050004`.

Damit ist die frühere Interpretation `0x08080000 = Main-App-Linkbasis` widerlegt. `0x08080000` ist eine Flash-/Page-Grenze innerhalb des Updatefensters, kein bestätigtes Bootziel.

## 2. Dynamisch bestätigter LTE→Board-Transport

Der originale ARM-Prozess `phnixIot4G` wurde in einer isolierten QEMU-/Loopback-Umgebung ausgeführt.

Bestätigt wurden:

- C350
- C357
- C5A8
- C36E-Auswertung
- C371-Auswertung
- C544/C37B
- vollständiger V3.3-Blockstrom

Der vollständige C5A8-Test ergab:

```text
C5A8-Frames:              1712
rekonstruierte Nutzbytes: 287598
SHA-256:                  6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Damit ist dynamisch bewiesen:

> **Das vom originalen LTE-Prozess über C5A8 gesendete Image ist bytegenau die bekannte V3.3-Datei.**

Der letzte Block enthält 150 reale Bytes plus 18 × `0xFF` Padding.

## 3. Reales C544

Live empfangen:

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
SSID:             0063
Hardwarecode:     82300314
Hardwareversion:  0000
Softwarecode:     82400644
Softwareversion:  0033 / V3.3
```

LTE-Antwort:

```text
63 10 C3 7B 00 02 04 00 63 00 07 B5 A8
```

Mainboard-ACK:

```text
63 10 C3 7B 00 02 05 D7
```

## 4. RS485-OTA-Protokoll

Grundparameter:

```text
Slave:       0x63
Funktion:    0x10
Baudrate:    9600
Format:      8N1
CRC:         Modbus CRC16, Low-Byte zuerst
Blockgröße:  168 Byte
```

Relevante Register:

| Register | Bedeutung |
|---:|---|
| `C350` | Ziel-Softwarecode/-version |
| `C357` | Dateigröße und MD5 |
| `C36A` | Cancel |
| `C36C` | Cancel-Bestätigung |
| `C36E` | Board-OTA-Status |
| `C371` | Block-ACK |
| `C37B` | Status-ACK |
| `C5A8` | Firmwaredatenblock |
| `C544` | laufende Hardware-/Softwarecodes |

### C350 V3.3

```text
63 10 C3 50 00 07 0E 00 63
38 32 34 30 30 36 34 34
30 30 33 33
59 4D
```

### C357

Überträgt SSID, Dateigröße und MD5.

### C5A8

Bei 168 Byte Blockgröße:

```text
SSID_BE16
total_blocks_BE16
current_block_BE16
firmware_data[168]
```

### C371

```text
SSID_BE16
ackA_BE16   = 1
ackB_BE16   = 1 weiterer Block / 2 letzter Block
block_BE16
```

Der echte Mainboard-Endpfad verwendet am letzten Block `ackB=2`; der LTE-Prozess setzt seinen Offset dadurch direkt auf `fileSize = 287598`.

## 5. Mainboard-OTA-Pfad – korrigierter Stand

Die wichtigsten Mainboard-Codeadressen sind wegen der korrigierten Imagebasis `0x08050000` jeweils `0x30000` niedriger als in frühen Notizen.

Beispiele:

```text
C350 RX       0x08067CE4
C357 RX       0x08067D30
C5A8 RX       0x08068108
C36E Sender   0x08068BDC
C371 Sender   0x08068CE2
Commitworker  0x08076848
Copy/Erase    0x080770EC
C5A8 Worker   0x08078628
Transition    0x08079040
Jumpworker    0x08079354
MD5           0x0807964C
Role setter   0x080763E2
```

Ablauf:

```text
C350
→ Ziel/Build prüfen
→ C36E 0 oder 1

C357
→ Länge/MD5 übernehmen
→ EEPROM-Ready-State
→ C36E 2

C5A8 × N
→ RAM-Staging
→ Flash-Staging ab 0x080A1000
→ C371 pro committed Block

letzter Block
→ MD5 über 0x080A1000
→ C36E 3 bei Erfolg / 4 bei Fehler

Descriptor
0x080A0000 → 0x0804F800

Erase/Copy
0x080A1000 → 0x08050000

zweiter MD5 über 0x08050000
→ Commit/EEPROM
→ C36E 5 bei erfolgreichem späteren Commit
→ Status 6 bei Post-Copy-/Commitfehlern

Jump
MSP = [0x08050000] = 0x2000EB90
PC  = [0x08050004] = 0x080927D1
```

## 6. Keine Relocation / kein separates Phase-A-Image erforderlich

Der Copy-Pfad ist eine direkte Word-für-Word-Kopie. Es wurde dort gefunden:

- keine Dekompression
- keine Relocation
- keine Pointerkorrektur
- keine Headerentfernung

Da die bekannte V3.3-Datei selbst für `0x08050000` gebaut ist, ist der direkte Jump nach der Copy korrekt.

Die frühere Hypothese:

```text
kleines Phase-A-IAP @ 0x08050000
→ danach Main-App @ 0x08080000
```

ist in dieser Form **widerlegt**.

Ein separates unbekanntes Phase-A-Image muss nicht mehr angenommen werden.

## 7. Flashbereiche

```text
0x08000000   residenter Loader/Recovery
0x0804F800   persistenter 64-B-Descriptor
0x08050000   Image-/Vectorbasis der V3.3
0x08080000   Flash-/Page-Grenze innerhalb des Updatefensters
0x080A0000   Staging-Descriptor
0x080A1000   Staging-Firmware
```

Großer Erase-Bereich:

```text
0x08050000 … 0x0809BFFF
```

Maximale Image-/Copy-Länge:

```text
0x4B000 = 307200 Byte
```

## 8. Persistente Mainboard-OTA-Zustände

Im externen I²C-EEPROM wurden CRC-geschützte Records gefunden:

```text
0x3D8   Role-State 1/2
0x3E0   Transition-/Recovery-State
0x3E8   Candidate-/Commit-State
0x3F0   C357-/Download-Ready-State
```

`0x080763E2(1)` setzt Role 1 und schreibt Role + CRC nach EEPROM `0x3D8`; `0x080763E2(2)` setzt Role 2.

Die genaue Herstellerbezeichnung von Role 1/2 ist offen. Sehr wahrscheinlich gilt:

```text
Role 2 = normale Anwendung
Role 1 = Loader/Promotion/Recovery
```

## 9. Vortest-Sicherheitsgrenze

Für einen abbrechbaren Handshake ohne Firmwaredaten gilt weiterhin:

```text
C5A8 niemals senden
```

C350 bleibt RAM-basiert. Status 0 ist kein globaler OTA-Reset, verursacht aber selbst keine neuen Flash-/EEPROM-Schreibzugriffe. Für C350 Status 1 ohne C357 wurde kein eigener Mainboard-Wartetimeout gefunden.

C357 setzt EEPROM `0x3F0`, schreibt aber noch keine Firmwaredaten. Ein frühes C36A setzt `0x3F0` zurück; der Flash-Erase-Zweig ist vor C5A8 nicht erreichbar.

Details: [`FW3.3-OTA-VORTEST-SICHERHEIT.md`](FW3.3-OTA-VORTEST-SICHERHEIT.md).

## 10. Neue Promotion-/Recovery-Erkenntnis

Der Transitionworker `0x08079040` enthält **zwei getrennte 600-Zyklen-Gates**.

Ein Gate setzt bei Erreichen von `600`:

```text
Erasecounter = 124
```

und startet damit den großen Target-Erase.

Ein anderer Gate-Pfad persistiert zuerst Transitiondaten nach EEPROM `0x3E0`. Bei exakt `600` passiert anschließend:

```text
0x080763E2(1)      # Role 1 + CRC -> EEPROM 0x3D8
Boot-Control +0x42 = 0
Boot-Control +0x22 = 1
```

`+0x22` ist der Eingang des Jumpworkers für den residenten Loader:

```text
MSP = [0x08000000]
PC  = [0x08000004]
BLX PC
```

Damit ist nun direkt belegt, dass vor mindestens einem kritischen OTA-Übergang:

1. Transition-State persistent gespeichert wird,
2. Role 1 persistent gespeichert wird,
3. anschließend ein Chain-Jump zum residenten Loader `0x08000000` vorbereitet wird.

## 11. Verbleibende harte Unsicherheit

Der Promotionworker `0x080770EC` liegt selbst im später zu löschenden Bereich. Ebenso liegen die verwendeten Flash-Helfer:

```text
0x0808D144
0x0808D190
0x0808D1C0
0x0808D2E4
```

innerhalb des Target-Erasebereichs `0x08050000..0x0809BFFF`.

Für eine vollständige reale Promotion kann dieser Code daher nicht ausschließlich aus der gerade zu löschenden Imageinstanz ausgeführt werden.

Gezielte Suche im bekannten V3.3-Binary ergab keinen belastbaren Nachweis für:

- RAM-Kopie des Promotionworkers,
- RAM-Kopie der Flash-Helfer,
- `BLX` auf einen SRAM-Trampolinpfad,
- Startup-Copy-Tabelle, die genau diesen Code nach RAM verlagert.

Die persistente Role-1-/Transition-Sequenz und der direkte Loader-Handoff sprechen deshalb jetzt **stark** dafür, dass der residente Loader `0x08000000` den sicheren Promotion-/Recoverykontext bereitstellt oder mindestens steuert.

Was ohne dessen Dump weiterhin nicht bewiesen werden kann:

- ob er selbst Target-Erase/Copy ausführt,
- ob er eine unterbrochene Promotion vollständig neu startet,
- ob ein teilweise geschriebenes Target niemals nur aufgrund eines gültigen Vector Tables gebootet wird,
- welche Commit-/MD5-/Descriptorbedingungen er beim Power-on verlangt,
- wie er auf Power-Loss während Erase oder Copy reagiert.

Genau dieser Loader-/Power-Loss-Punkt ist inzwischen der wesentliche Sicherheitsblocker für einen echten vollständigen OTA-Test.

Vollständige Analyse und Power-Loss-Matrix:
[`FW3.3-OTA-PROMOTION-RECOVERY.md`](FW3.3-OTA-PROMOTION-RECOVERY.md).

## 12. Wichtige Detaildokumente

- [`FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md`](FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md)
- [`FW3.3-OTA-ERKENNTNISSE.md`](FW3.3-OTA-ERKENNTNISSE.md)
- [`FW3.3-OTA-PROMOTION-RECOVERY.md`](FW3.3-OTA-PROMOTION-RECOVERY.md)
- [`FW3.3-OTA-VORTEST-SICHERHEIT.md`](FW3.3-OTA-VORTEST-SICHERHEIT.md)
- [`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md)

## 13. Sicherheitsregel für weitere Arbeit

Ohne ausdrückliche Freigabe:

- nichts an die reale Wärmepumpe senden,
- keinen realen ser2net-/RS485-Endpunkt öffnen,
- nichts an die PHNIX-Cloud senden,
- keine Firmware flashen,
- keine Dateien oder Prozesse auf dem LTE-Modem verändern.

Offline-Analyse, Capturevergleich und Simulation bleiben der Standard.