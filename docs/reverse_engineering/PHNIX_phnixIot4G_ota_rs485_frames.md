# PHNIX `phnixIot4G` – OTA-RS485-Frames C350 / C357 / C36E / C371 / C5A8

Stand: 2026-08-22

Grundlage ist die statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`. Wo der Code ein Frame vollständig erzeugt, ist das Frame bytegenau rekonstruierbar. Wo ein Frame nur empfangen wird und der Handler Teile des Payloads ignoriert, ist nur das tatsächlich notwendige/ausgewertete Layout beweisbar; solche Stellen sind unten ausdrücklich als synthetisch/minimal gekennzeichnet.

## 1. CRC-Reihenfolge auf dem Draht

`crc16()` liegt bei `0x137C8`. Die Funktion berechnet den üblichen Modbus-CRC16 mit Initialwert `0xFFFF`, gibt den 16-Bit-Wert jedoch bereits bytevertauscht zurück:

```text
return = (crc_low << 8) | crc_high
```

Die Framebauer schreiben anschließend immer:

```text
(crc >> 8) & 0xFF
crc & 0xFF
```

Dadurch erscheinen auf dem Draht die für Modbus üblichen Bytes:

```text
CRC low byte, dann CRC high byte
```

Beweis mit dem festen Read-Frame aus demselben Binary:

```text
63 03 00 04 00 01 CD 89
```

Standard-Modbus-CRC über `63 03 00 04 00 01` = `0x89CD`, Drahtfolge also `CD 89`.

**Ergebnis:** alle unten angegebenen CRCs sind als tatsächliche Drahtreihenfolge `LOW HIGH` notiert.

---

## 2. Welche Bytes die OTA-Handler tatsächlich erhalten

`unpack_mcu_modbus()` bei `0x1DDE8` erkennt nur Slave `0x63`, FC `0x10` und die acht lokalen OTA-Register.

Für ein FC10-Frame der Form

```text
[0] slave
[1] 0x10
[2] reg_hi
[3] reg_lo
[4] quantity_hi
[5] quantity_lo
[6] byte_count
[7...] data
[..] crc_lo crc_hi
```

wird dem jeweiligen Handler übergeben:

```c
handler(&frame[7], quantity * 2);
```

Das heißt:

- `r0` = Zeiger auf erstes Datenbyte, also `frame + 7`
- `r1` = `quantity * 2`

Die Handler sehen **nicht** Slave, FC, Register, Quantity, Bytecount oder CRC.

---

# C350 – Softwarecode + Softwareversion zum Mainboard

## 3. Request DTU → Board

Erzeuger:

```text
set_sev_code_and_ver() @ 0x1C4BC
```

Aufrufer:

```text
dtu_set_devver_by_485() @ 0x1C740
```

Frameaufbau:

```text
63 10 C3 50 00 07 0E
SS SS
softwareCode[8]
softwareVer[4]
CRC_LO CRC_HI
```

Bedeutung:

```text
63       slave
10       FC16
C3 50    Register C350
00 07    7 Register = 14 Datenbytes
0E       Bytecount 14
SS SS    OTA-SSID big-endian
8 Bytes  softwareCode
4 Bytes  softwareVer
```

Für die bekannte Mainboard-Firmware V3.3:

```text
softwareCode = "82400644"
softwareVer  = "V3.3"
SSID         = 0x0063
```

vollständiges Requestframe einschließlich CRC:

```text
63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 56 33 2E 33 BE 95
```

ASCII-Anteil:

```text
38 32 34 30 30 36 34 34 = "82400644"
56 33 2E 33             = "V3.3"
```

CRC auf dem Draht:

```text
BE 95
```

## 4. C350-Bestätigung Board → DTU

Handler:

```text
board_set_ser_ver_handle() @ 0x1B480
```

Der Handler ignoriert `r0` und `r1` vollständig. Seine einzige Wirkung ist:

```c
app->c350_retry = 0;   // app+0x3C @ 0x98938
```

Damit ist statisch **nicht beweisbar**, welchen Datenpayload das reale Board in seiner C350-Bestätigung zurücksendet. Jedes CRC-gültige FC10-C350-Frame, das `unpack_mcu_modbus()` akzeptiert, führt zum selben Handlerverhalten.

Ein minimal synthetisch gültiges Bestätigungsframe mit Quantity 1 und zwei Null-Datenbytes wäre z. B.:

```text
63 10 C3 50 00 01 02 00 00 E8 6E
```

Dieses Frame ist für einen Emulator geeignet, aber **nicht als bytegenaue Rekonstruktion der realen Boardantwort bewiesen**.

---

# C357 – Firmware-Dateiinformation zum Mainboard

## 5. Request DTU → Board

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

Die Funktion wandelt `A..Z` im MD5-String vor dem Kopieren nach `a..z` um.

Für V3.3:

```text
SSID     = 0x0063
fileSize = 287598 = 0x0004636E
MD5      = CEB6A4BF386FF644E23E410023E74673
```

übertragen wird der MD5 als lowercase ASCII:

```text
ceb6a4bf386ff644e23e410023e74673
```

Vollständiges Frame:

```text
63 10 C3 57 00 13 26 00 63 00 04 63 6E
63 65 62 36 61 34 62 66 33 38 36 66 66 36 34 34
65 32 33 65 34 31 30 30 32 33 65 37 34 36 37 33
C3 65
```

Einzeilig:

```text
63 10 C3 57 00 13 26 00 63 00 04 63 6E 63 65 62 36 61 34 62 66 33 38 36 66 66 36 34 34 65 32 33 65 34 31 30 30 32 33 65 37 34 36 37 33 C3 65
```

CRC:

```text
C3 65
```

## 6. C357-Bestätigung Board → DTU

Handler:

```text
board_set_bin_info_handle() @ 0x1B4B4
```

Auch dieser Handler ignoriert Payload und Länge vollständig und tut nur:

```c
app->c357_retry = 0;   // app+0x44
```

Ein minimal synthetisch gültiges C357-Bestätigungsframe wäre:

```text
63 10 C3 57 00 01 02 00 00 E9 D9
```

Auch hier gilt: geeignet als Emulatorantwort, aber das reale Boardpayload ist statisch nicht aus diesem ELF ableitbar.

---

# C36E – Board-Status / „is allow upgrade“

## 7. Wichtige Korrektur: kein C36E-Request aus `phnixIot4G`

Im gesamten Executable existiert kein Framebauer, der Register `0xC36E` sendet.

`0xC36E` kommt ausschließlich in der lokalen Dispatch-Tabelle vor und wird an

```text
board_is_allow_upg_handle() @ 0x1BA04
```

weitergereicht.

Damit ist C36E in diesem Build ein **Board → DTU Status-/Handshakeframe**, kein DTU → Board Request.

## 8. Vom Handler ausgewertetes C36E-Payload

Der Handler erhält `data = &frame[7]`.

Ausgewertet werden:

```text
data[1]       -> otaDeviceInfo.ssid             (+0x252)
data[3]       -> otaDeviceInfo.board_ota_status (+0x251)
data[4:5]     -> optionale Blockgröße, nur wenn handler_len == 6
```

`data[0]` und `data[2]` werden in diesem Handler nicht benutzt.

Für ein 6-Byte-C36E-Payload ist damit das praktisch rekonstruierbare Layout:

```text
[0] SSID_hi / vom Handler ignoriert
[1] SSID_lo
[2] reserviert / unbekannt
[3] status
[4] blockSize_hi
[5] blockSize_lo
```

Der Code speichert bei `len == 6` eine positive 16-Bit-Blockgröße nach:

```text
app+0x64
```

Default ist 168 (`0x00A8`).

### Synthetisch gültiges Status-1-Frame

Für SSID `0x0063`, Status `1`, Blockgröße 168:

```text
63 10 C3 6E 00 03 06 00 63 00 01 00 A8 65 18
```

### Synthetisch gültiges Status-2-Frame

```text
63 10 C3 6E 00 03 06 00 63 00 02 00 A8 95 18
```

Diese Frames entsprechen exakt dem Layout, das der Handler auswertet und besitzen gültige CRCs. Ob das reale Mainboard in `data[0]` und `data[2]` genau `00` sendet, kann aus `phnixIot4G` allein nicht bewiesen werden.

---

# 9. Tatsächliche Reihenfolge und Retry-/Timerlogik

Die früher naheliegende vereinfachte Reihenfolge

```text
C350 -> C357 -> C36E
```

ist so im Code **nicht** fest verdrahtet.

Der produktive Ablauf ist ereignisgesteuert:

```text
0033 angenommen
  -> app+0x3C = 3             C350-Retrybudget
  -> board-state noch nicht 1/3

