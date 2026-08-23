# PHNIX `phnixIot4G` – C544 / Board-Softwareinfo / Resume-Entscheidung

Stand: 2026-08-23

Grundlage: statische Analyse des ARM-ELF `phnixIot4G` sowie bereits dynamisch bestätigte OTA-Felder der V3.3-Firmware.

## 1. Handler und Richtung

Register `0xC544` wird von `unpack_mcu_modbus()` an

```text
board_softcode_ver_handle() @ 0x1C1BC
```

weitergereicht. Der Handler erhält wie bei den anderen lokalen OTA-FC10-Frames nur den Datenbereich:

```c
handler(&frame[7], quantity * 2);
```

Für alle unten ausgewerteten Bytes muss der C544-Datenbereich mindestens 26 Byte lang sein, also mindestens 13 Register.

Ein vollständiger C544-Frame hat damit mindestens die Form:

```text
63 10 C5 44 00 0D 1A
<data[0..25]>
CRC_LO CRC_HI
```

Die konkrete Hardwarecode/-versionsbelegung ist im LTE-ELF nicht enthalten. Seit dem Live-Mitschnitt vom 23. August 2026 liegt für die untersuchte V3.3-Platine jedoch ein bytegenaues reales C544 vor; siehe Abschnitt 11.

## 2. Exaktes C544-Payloadlayout

`board_softcode_ver_handle()` kopiert folgende Felder:

```text
data[0]       vom Handler nicht benutzt

data[1]       -> otaDeviceInfo.ssid (+0x252)

data[2..9]    -> hw_code, 8 Bytes

data[10..13]  -> hw_ver_raw, 4 Bytes

data[14..21]  -> sw_code, 8 Bytes

data[22..25]  -> sw_ver_raw, 4 Bytes
```

Zielspeicher:

```text
otaDeviceInfo @ 0x933AC

+0x235 / 0x935E1  sw_code[9]
+0x23E / 0x935EA  sw_ver[5]
+0x243 / 0x935EF  hw_code[9]
+0x24C / 0x935F8  hw_ver[5]
+0x252 / 0x935FE  ssid
```

Das wird durch die Debugstrings direkt bestätigt:

```text
hw_code:%s,hw_ver:%s
sw_code:%s,sw_ver:%s
```

Dabei werden `hw_code/hw_ver` aus `+0x243/+0x24C` und `sw_code/sw_ver` aus `+0x235/+0x23E` ausgegeben.

## 3. Besonderheit der Softwareversion

Die vier Bytes `data[22..25]` werden zunächst unverändert als `sw_ver_raw[4]` kopiert und genau in dieser Form an `dev_otavercode_compare()` übergeben.

Danach überschreibt `board_softcode_ver_handle()` dieses Feld für die spätere Anzeige/Cloudmeldung mit:

```c
sw_ver_display[0] = 'V';
sw_ver_display[1] = data[24];
sw_ver_display[2] = '.';
sw_ver_display[3] = data[25];
sw_ver_display[4] = 0;
```

Für V3.3 ist das konsistent mit dem dynamisch bestätigten internen OTA-Format:

```text
wire/raw OTA version:  "0033"
Cloud/display version:  "V3.3"
```

Also:

```text
data[22..25] = 30 30 33 33 = "0033"

nach der Rekonstruktion:
"V3.3"
```

Die früher scheinbar „dritte Versionsinformation“ in `data[24]/data[25]` ist damit keine dritte unabhängige Version. Es sind schlicht die beiden relevanten Ziffern des vierstelligen internen Versionsstrings.

## 4. Welche Version an die Cloud gemeldet wird

`ota_device_send_version_to_phnix() @ 0x18A38` verwendet für den `0003`-Report ausdrücklich:

```text
otaDeviceInfo+0x235 -> deviceSoftwareCode
otaDeviceInfo+0x23E -> deviceSoftwareVer
otaDeviceInfo+0x252 -> ssid
```

Damit wird aus dem C544-Payload das **Software-Paar**, nicht das Hardware-Paar, an die Cloud gemeldet.

Format:

```json
{"cmd":"CMD_OTA","code":"0003","param":{"deviceCode":"<redigiert>","deviceSoftwareCode":"<sw_code>","deviceSoftwareVer":"<Vx.y>","ssid":"<ssid>"}}
```

## 5. `dev_otavercode_compare()` – exakte Resume-Entscheidung

Funktion:

```text
dev_otavercode_compare() @ 0x1BFB0
```

Aufruf aus C544:

```c
ret = dev_otavercode_compare(sw_ver_raw, sw_code);
```

also:

```text
r0 = C544 data[22..25] = interner Softwareversionsstring, z. B. "0033"
r1 = C544 data[14..21] = Softwarecode, z. B. "82400644"
```

