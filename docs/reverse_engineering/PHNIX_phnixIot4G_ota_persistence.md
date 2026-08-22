# PHNIX `phnixIot4G` – OTA-Persistenz, `sys_para` und Resume

Stand: 2026-08-23

Grundlage: statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`.

## Kurzfazit

Es existieren **zwei getrennte Persistenzdateien**, die bisher leicht verwechselt werden konnten:

```text
/data/phnixIot_device_statisic
/data/phnixIot_device_OTA_INFO
```

Die erste Datei enthält `statistic_para` (128 Byte) und u. a. die zuletzt gespeicherte Board-OTA-SSID.

Die zweite Datei enthält `sys_para` (220 Byte) und ist die eigentliche OTA-/Resume-Persistenz mit CRC, Firmware-MD5, Dateilänge und bestätigtem Dateioffset.

`board_ota_step` selbst wird **nicht** persistent gespeichert.

---

## 1. `/data/phnixIot_device_statisic`

Globale Struktur:

```text
statistic_para @ 0x91B60
Größe: 128 Byte
```

Leser/Schreiber:

```text
static_read_data()  @ 0x10598
static_write_data() @ 0x106F0
```

Datei:

```text
/data/phnixIot_device_statisic
```

### `static_read_data(flag)`

Öffnet mit:

```text
"a+"
```

und liest exakt:

```text
fread(statistic_para, 128, 1, fp)
```

Bei `flag != 0` werden nach dem Einlesen mehrere Statistik-/Runtimefelder zurückgesetzt, aber **nicht** die Board-OTA-SSID bei `+0x7C`.

Die OTA-SSID bleibt damit über Neustarts erhalten.

Relevantes Feld:

```text
statistic_para + 0x7C   uint16_t board_ota_ssid
VA 0x91BDC
```

Getter:

```text
sys_get_board_ota_ssid() @ 0x1ABEC
```

führt zunächst `static_read_data(0)` aus und liefert danach `*(uint16_t *)(0x91B60+0x7C)`.

Setter:

```text
sys_set_board_ota_ssid() @ 0x1AC10
```

schreibt nur bei Änderung und ruft anschließend `static_write_data()`.

### `0033` schreibt die SSID vor der eigentlichen OTA-Persistenz

Nach erfolgreichem JSON-Parsing:

```text
0x190C8  otaDeviceInfo.ssid lesen
0x190D8  statistic_para+0x7C schreiben
0x190DC  static_write_data()
```

Erst danach folgen:

```text
0x190E8  rm -f /cache/phnixIot_device_OTA
0x190F4  true > /data/phnixIot_device_OTA_INFO
```

Damit ist die SSID bereits in der Statistikdatei persistent, bevor die OTA_INFO-Datei bewusst geleert wird.

---

# 2. `/data/phnixIot_device_OTA_INFO`

Globale Struktur:

```text
sys_para @ 0x98820
Größe: 220 Byte (0xDC)
```

Datei:

```text
/data/phnixIot_device_OTA_INFO
```

## 3. Dateiformat / CRC

`sys_flash_erase_write() @ 0x1A6D8`:

```c
crc = GetCrc16((uint8_t *)&sys_para + 4, 216);
sys_para.crc = crc;

fp = fopen("/data/phnixIot_device_OTA_INFO", "wb");
fwrite(&sys_para, 220, 1, fp);
fflush(fp);
fsync(fileno(fp));
fclose(fp);
```

Das bedeutet:

```text
+0x00 .. +0x03   CRC32-Speicherplatz, tatsächlich 16-Bit-Wert in 32 Bit
+0x04 .. +0xDB   CRC-geschützte Nutzdaten, 216 Byte
```

`GetCrc16()` verwendet hier **nicht** den Modbus-CRC aus `crc16()`, sondern eine eigene tabellenbasierte CRC-Routine mit:

```text
Startwert = 0xFFFF
am Ende bitweise NOT
```

`sys_read_para() @ 0x1A7D0` liest 220 Byte und verifiziert:

```c
calc = GetCrc16(&tmp[4], 216);
if (*(uint32_t *)&tmp[0] != calc)
    return -1;
