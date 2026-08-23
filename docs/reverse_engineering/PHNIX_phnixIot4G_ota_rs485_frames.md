# PHNIX `phnixIot4G` – OTA-RS485-Frames C350 / C357 / C36E / C371 / C5A8

Stand: 2026-08-23

Grundlage ist die statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`, ergänzt um dynamisch bestätigte Frames aus dem vollständig isolierten Laborlauf.

## 1. CRC-Reihenfolge auf dem Draht

`crc16()` liegt bei `0x137C8`. Die Funktion berechnet den üblichen Modbus-CRC16 mit Initialwert `0xFFFF`, gibt den 16-Bit-Wert jedoch bereits bytevertauscht zurück:

```text
return = (crc_low << 8) | crc_high
```

Die Framebauer schreiben anschließend:

```text
(crc >> 8) & 0xFF
crc & 0xFF
```

Dadurch erscheinen auf dem Draht die üblichen Modbus-Bytes:

```text
CRC low byte, dann CRC high byte
```

Beispiel:

```text
63 03 00 04 00 01 CD 89
```

Standard-Modbus-CRC über `63 03 00 04 00 01` = `0x89CD`, Drahtfolge `CD 89`.

Wichtig: Die Disassembly wirkt auf den ersten Blick wie `HIGH, LOW`, weil `crc16()` selbst bereits bytevertauscht zurückgibt. Auf dem Draht bleibt es Modbus-konform `LOW, HIGH`.

---

## 2. Welche Bytes die OTA-Handler tatsächlich erhalten

`unpack_mcu_modbus()` bei `0x1DDE8` übergibt bei den lokalen OTA-FC10-Registern:

```c
handler(&frame[7], quantity * 2);
```

Die Handler sehen daher nur den Datenbereich:

```text
r0 = &frame[7]
r1 = quantity * 2
```

Slave, FC, Register, Quantity, Bytecount und CRC werden vorher verarbeitet und nicht an die Handler weitergereicht.

---

# C350 – Softwarecode + intern kodierte Softwareversion

## 3. Wo die Version `V3.3` zu `0033` wird

Die Cloud-`0033`-Metadaten enthalten `softwareVer = "V3.3"`. `ota_device_set_ota_file_download_info()` bei `0x18DB8` erzeugt daraus für den RS485-Pfad eine eigene vierstellige Darstellung.

Die relevante Transformation liegt bei `0x18F18..0x18F64`:

```c
otaDeviceInfo.version485[0] = '0';
otaDeviceInfo.version485[1] = '0';
otaDeviceInfo.version485[2] = softwareVer[1];
otaDeviceInfo.version485[3] = softwareVer[3];
```

Für:

```text
softwareVer = "V3.3"
```

entsteht:

```text
version485 = "0033"
```

`dtu_set_devver_by_485()` bei `0x1C740` ruft anschließend auf:

```c
set_sev_code_and_ver(
    &otaDeviceInfo.softwareCode[0],   // 0x933AC
    &otaDeviceInfo.version485[0]      // 0x933B5
);
```

Damit ist statisch eindeutig: **C350 sendet in diesem Build nicht ASCII `V3.3`, sondern `0033`.**

Der isolierte dynamische Lauf bestätigt genau dieses Frame.

## 4. C350 Request DTU → Board

Erzeuger:

```text
set_sev_code_and_ver() @ 0x1C4BC
```

Frameaufbau:

```text
63 10 C3 50 00 07 0E
SS SS
softwareCode[8]
version485[4]
CRC_LO CRC_HI
```

Für V3.3:

```text
SSID         = 0x0063
softwareCode = "82400644"
version485   = "0033"
```

Bytegenau:

```text
63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 30 30 33 33 59 4D
```

ASCII-Anteil:

```text
38 32 34 30 30 36 34 34 = "82400644"
30 30 33 33             = "0033"
```

CRC auf dem Draht:

```text
59 4D
```

Dieser Request ist inzwischen dynamisch bestätigt.

## 5. C350-Bestätigung Board → DTU

Handler:

```text
board_set_ser_ver_handle() @ 0x1B480
```

Der Handler ignoriert Payload und Länge vollständig und tut nur:

```c
app->c350_retry = 0;   // app+0x3C @ 0x98938
```

Das reale Antwortpayload des Mainboards lässt sich deshalb aus `phnixIot4G` allein nicht bestimmen.

---

# C357 – Firmware-Dateiinformation zum Mainboard

## 6. Request DTU → Board

Erzeuger:

```text
set_ota_bin_info() @ 0x1CEA0
```

Aufrufer:

```text
set_ota_bin_info_by_485() @ 0x1D214
```

Frameaufbau:

```text
63 10 C3 57 00 13 26
SS SS
FILESIZE_BE32
MD5_ASCII_LOWERCASE[32]
CRC_LO CRC_HI
```

Für V3.3:

```text
SSID     = 0x0063
fileSize = 287598 = 0x0004636E
MD5      = CEB6A4BF386FF644E23E410023E74673
```

übertragen als lowercase ASCII:

```text
ceb6a4bf386ff644e23e410023e74673
```

Vollständiges Frame:

```text
63 10 C3 57 00 13 26 00 63 00 04 63 6E 63 65 62 36 61 34 62 66 33 38 36 66 66 36 34 34 65 32 33 65 34 31 30 30 32 33 65 37 34 36 37 33 C3 65
```

## 7. C357-Bestätigung Board → DTU

Handler:

```text
board_set_bin_info_handle() @ 0x1B4B4
```

Wirkung:

```c
app->c357_retry = 0;   // app+0x44
```

Auch hier wird das Payload nicht ausgewertet.

---

# C36E – Board-Status / „is allow upgrade“

## 8. C36E ist Board → DTU

Im Executable existiert kein lokaler Framebauer für Register `0xC36E`. Es ist ein eingehendes Status-/Handshakeframe und wird an:

```text
board_is_allow_upg_handle() @ 0x1BA04
```

weitergereicht.

Ausgewertet werden:

```text
data[1]   -> SSID
data[3]   -> Board-OTA-Status
data[4:5] -> optionale Blockgröße, wenn len == 6
```

Praktisches 6-Byte-Layout:

```text
[0] SSID_hi / hier nicht ausgewertet
[1] SSID_lo
[2] reserviert / unbekannt
[3] status
[4] blockSize_hi
[5] blockSize_lo
```

Für SSID `0x0063`, Blockgröße 168:

Status 1:

```text
63 10 C3 6E 00 03 06 00 63 00 01 00 A8 65 18
```

Status 2:

```text
63 10 C3 6E 00 03 06 00 63 00 02 00 A8 95 18
```

---

# 9. Tatsächliche Handshake-Reihenfolge

Der normale Neu-OTA-Pfad ergibt sich als:

```text
0033 angenommen
 -> app+0x3C = 3