Persistierte Vergleichswerte in `sys_para @ 0x98820`:

```text
+0xC6 / 0x988E6 -> gespeicherter Ziel-Softwarecode, 8 Bytes + NUL
+0xCF / 0x988EF -> gespeicherte Ziel-Version, 4 Bytes + NUL
+0xD4           -> bestätigter Firmwareoffset
+0xD8           -> Firmwaredateilänge
```

`sys_set_dev_otavercode()` speichert genau das interne vierstellige Versionsformat und den achtstelligen Softwarecode. Beim erfolgreichen neuen Download wird es mit:

```text
version = otaDeviceInfo+0x009
code    = otaDeviceInfo+0x000
```

aufgerufen. Seit der dynamischen C350-Korrektur ist klar, dass `otaDeviceInfo+0x009` intern z. B. `"0033"` enthält, nicht `"V3.3"`.

## 6. Entscheidungsbaum von `dev_otavercode_compare()`

### 6.1 Persistenz muss lesbar sein

Zuerst:

```c
if (sys_read_para() == -1)
    return -1;
```

### 6.2 Wenn bereits OTA-Aktivität vorhanden ist

Wenn mindestens eine dieser Bedingungen gilt:

```text
ota_info+0x16 != 0
oder
ota_info+0x0A != 0
oder
ota_info+0x00 != 0
```

wird kein normaler Boot-Resume-Vergleich durchgeführt.

Falls dabei zusätzlich:

```text
board_ota_step == 6
ota_info+0x16 != 0
app+0x44 == 0
```

gilt, wird ein erneuter C357-Handschlag vorbereitet:

```text
app+0x44 = 3   C357-Retrybudget
app+0x40 = 6   C357-Timer
app+0x01 = 1   Resume-Modus
```

Danach liefert die Funktion trotzdem `-1`.

Das ist ein gezielter Rehandshake während eines bereits laufenden/unterbrochenen Step-6-Zustands, kein erfolgreicher Vergleichsreturn.

### 6.3 Normaler Boot-/Resume-Pfad

Nur wenn die obigen OTA-Aktivitätsflags alle 0 sind, geht es in die Persistenzprüfung.

Zuerst muss gelten:

```text
saved_offset != 0
saved_offset < saved_file_len
```

Sonst:

```text
return -1
```

### 6.4 Softwarecode muss exakt passen

Dann:

```c
if (strcmp(saved_sw_code, board_sw_code) != 0)
    return -1;
```

Der Debugstring dazu lautet sinngemäß:

```text
NOT_RIGHT: gespeicherter Server-Softwarecode stimmt nicht überein
```

Das bedeutet: Resume ist nur für dieselbe Softwarefamilie / denselben Softwarecode erlaubt.

### 6.5 Version muss gerade NICHT gleich sein

Anschließend:

```c
if (strcmp(saved_target_version, board_current_version) == 0)
    return -1;
```

Bei Gleichheit lautet der Debugpfad sinngemäß:

```text
UPDATAERR: gespeicherte Mainboard-Version ist identisch, kein Upgrade
```

Bei Unterschied:

```text
UPDATAok: gespeicherte Mainboard-Version unterscheidet sich, Upgrade möglich
```

Dann werden die gespeicherten Zielwerte zurück in `otaDeviceInfo` übernommen:

```text
otaDeviceInfo+0x000 <- saved_sw_code
otaDeviceInfo+0x009 <- saved_target_version
```

und die Funktion liefert:

```text
0
```

## 7. Bedeutung für einen echten Resume

Für einen Resume muss also exakt folgendes gelten:

```text
persistierter Offset > 0
persistierter Offset < Dateilänge
persistierter Ziel-Softwarecode == aktuell vom Board gemeldeter Softwarecode
persistierte Ziel-Version != aktuell vom Board gemeldete Softwareversion
```

Beispiel:

```text
Board C544:
  sw_code = 82400644
  sw_ver  = 0033

Persistenz nach begonnenem Upgrade auf V3.4:
  sw_code = 82400644
  target  = 0034
  offset  = 50400
  len     = ...

=> dev_otavercode_compare() == 0
=> Resume wird vorbereitet
```

Wenn das Board dagegen bereits `0034` meldet, ist die persistierte Zielversion erreicht und es wird **kein Resume** gestartet.

## 8. Was `board_softcode_ver_handle()` bei erfolgreichem Vergleich tut

Wenn `dev_otavercode_compare() == 0`:

```text
sys_para.file_len -> otaDeviceInfo.fileSize
sys_para.fileMD5  -> otaDeviceInfo.fileMD5
app+0x01          = 1     Resume-Modus
app+0x3C          = 3     C350-Retrybudget
app+0x38          = 6     C350-Timer
```