```

Nur bei korrekter CRC wird der komplette 220-Byte-Block nach `sys_para @ 0x98820` kopiert.

---

# 4. Bestätigte `sys_para`-Felder

Die folgenden Offsets sind statisch direkt bewiesen:

| Offset | VA | Größe | Bedeutung |
|---:|---:|---:|---|
| `+0x00` | `0x98820` | 4 | gespeicherter CRC-Wert |
| `+0x1C` | `0x9883C` | 6 | interne Persistenz-/Strukturversion |
| `+0xA5` | `0x988C5` | 33 | Board-Firmware-MD5 als ASCII inkl. NUL |
| `+0xC6` | `0x988E6` | 9 | gespeicherter OTA-Softwarecode inkl. NUL |
| `+0xCF` | `0x988EF` | 5 | gespeicherte OTA-Version inkl. NUL |
| `+0xD4` | `0x988F4` | 4 | bestätigter Board-Firmware-Dateioffset |
| `+0xD8` | `0x988F8` | 4 | Board-Firmware-Dateilänge |

Strukturgröße endet bei:

```text
+0xDC
```

### Strukturversion

`sys_set_ver()` schreibt 6 Byte nach `sys_para+0x1C`.

Wenn `/data/phnixIot_device_OTA_INFO` beim Start leer/nicht vorhanden ist, setzt `fota_board_thread_handle()`:

```text
"V1.2"
```

als initiale Version.

---

# 5. Setter/Getter und Schreibzeitpunkte

## Firmware-MD5

```text
sys_set_board_file_md5() @ 0x1A9B4
sys_get_board_file_md5() @ 0x1AA6C
```

Offset:

```text
sys_para+0xA5
```

Es werden 32 MD5-Zeichen plus NUL gespeichert.

Setter schreibt nur, wenn der neue String abweicht; danach `sys_flash_erase_write()`.

## Dateilänge

```text
sys_set_board_file_len() @ 0x1AAFC
sys_get_board_file_len() @ 0x1AB50
```

Offset:

```text
sys_para+0xD8
```

Setter schreibt nur bei Änderung und persistiert sofort.

## bestätigter Dateioffset

```text
sys_set_board_file_offset() @ 0x1AB70
sys_get_board_file_offset() @ 0x1ABCC
```

Offset:

```text
sys_para+0xD4
```

Dieser Wert ist der zentrale Resume-Zeiger.

Nach einem erfolgreichen C371-ACK mit `ackB==1` wird:

```text
offset += blockSize
```

berechnet und anschließend über `sys_set_board_file_offset()` persistent geschrieben.

Bei `ackB==2` wird der Offset auf die vollständige Dateilänge gesetzt.

## Softwarecode / Version

```text
sys_set_dev_otavercode() @ 0x1A908
```

Speichert:

```text
sys_para+0xC6   softwareCode[8] + NUL
sys_para+0xCF   softwareVer[4]  + NUL
```

Auch hier erfolgt danach unmittelbar `sys_flash_erase_write()`.

---

# 6. Wann nach einem erfolgreichen Download persistiert wird

In `dtu_upgrade_pro()` nach erfolgreichem:

```text
board_ota_http_download()
```

folgt exakt:

```text
0x1D870  sys_set_board_file_offset(0)
0x1D87C  sys_set_board_file_md5(...)
0x1D890  sys_set_board_file_len(otaDeviceInfo.fileSize)
0x1D8E0  sys_set_dev_otavercode(...)
0x1D8FC  set_board_ota_step(6)
```

Wichtig:

Jeder Setter kann die gesamte 220-Byte-Datei neu schreiben. Der persistente OTA-Stand wird also **schrittweise** aufgebaut.

`board_ota_step=6` kommt erst danach und ist nur RAM.

---

# 7. `board_ota_step` ist nicht persistent

Globale Variable:

```text
board_ota_step @ 0x98A94
```

`set_board_ota_step()` schreibt ausschließlich RAM.

Beim Start von `fota_board_thread_handle()` wird sogar explizit gesetzt:

```text
0x1DDD8  set_board_ota_step(12)
```

Danach läuft permanent:

```text
dtu_upgrade_pro()
```

Daraus folgt:

> Ein Prozess-/Systemneustart setzt die State-Machine nicht automatisch auf den zuletzt aktiven Schritt zurück.

Resume erfolgt ausschließlich über die persistenten Metadaten plus erneuten Board-Handshake.

---

# 8. Resume-Erkennung durch `dev_otavercode_compare()`

`dev_otavercode_compare() @ 0x1BFB0` ruft zuerst:

```text
sys_read_para()
```

auf.

Der relevante Resume-Fall ist:

```c
if (ota runtime idle)
{
    if (saved_offset != 0 && saved_offset < saved_file_len)
    {
        if (saved_version == board_version &&
            saved_softwareCode == board_softwareCode)
        {
            // gespeicherte OTA-Metadaten passen zum Board
            return 0;
        }
    }
}
```

Bei erfolgreichem Vergleich übernimmt `board_softcode_ver_handle()` anschließend:

```text
sys_para+0xD8 -> otaDeviceInfo.fileSize
sys_para+0xA5 -> otaDeviceInfo.fileMD5
```

und setzt:

```text
app+0x01 = 1
app+0x3C = 3      // C350 Retrybudget
app+0x38 = 6      // C350 Timer/Verzögerung
```

`app+0x01 == 1` ist später genau der Hinweis, dass bei C36E Status 2 nicht der Neu-OTA-Pfad, sondern der Resume-Pfad gewählt werden soll.

Damit ist der Neustartpfad:

```text
Start
 -> sys_read_para()
 -> board_ota_step = 12
 -> Board meldet C544 Softwarecode/Version
 -> dev_otavercode_compare()
 -> gespeicherter offset > 0 und < file_len
 -> Code/Version passen
 -> otaDeviceInfo wird aus sys_para rekonstruiert
 -> app+1 = 1
 -> erneuter C350/C36E/C357-Handshake
 -> C36E Status 2
 -> board_ota_step = 6
 -> Transfer ab gespeichertem Offset