Worker dtu_upgrade_pro()
  -> dtu_set_devver_by_485()
     wenn timerC350(app+0x38)==0 && retryC350(app+0x3C)>0:
       retry--
       C350 senden
       timerC350 = 3

Board-C350-Bestätigung
  -> board_set_ser_ver_handle()
  -> retryC350 = 0

Board sendet C36E Status 1
  -> board_is_allow_upg_handle()
  -> setzt retryC357(app+0x44) = 3
  -> übernimmt optional Blockgröße

Worker
  -> set_ota_bin_info_by_485()
     wenn timerC357(app+0x40)==0 && retryC357(app+0x44)>0:
       retry--
       timerC357 = 3
       C357 senden

Board-C357-Bestätigung
  -> board_set_bin_info_handle()
  -> retryC357 = 0

Board sendet C36E Status 2
  -> abhängig von internem app+1:
       app+1 == 0 -> board_ota_step = 1
       app+1 == 1 -> board_ota_step = 6 / Resume-Transfer
```

Daher ist die typische Neu-OTA-Sequenz eher:

```text
0033
 -> C350
 -> C350 confirm
 -> C36E status 1
 -> C357
 -> C357 confirm
 -> C36E status 2
 -> board_ota_step 1
 -> Cloud-Allow/board_request_upgrade
 -> board_ota_step 3
 -> HTTP download