Worker:
 -> C350 senden

C350-Bestätigung:
 -> app+0x3C = 0

Board:
 -> C36E Status 1
 -> app+0x44 = 3
 -> optionale Blockgröße übernehmen

Worker:
 -> C357 senden

C357-Bestätigung:
 -> app+0x44 = 0

Board:
 -> C36E Status 2
 -> board_ota_step = 1 (Neu-OTA)
   oder Step 6 im Resume-Pfad
```

Die C357-Bestätigung ist im LTE-Programm kein harter State-Gate; sie beendet nur die Wiederholungen. Der echte Fortschritt wird durch C36E Status 2 ausgelöst.

C350:

```text
app+0x38 = Timer
app+0x3C = Retrybudget
```

C357:

```text
app+0x40 = Timer
app+0x44 = Retrybudget
```

Timer werden ungefähr einmal pro Sekunde dekrementiert; nach Senden wird jeweils `3` gesetzt.

---

# C371 – ACK für Firmwareblock

## 10. Payload

`board_updata_bin_handle() @ 0x1B72C` liest:

```text
data[2:3] -> ackA
data[4:5] -> ackB
data[6:7] -> ackBlock
```

Akzeptanz:

```text
ackA == 1
AND ackBlock == aktueller erwarteter Block
```

`ackB == 1`:

```text
offset += blockSize
```

`ackB == 2`:

```text
offset = fileSize
```

Für Block 1, SSID `0x0063`, `ackA=1`, `ackB=1`, `ackBlock=1`:

```text
63 10 C3 71 00 04 08 00 63 00 01 00 01 00 01 12 EB
```

---

# C5A8 – Firmware-Datenblock

## 11. Präfix bei Defaultblockgröße 168

Für:

```text
SSID          = 0x0063
blockSize     = 168 = 0x00A8
total_blocks  = 1712 = 0x06B0
current_block = 1
```

lautet das Frame-Präfix:

```text
63 10 C5 A8 00 57 A8 00 63 06 B0 00 01
```

Danach:

```text
168 Firmwarebytes
CRC_LO CRC_HI
```

Der letzte Block wird auf die volle Blockgröße mit `0xFF` aufgefüllt.

Für die V3.3-Datei wurde dies im isolierten Originalprozess dynamisch bestätigt:

```text
offset vor Block 1712 = 287448
reale Restdaten       = 150 Byte
Padding               = 18 × FF
```

Ein gezielter Emulator-Grenztest bestätigte zusätzlich den LTE-Handlerpfad für
`ackB=1` beim letzten Block: Der Offset steigt dann um die volle Blockgröße auf
`287616`, und der nächste Worker-Durchlauf erkennt `file_len <= file_offset`.
Dies ist nicht der normale reale Mainboardabschluss. Die Mainboard-Firmware V3.3
sendet beim letzten Block `ackB=2`; dadurch setzt das LTE-Modem den Offset direkt
auf `fileSize = 287598`. Siehe
[`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md).

---

## 12. Runtime-Korrektur 2026-08-23

Der erste streng bytegenaue Emulatorlauf erwartete fälschlich C350 mit `V3.3` und erkannte den echten Request deshalb nicht. Tatsächlich beobachtet wurde:

```text
63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 30 30 33 33 59 4D
```

Die anschließende statische Nachprüfung zeigt, dass dies kein Laufzeitzufall ist: `ota_device_set_ota_file_download_info()` erzeugt explizit die vierstellige interne Versionsdarstellung `0033`, bevor `set_sev_code_and_ver()` sie in C350 einsetzt.

Der spätere vollständige isolierte Lauf bestätigte außerdem alle 1712 C5A8-Frames
bytegenau gegen die V3.3-Referenzdatei einschließlich CRC, Blocknummern und
Final-Padding. Der rekonstruierte SHA-256 war
`6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A`.