```

---

# 9. Was bei verschiedenen Crash-Zeitpunkten erhalten bleibt

## Crash direkt nach angenommenem `0033`

Bereits persistent:

```text
statistic_para.board_ota_ssid
```

Gleichzeitig wurde aber:

```text
/data/phnixIot_device_OTA_INFO
```

auf Länge 0 gesetzt.

Noch nicht persistent:

```text
neuer MD5
neue Dateilänge
neuer Softwarecode
neue Softwareversion
Offset
```

Folge: kein Resume des neuen Transfers möglich.

## Crash während HTTP-Download

`OTA_INFO` wurde beim `0033` geleert und die neuen Metadaten werden erst **nach erfolgreichem Download + MD5-Check** in `sys_para` geschrieben.

Folge:

```text
kein echter HTTP-Resume
kein persistierter Step 3
```

## Crash nach Download, vor erstem Block

Dann können bereits gespeichert sein:

```text
offset = 0
MD5
file_len
softwareCode
softwareVer
```

Da Resume-Logik einen Offset `>0` verlangt, ist dies kein bereits bestätigter Block-Resume. Der Transfer muss durch Handshake erneut in Gang gesetzt werden.

## Crash nach bestätigtem Block N

Persistiert:

```text
offset = Beginn von Block N+1
```

Nach Neustart und erfolgreichem Versionsvergleich kann exakt ab diesem Offset fortgesetzt werden.

## Crash nach Senden von Block N, aber vor ACK

Der persistierte Offset bleibt auf Block N.

Nach Wiederaufnahme wird derselbe Block erneut übertragen.

Das Verhalten ist damit idempotent gegenüber verlorenen ACKs.

---

# 10. Fehlerfälle der OTA_INFO-Datei

`sys_read_para()` akzeptiert die Datei nur, wenn:

```text
fopen erfolgreich
fread liefert != 0
CRC über Byte 4..219 stimmt exakt
```

Bei CRC-Fehler:

```text
return -1
```

und der gelesene Block wird nicht nach `sys_para` übernommen.

Es gibt keinen Recovery-Mechanismus, der beschädigte Teilfelder akzeptiert.

Beim Workerstart wird die Dateigröße per `stat()` betrachtet. Ist die Datei leer bzw. Größe <=0, wird die Strukturversion `V1.2` initialisiert und ein neuer gültiger `sys_para`-Block geschrieben.

---

# 11. Konsequenz für isolierte Work-Läufe

Für vollständig reproduzierbare OTA-Tests müssen **beide** Dateien berücksichtigt werden:

```text
/data/phnixIot_device_statisic
/data/phnixIot_device_OTA_INFO
```

Insbesondere kann eine alte `OTA_INFO` mit gültigem CRC und:

```text
offset > 0
offset < file_len
passendem softwareCode
passender softwareVer
```

einen Resume-Pfad aktivieren, obwohl im aktuellen Test gar kein neuer Download durchgeführt wurde.

Die Statistikdatei kann zusätzlich eine alte OTA-SSID liefern.

Für reine Beobachtung eines synthetischen `0033` bleibt der bereits bestimmte Breakpoint:

```gdb
b *0x19064
```

weiterhin der sicherste Halt **nach vollständiger JSON-Auswertung, aber vor**:

```text
State-Änderung
SSID-Persistenz
Cache-Dateilöschung
OTA_INFO-Truncation
Download
RS485-OTA-State-Machine
```

Für Tests, die bewusst hinter diesen Punkt gehen, sollte Work den Inhalt und die Größe beider Persistenzdateien vor und nach dem Lauf protokollieren.