Damit wird nicht direkt Step 6 gesetzt. Stattdessen wird der OTA-Handschlag erneut angestoßen.

Später führt der bekannte Ablauf über C350/C36E/C357/C36E; bei `app+1 == 1` bewirkt C36E Status 2 den Wiedereinstieg in Step 6 statt den Neu-OTA-Pfad über Step 1/3.

## 9. C544 wird zusätzlich gepuffert

Unabhängig vom Resume-Ergebnis wird die komplette 596-Byte-`otaDeviceInfo`-Struktur in die interne FIFO/Line-Queue geschrieben:

```text
insert_data_to_line(...)
```

Vorher wurde bereits:

```text
ota_info+0x19++
```

ausgeführt. Der FOTA-Worker verwendet diesen Queueeintrag später für den `0003`-Versionsreport.

## 10. C37B Status 7 – Bestätigung des C544-Reports

Am Ende von `board_softcode_ver_handle()` wird immer aufgerufen:

```c
dtu_reply_recv_status(7);
```

`dtu_reply_recv_status() @ 0x1AD30` baut:

```text
Slave      0x63
FC         0x10
Register   0xC37B
Quantity   0x0002
Bytecount  0x04
Data       SSID_BE16, STATUS_BE16
CRC        Modbus LOW/HIGH auf dem Draht
```

Für SSID `0x0063` und Status 7 lautet das vollständige Frame:

```text
63 10 C3 7B 00 02 04 00 63 00 07 B5 A8
```

CRC numerisch:

```text
0xA8B5
```

Drahtfolge:

```text
B5 A8
```

Damit ist C544 nicht nur ein passiver Versionsbericht: Das DTU quittiert jedes verarbeitete C544 explizit mit `C37B/status=7`.

## 11. Dynamisch bestätigtes reales C544 für V3.3

Nach einem einmaligen FC03-Read auf `0x0004` sendete das reale Mainboard rund
49 Sekunden später:

```text
63 10 C5 44 00 0D 1A
00 63
38 32 33 30 30 33 31 34
30 30 30 30
38 32 34 30 30 36 34 34
30 30 33 33
CC F0
```

Damit sind für die untersuchte Anlage bestätigt:

```text
SSID             = 0063
Hardwarecode     = 82300314
Hardwareversion  = 0000
Softwarecode     = 82400644
Softwareversion  = 0033 -> Anzeige V3.3
```

Das LTE-Modem antwortete exakt wie statisch rekonstruiert:

```text
63 10 C3 7B 00 02 04 00 63 00 07 B5 A8
```

Das Mainboard bestätigte dieses FC10-Frame anschließend mit:

```text
63 10 C3 7B 00 02 05 D7
```

Der vollständige Versuch ist in
[`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md)
dokumentiert.

### 11.1 Minimal rekonstruierbares Schema für andere Boards

Ohne reale Hardwarecode/-version kann nur das Softwaresegment bytegenau angegeben werden.

Für V3.3:

```text
data[14..21] = 38 32 34 30 30 36 34 34   "82400644"
data[22..25] = 30 30 33 33               "0033"
```

Das vollständige Payloadschema lautet daher:

```text
XX 63
HH HH HH HH HH HH HH HH
HV HV HV HV
38 32 34 30 30 36 34 34
30 30 33 33
```

wobei:

```text
XX          data[0], im Handler unbenutzt
63          SSID low byte
acht HH     Hardwarecode
vier HV     rohe Hardwareversion
```

Für andere Boards sollten abweichende Hardwarefelder weiterhin nicht
willkürlich als real bestätigt dokumentiert werden. Der LTE-Code benötigt für
die OTA-Resume-Entscheidung ausschließlich SSID sowie das Softwarepaar ab
`data[14]`.

## 12. Wichtigste Korrekturen/Ergebnisse

1. C544 enthält **Hardware- und Softwarecode/-version**, nicht zwei aktive/Backup-Software-Slots.
2. Das zweite Paar (`data[14..25]`) ist eindeutig das Softwarepaar und wird für Resume und Cloudreport benutzt.
3. `data[24]/data[25]` sind keine dritte Versionsinformation; aus dem internen `00xy` wird daraus für die Anzeige `Vx.y` gebaut.
4. Resume verlangt gleichen Softwarecode, aber unterschiedliche aktuelle und gespeicherte Zielversion.
5. Ein erfolgreicher Vergleich startet zunächst einen erneuten C350-Handschlag; der direkte Wiedereinstieg in Step 6 erfolgt erst später über C36E Status 2 im Resume-Modus.
6. Jedes C544 wird mit `C37B/status 7` bestätigt.
7. Für die untersuchte V3.3-Platine sind Hardwarecode `82300314`, rohe Hardwareversion `0000` und das vollständige C544 einschließlich CRC dynamisch bestätigt.