```

## 10. Timer und Retries

C350:

```text
app+0x38 = Timer
app+0x3C = Retrybudget
```

Nach Senden:

```text
timer = 3
```

C357:

```text
app+0x40 = Timer
app+0x44 = Retrybudget
```

Nach Senden:

```text
timer = 3
```

`TimerHandler()` bei `0xAB0C` schläft jeweils 1 Sekunde und dekrementiert beide Timer einmal pro Sekunde. Damit beträgt der Retry-Abstand ungefähr 3 Sekunden.

## 11. Ist die C357-Bestätigung zwingend?

Auf LTE-Codeebene: **nein, nicht als explizite State-Machine-Bedingung.**

`board_set_bin_info_handle()` tut ausschließlich:

```c
app+0x44 = 0;
```

Es setzt keinen `board_ota_step` und kein sonstiges Freigabeflag.

Der eigentliche Übergang wird durch ein später eintreffendes C36E-Statusframe ausgelöst.

Praktisch heißt das:

- Ohne C357-Bestätigung sendet das LTE-Modul C357 bis zum Verbrauch des Retrybudgets erneut.
- Wenn trotzdem ein gültiges C36E Status 2 eintrifft, kann die State-Machine weiterlaufen.
- Ob das reale Mainboard Status 2 jemals ohne vorherige C357-Bestätigung sendet, ist eine Eigenschaft der Mainboard-Firmware und aus `phnixIot4G` allein nicht beweisbar.

Damit ist die **C357-Bestätigung im DTU selbst nicht zwingend**, im realen Boardprotokoll aber sehr wahrscheinlich Teil des normalen Handshakes.

---

# C371 – ACK für Firmwareblock

## 12. Vom Handler ausgewertetes Payload

`board_updata_bin_handle() @ 0x1B72C` erhält wieder `data = frame+7`.

Es liest:

```text
data[2:3] -> ackA
\data[4:5] -> ackB
\data[6:7] -> ackBlock
```

Die ersten zwei Datenbytes werden vom Handler nicht ausgewertet und entsprechen protokolltypisch der SSID.

Akzeptanzbedingung:

```text
ackA == 1
AND
ackBlock == erwarteter aktueller Block
```

`ackB == 1`:

```text
file_offset += blockSize
persistieren
```

`ackB == 2`:

```text
file_offset = fileSize
persistieren
```

## 13. Vollständiges ACK für Block 1

Für:

```text
SSID     = 0x0063
ackA     = 1
ackB     = 1
ackBlock = 1
```

Payload:

```text
00 63 00 01 00 01 00 01
```

Quantity = 4 Register, Bytecount = 8.

Vollständiges Frame einschließlich CRC:

```text
63 10 C3 71 00 04 08 00 63 00 01 00 01 00 01 12 EB
```

CRC-Drahtfolge:

```text
12 EB
```

---

# C5A8 – Firmware-Datenblock

## 14. Frameformat aus `set_board_update_bin()`

Framebauer:

```text
set_board_update_bin() @ 0x1C7CC
```

Gesendet über:

```text
uart485_send_data_to_board() @ 0x1562C
```

Format:

```text
63 10 C5 A8
QQ QQ
LL
SS SS
TT TT
BB BB
<data blockSize bytes>
CRC_LO CRC_HI
```

Bedeutung:

```text
QQQQ = (blockSize + 6) / 2
LL   = blockSize, falls <=255, sonst 0xFF
SSSS = SSID
TTTT = total_blocks
BBBB = current_block
```

Auffällig: `LL` ist nur die Firmwareblocklänge und nicht die gesamte Nutzlastlänge nach dem Bytecount-Feld. Das ist proprietäres PHNIX-Layout und kein normales Modbus-FC16-Bytecount-Verhalten.

## 15. Defaultblockgröße 168

```text
blockSize = 168 = 0x00A8
quantity  = (168 + 6) / 2 = 87 = 0x0057
LL        = 0xA8
```

Für V3.3:

```text
fileSize      = 287598
blockSize     = 168
287598 / 168  = 1711 Rest 150
=> total_blocks = 1712 = 0x06B0
```

Erster Block:

```text
current_block = 1 = 0x0001
SSID          = 0x0063
```

Damit lautet das vollständige erwartete Präfix vor dem ersten Firmwarebyte:

```text
63 10 C5 A8 00 57 A8 00 63 06 B0 00 01
```

Danach folgen exakt 168 Bytes aus `/cache/phnixIot_device_OTA`, beginnend am aktuellen persistenten Offset.

Das komplette Block-1-Frame ist somit:

```text
63 10 C5 A8 00 57 A8 00 63 06 B0 00 01
<168 Firmwarebytes>
CRC_LO CRC_HI
```

Gesamtlänge:

```text
13 Byte Präfix
+ 168 Byte Firmware
+ 2 Byte CRC
= 183 Byte
```

Der CRC kann für Block 1 erst dann bytegenau angegeben werden, wenn die tatsächlichen ersten 168 Firmwarebytes bekannt sind.

---

## 16. Kurzfazit für Emulator/Lab

Für einen synthetischen Mainboard-Emulator sind bytegenau verwendbar:

```text
C350 V3.3 request:
63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 56 33 2E 33 BE 95

C357 V3.3 request:
63 10 C3 57 00 13 26 00 63 00 04 63 6E 63 65 62 36 61 34 62 66 33 38 36 66 66 36 34 34 65 32 33 65 34 31 30 30 32 33 65 37 34 36 37 33 C3 65

C36E status 1, block 168, synthetisch:
63 10 C3 6E 00 03 06 00 63 00 01 00 A8 65 18

C36E status 2, block 168, synthetisch:
63 10 C3 6E 00 03 06 00 63 00 02 00 A8 95 18

C371 ACK block 1:
63 10 C3 71 00 04 08 00 63 00 01 00 01 00 01 12 EB

C5A8 block-1 prefix:
63 10 C5 A8 00 57 A8 00 63 06 B0 00 01
```

Bei C350/C357 sind die oben angegebenen DTU-Requests vollständig bewiesen. Die realen Board-Bestätigungs-Payloads sind dagegen nicht rekonstruierbar, weil die zugehörigen Handler Payload und Länge komplett ignorieren.