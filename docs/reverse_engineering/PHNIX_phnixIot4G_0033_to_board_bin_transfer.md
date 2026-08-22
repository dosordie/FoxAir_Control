# PHNIX `phnixIot4G` – von OTA `0033` bis zum Board-Firmwareblocktransfer

Stand: 2026-08-22

Grundlage: statische Analyse des bereitgestellten ARM32-ELF `phnixIot4G` (SHA256 `7C573431F0A67620D473419644A83A4F4DC04B8A91BDE5923C74A63BA1EAEDB7`). Adressen sind feste virtuelle ELF-Adressen dieses Builds.

Diese Notiz schließt zwei bisher getrennte Bereiche:

1. Wie ein angenommenes Cloud-OTA-Kommando `0033` über `app+0x3C` tatsächlich zum `board_ota_step` 1 und anschließend 3 führt.
2. Wie `set_update_board_bin_by_485()` und `set_board_update_bin()` die heruntergeladene Board-Firmware blockweise über RS485 übertragen.

---

## 1. Relevante globale Zustände

### `app`

```text
app base = 0x988FC
```

Für diesen Ablauf relevante Felder:

```text
app+0x00  0x988FC  Status-/Progressflag
app+0x01  0x988FD  OTA-Handshakeflag
app+0x04  0x98900  Retry-/Statusfeld
app+0x05  0x98901  Retry-/Statusfeld
app+0x38  0x98934  Timer für C350-Versionstransfer
app+0x3C  0x98938  C350-Sende-/Retryzähler
app+0x48  0x98944  Blocktransfer-Retrytimer
app+0x4C  0x98948  Blocktransfer-Retrybudget
app+0x64  0x98960  OTA-Blockgröße
app+0x68  0x98964  Cancel-/Abbruchflag vor Download
```

`app+0x3C` ist **nicht** `board_ota_step`. Es ist ein Zähler für wiederholtes Senden des Server-Code-/Versions-Handshakes C350.

### `board_ota_step`

Der Board-OTA-State liegt bei:

```text
ota_info + 0x18 = 0x98A94
```

Zugriff erfolgt regulär über:

```text
set_board_ota_step() @ 0x1D34C
get_board_ota_step() @ 0x1D38C
```

---

## 2. Alle direkt gefundenen Leser/Schreiber von `app+0x3C` (`0x98938`)

### Schreiber

#### `ota_device_set_ota_file_download_info()`

```text
0x19070: app+0x3C = 3
```

Das geschieht **nach vollständigem erfolgreichen JSON-Parsing** eines akzeptierten `0033`.

#### `board_set_ser_ver_handle()`

```text
0x1B4A4: app+0x3C = 0
```

Dieser Handler gehört zum RS485-OTA-Register `0xC350`. Die Antwort des Boards beendet damit die C350-Wiederholung.

#### `board_recv_cancel_upgrade_handle()`

```text
0x1B5D8: app+0x3C = 3
```

Nur in einem Cancel-/Recovery-Zweig.

#### `board_softcode_ver_handle()`

```text
0x1C368: app+0x3C = 3
```

Wenn `dev_otavercode_compare(...) == 0`.

#### `dtu_set_devver_by_485()`

```text
0x1C788: app+0x3C = app+0x3C - 1
```

Der Zähler wird nur dekrementiert, wenn der zugehörige Timer `app+0x38 == 0` ist.

### Leser

Der produktive direkte Leser ist `dtu_set_devver_by_485()`:

```text
if (app+0x38 != 0)
    return;

if (app+0x3C == 0)
    return;

app+0x3C--;
...
app+0x38 = 3;
```

`TimerHandler()` dekrementiert `app+0x38`, nicht `app+0x3C`. Damit wird C350 zeitlich wiederholt, bis ein Board-Reply `app+0x3C` auf 0 setzt oder das Budget aufgebraucht ist.

Hinweis: Eine mögliche Gesamtinitialisierung von `app` per `memset` ist von diesen direkten Feldzugriffen getrennt zu betrachten; oben sind die semantischen Einzelzugriffe auf `+0x3C` aufgeführt.

---

## 3. Alle gefundenen Schreiber von `board_ota_step` (`0x98A94`)

Direkte produktive Writes laufen über `set_board_ota_step()`.

```text
down_board_cancel_ota_handle          -> 7
down_board_ver_bcakroll_handle        -> 8
board_recv_cancel_upgrade_handle      -> 7
board_reply_verbackroll_handle        -> 8

board_is_allow_upg_handle:
  0x1BBEC -> 10
  0x1BC54 -> 6
  0x1BCA0 -> 1
  0x1BDAC -> 7
  0x1BE6C -> 5
  0x1BF5C -> 7

dtu_upgrade_pro:
  0x1D744 -> 12
  0x1D79C -> 3
  0x1D848 -> 7
  0x1D900 -> 6
  0x1D9CC -> 10
  0x1D9FC -> 12
  0x1DA38 -> 12
  0x1DB8C -> 12
  0x1DB94 -> 10
  0x1DC28 -> 9
  0x1DC5C -> 9
  0x1DC90 -> 12

fota_board_thread_handle:
  0x1DDDC -> 12
```

Der für ein neues `0033` entscheidende Writer von **Step 1** ist:

```text
board_is_allow_upg_handle @ 0x1BCA0
```

Der Writer von **Step 3** ist:

```text
dtu_upgrade_pro @ 0x1D79C
```

### Leser

`get_board_ota_step()` wird unter anderem gelesen durch:

```text
board_is_allow_upg_handle
dev_otavercode_compare
dtu_upgrade_pro
```

`dtu_upgrade_pro()` fragt den State mehrfach hintereinander ab und bildet damit die eigentliche Worker-State-Machine.

---

## 4. Exakter Kontrollfluss: angenommenes `0033` -> `app+0x3C = 3`

`down_board_ota_url_handle()` befindet sich in diesem Build bei `0x19688`.

Nach seinen Gate-Bedingungen ruft er auf:

```text
0x196F4 -> ota_device_set_ota_file_download_info(json)
```

Der JSON-Parser endet bei:

```text
0x19060 -> json_object_put(root)
```

Unmittelbar danach beginnt der erste Zustandsänderungsblock:

```text
0x19070 -> app+0x3C = 3
0x19080 -> ota_info+0x16 = 2
...
0x190AC -> app+0x00 = 0
0x190BC -> app+0x01 = 0
...
0x190DC -> static_write_data()
0x190E8 -> rm -f /cache/phnixIot_device_OTA
0x190F4 -> true > /data/phnixIot_device_OTA_INFO
```

Wichtig: Der Parser schreibt **noch keinen `board_ota_step`**.

---

## 5. Was `app+0x3C = 3` auslöst

Der permanente FOTA-Worker ruft `dtu_upgrade_pro()` auf. Produktiv wird dieser erst, wenn:

```text
get_dtu_run_step() == 11
```

Innerhalb jedes produktiven Durchlaufs werden vor dem eigentlichen State-Dispatch aufgerufen:

```text
0x1D6CC -> dtu_set_devver_by_485()
0x1D6D0 -> set_ota_bin_info_by_485()
```

`dtu_set_devver_by_485()` benutzt `app+0x3C` als Retrybudget. Wenn `app+0x38 == 0` und `app+0x3C != 0`:

```text
app+0x3C--
otaDeviceInfo.ssid = sys_get_board_ota_ssid()
set_sev_code_and_ver(...)
app+0x38 = 3
```

`set_sev_code_and_ver()` sendet den Board-/Server-Code-/Versions-Handshake über RS485 FC10 auf:

```text
Register 0xC350
```

Ein C350-Reply wird durch `board_set_ser_ver_handle()` verarbeitet und setzt:

```text
app+0x3C = 0
```

Damit ist `app+0x3C=3` ein Trigger für maximal drei zeitlich getrennte C350-Sendeversuche und **kein direkter Step-Transition-Wert**.

---

## 6. Übergang zum echten `board_ota_step = 1`

`board_is_allow_upg_handle()` gehört zum OTA-RS485-Register:

```text
0xC36E
```

In seinem Statuszweig für Boardstatus `2` gibt es zwei Fälle. Entscheidend für ein frisch akzeptiertes `0033` ist, dass der Parser zuvor gesetzt hat:

```text
app+0x01 = 0
```

Wenn der C36E-Handler Status 2 erhält und `app+0x01 != 1`, landet er im Branch:

```text
0x1BC9C: mov r0,#1
0x1BCA0: bl set_board_ota_step
```

also:

```text
board_ota_step = 1
```

Damit ist der statisch bewiesene State-Übergang:

```text
angenommenes 0033
 -> app+0x3C = 3
 -> C350-Metadaten/Version werden wiederholt zum Board gesendet
 -> Board-OTA-Handshake läuft
 -> C36E / board_is_allow_upg_handle(), Status=2 und app+1=0
 -> board_ota_step = 1 @ 0x1BCA0
```

Die konkrete zeitliche Kausalität „C350-Antwort verursacht anschließend genau den C36E-Status 2“ ist aus dem LTE-Binary allein nicht beweisbar; der C350-Sendepfad, der C36E-Handler und dessen Step-1-Branch sind dagegen jeweils statisch eindeutig.

---

## 7. `board_ota_step 1 -> 3`

In `dtu_upgrade_pro()`:

```text
0x1D750 -> get_board_ota_step()
0x1D758 -> compare with 1
0x1D760 -> board_request_upgrade()
```

`board_request_upgrade()` bei `0x1D4E4` ist vollständig kurz:

```c
int board_request_upgrade(void)
{
    uint8_t status = otaDeviceInfo.current_board_status; // +0x251

    if (ota_device_send_is_can_ota_to_phnix(status) < 0)
        return -1;

    return 0;
}
```

Nach erfolgreichem Report prüft `dtu_upgrade_pro()` zusätzlich:

```text
0x1D778: ota_info[0] == 0
0x1D78C: otaDeviceInfo.fileSize != 0
```

Nur dann:

```text
0x1D798 -> r0 = 3
0x1D79C -> set_board_ota_step(3)
```

Danach werden gesetzt:

```text
ota_info[0]      = 2
ota_info+0x16    = 1
ota_info+0x15    = 0
ota_info+0x10    = 0
app+0x05         = 0
app+0x04         = 0
```

Damit sind die exakten Gate-Bedingungen für Step 1 -> Step 3:

```text
board_ota_step == 1
AND board_request_upgrade() == 0
AND ota_info[0] == 0
AND otaDeviceInfo.fileSize != 0
```

---

## 8. Step 3 -> erster Firmwaredatei-Download

Der nächste State-Test liegt bei:

```text
0x1D820 -> get_board_ota_step()
0x1D828 -> compare with 3
```

Vor dem Download wird nur noch geprüft:

```text
app+0x68 == 1 ?
```

Wenn ja:

```text
board_ota_step = 7
app+0x68 = 0
return
```

Wenn nein, erfolgt der tatsächliche Download-Aufruf:

```text
0x1D860 -> board_ota_http_download() @ 0x1D520
```

Der exakte Kontrollfluss ist damit:

```text
0033 akzeptiert
  -> app+0x3C=3
  -> C350-Retries
  -> C36E Status 2, app+1=0
  -> board_ota_step=1
  -> board_request_upgrade()==0
  -> ota_info[0]==0
  -> fileSize!=0
  -> board_ota_step=3
  -> app+0x68!=1
  -> board_ota_http_download() @0x1D520
```

---

## 9. `board_ota_http_download()`

```c
int board_ota_http_download(void)
{
    if (ota_download_device_otaFile() < 0) {
        ota_device_send_ota_FirmwareDownloadFailed();
        return -1;
    }

    if (ota_check_device_otaFile_md5() < 0)
        return -1;

    return 0;
}
```

Bei Erfolg setzt `dtu_upgrade_pro()` anschließend:

```text
0x1D870 -> sys_set_board_file_offset(0)
0x1D878 -> sys_set_board_file_md5(expected MD5)
0x1D890 -> sys_set_board_file_len(otaDeviceInfo.fileSize)
0x1D8D4 -> sys_set_dev_otavercode(...)
0x1D900 -> set_board_ota_step(6)
0x1D920 -> app+0x4C = 3
```

Damit beginnt erst nach erfolgreichem Download und MD5-Check der eigentliche Board-Binärtransfer.

---

# Teil II – `set_update_board_bin_by_485()` und Firmwareblocktransfer

## 10. Wrapper `set_update_board_bin_by_485()` @ `0x1CE14`

Exaktes Pseudocode:

```c
int set_update_board_bin_by_485(void)
{
    int ret = -1;

    if (app.retry_timer_48 != 0)
        return -1;

    if (app.retry_budget_4C == 0)
        return -1;

    app.retry_budget_4C--;
    ret = set_board_update_bin();
    app.retry_timer_48 = 5;

    return ret;
}
```

Adressen:

```text
0x1CE30 read app+0x48
0x1CE44 read app+0x4C
0x1CE74 write app+0x4C--
0x1CE78 call set_board_update_bin()
0x1CE8C write app+0x48 = 5
```

`TimerHandler()` zählt `app+0x48` herunter. Solange kein ACK kommt, wird nach Ablauf dieses Timers derselbe Block erneut gesendet, solange `app+0x4C` noch ungleich 0 ist.

Im State 6 ruft `dtu_upgrade_pro()` auf:

```text
0x1D9E8 -> set_update_board_bin_by_485()
```

Nur Rückgabewert **0** führt zu:

```text
0x1D9F8 -> board_ota_step = 12
```

`-1` bedeutet hier nicht zwingend „Fehler“; während des normalen Transfers liefert das Senden eines Blocks `-1`, weil noch weitere ACK/Blöcke ausstehen.

---

## 11. Firmwaredatei und persistenter Resume-Offset

`set_board_update_bin()` bei `0x1C7CC` liest:

```text
sys_get_board_file_len()    -> persistente Firmwarelänge
sys_get_board_file_offset() -> persistenter aktueller Offset
```

Datei:

```text
/cache/phnixIot_device_OTA
```

Öffnungsmodus:

```text
"r"
```

Das `fseek()` benutzt den persistenten Offset aus `sys_para+0xD4`:

```text
sys_para base      0x98820
file offset        sys_para+0xD4
file length        sys_para+0xD8
```

Damit ist Resume innerhalb des Transferprotokolls real: Blocknummer und Dateiposition werden aus dem persistierten Offset rekonstruiert.

---

## 12. Ende der Datei

Sehr früh in `set_board_update_bin()`:

```c
file_len    = sys_get_board_file_len();
file_offset = sys_get_board_file_offset();

if (file_len <= file_offset) {
    MD5Final(...);       // nur diagnostischer Pfad
    print_digest();
    return 0;
}
```

Der Rückgabewert `0` ist damit der **Transfer-Ende-Indikator** für `dtu_upgrade_pro()`, welches anschließend Step 12 setzt.

Wenn `file_offset == 0`, wird zusätzlich ein Streaming-MD5-Kontext initialisiert. Dieser Streaming-MD5 ist jedoch nicht die produktive Integritätsprüfung; siehe Abschnitt „Checksummen“.

---

## 13. Blockgröße

Die aktive Blockgröße steht in:

```text
app+0x64
```

Default aus den bisherigen OTA-Pfaden:

```text
168 Byte
```

`board_is_allow_upg_handle()` kann diesen Wert beim Allow-Handshake aus zwei vom Board gelieferten Bytes überschreiben:

```text
blockSize = (buf[4] << 8) | buf[5]
if (blockSize > 0)
    app+0x64 = blockSize
```

Die Blockgröße ist daher **Board-verhandelbar**, 168 Byte ist nur der Default.

---

## 14. Exakte Blocknummern

`set_board_update_bin()` berechnet:

```c
total_blocks = file_len / block_size;
if (file_len % block_size != 0)
    total_blocks++;

current_block = file_offset / block_size + 1;
```

Damit sind beide Werte 1-basiert im übertragenen Protokoll.

---

## 15. RS485-Frameformat des Firmwareblocks

Register:

```text
0xC5A8
```

Funktion:

```text
0x10 (Modbus Write Multiple Registers)
```

Frameaufbau:

```text
Offset  Größe  Bedeutung
0       1      Slave = 0x63
1       1      Function = 0x10
2       2      Register = 0xC5A8, big-endian
4       2      Quantity = (blockSize + 6) / 2, big-endian
6       1      Blockdaten-Länge; blockSize falls <=255, sonst 0xFF
7       2      SSID, big-endian
9       2      total_blocks, big-endian
11      2      current_block, big-endian
13      N      Firmwaredaten, exakt blockSize Byte übertragen
13+N    2      CRC16, High-Byte zuerst, dann Low-Byte
```

Bei Default `blockSize=168`:

```text
Quantity = (168+6)/2 = 87 Register
Firmwaredaten = 168 Byte
Header vor Daten = 13 Byte
Frame vor CRC = 181 Byte
Gesamt = 183 Byte
```

Bemerkenswert: Byte 6 enthält `blockSize`, während Quantity zusätzlich die sechs Metadatenbytes SSID/total/current berücksichtigt. Das ist damit ein PHNIX-spezifisches FC10-Layout und nicht als streng generisches Modbus-Bytecount-Feld zu interpretieren.

---

## 16. Firmwaredateizugriff und letzter kurzer Block

Vor dem Lesen wird ein 1900-Byte-Puffer mit `0xFF` gefüllt.

Dann:

```c
fp = fopen("/cache/phnixIot_device_OTA", "r");
fseek(fp, persisted_offset, SEEK_SET);
read_count = fread(frame + 13, 1, blockSize, fp);
```

Es wird lediglich geprüft:

```text
read_count != 0
```

Es gibt **keine Forderung `read_count == blockSize`**.

Da der Puffer vorher vollständig mit `0xFF` gefüllt wurde und anschließend immer die volle `blockSize` zur Frame-Länge addiert wird, wird ein letzter kurzer Firmwareblock automatisch mit `0xFF` bis zur vollen Blockgröße aufgefüllt.

---

## 17. CRC

Nach Header + vollständigem `blockSize`-Datenbereich:

```text
crc16(frame, frame_len_before_crc)
```

Der 16-Bit-Wert wird angehängt als:

```text
CRC high byte
CRC low byte
```

Anschließend:

```text
uart485_send_data_to_board(frame, full_len)
```

---

## 18. ACK: `board_updata_bin_handle()` @ `0x1B72C`

Der Handler gehört zum OTA-Register:

```text
0xC371
```

Er wird nur produktiv, wenn:

```text
ota_info[0] == 2
OR
ota_info+0x16 != 0
```

Er dekodiert:

```text
ackA     = BE16(buf[2], buf[3])
ackB     = BE16(buf[4], buf[5])
ackBlock = BE16(buf[6], buf[7])
```

Er berechnet:

```text
expectedBlock = persisted_offset / blockSize + 1
```

Vor der eigentlichen Validierung setzt jeder ankommende ACK-Handler-Aufruf:

```text
app+0x48 = 0
app+0x4C = 3
```

also Retrytimer zurücksetzen und Retrybudget neu laden.

Ein ACK wird nur als passend behandelt, wenn:

```text
ackA == 1
AND
ackBlock == expectedBlock
```

### `ackB == 1` – Block angenommen

Dann:

```text
new_offset = old_offset + blockSize
sys_set_board_file_offset(new_offset)
```

Zusätzlich gibt es einen Progress-/Reporttrigger ungefähr alle 30 Blöcke.

### `ackB == 2` – Transferende bestätigt

Dann:

```text
file_len = sys_get_board_file_len()
sys_set_board_file_offset(file_len)
```

Beim nächsten `set_board_update_bin()` greift dadurch sofort:

```text
file_len <= file_offset
```

und die Funktion liefert 0 -> State 12.

### Falsches ACK

Bei falschem `ackA`, falscher Blocknummer oder unbekanntem `ackB` wird der persistente Offset nicht erhöht.

Die äußere Modbus-Empfangsschicht validiert den RS485-CRC bereits vor dem Dispatch. `board_updata_bin_handle()` selbst führt keine zweite CRC-Prüfung durch.

---

## 19. Retryverhalten

Vor jedem Sendeblock:

```text
app+0x48 muss 0 sein
app+0x4C muss !=0 sein
```

Dann:

```text
app+0x4C--
Block senden
app+0x48=5
```

Ohne ACK bleibt der persistente Offset unverändert. Nach Ablauf des Timers wird daher derselbe Block erneut aus derselben Dateiposition gelesen und mit derselben Blocknummer gesendet.

Ein gültiger ACK setzt:

```text
app+0x48=0
app+0x4C=3
```

und verschiebt erst danach den Offset.

Wenn das Retrybudget ohne ACK auf 0 fällt, führt `set_update_board_bin_by_485()` selbst keinen weiteren Send aus und liefert weiter `-1`. Ein eigenständiger „Budget erschöpft -> sofort Fehlerstate“-Branch ist in diesem Wrapper nicht vorhanden; ein eventueller höherer Timeout-/Recoverypfad muss daher getrennt betrachtet werden.

---

## 20. Resume-Verhalten

Resume wird primär über den persistenten Offset umgesetzt:

```text
file_offset -> sys_para+0xD4
file_len    -> sys_para+0xD8
```

Beim nächsten Block:

```text
fseek(file, file_offset, SEEK_SET)
current_block = file_offset / blockSize + 1
```

ACKs schreiben den neuen Offset über `sys_set_board_file_offset()` persistent zurück.

Damit kann ein unterbrochener Transfer grundsätzlich an einer gespeicherten Blockgrenze wieder aufgenommen werden, sofern Firmwaredatei, persistente OTA-Metadaten und State-Machine beim Neustart konsistent erhalten bleiben. Die Wiederaufnahmeentscheidung selbst wird zusätzlich durch die Startup-/`dev_otavercode_compare()`-Logik beeinflusst.

---

# Teil III – Metadaten-, Header- und Integritätsprüfungen

## 21. Cloud-Metadaten aus `0033`

Der Parser übernimmt:

```text
softwareCode
softwareVer
ssid
fileMD5
fileSize
otaFileDownloadAddr
```

Diese Werte werden in `otaDeviceInfo` geschrieben. Der Parser besitzt keine robuste semantische Validierung für leere URL, syntaktisch falsche MD5-Strings oder Versionsreihenfolge. `fileSize==0` verhindert allerdings später den Step-1->3-Übergang.

---

## 22. Download-MD5-Prüfung

`board_ota_http_download()` ruft nach Download auf:

```text
ota_check_device_otaFile_md5() @ 0x1A370
```

Die Funktion:

1. verlangt `otaDeviceInfo.fileSize != 0`,
2. alloziert `fileSize+1` Bytes und nullt den Puffer,
3. öffnet `/cache/phnixIot_device_OTA`,
4. liest `fileSize` Bytes per `fread`,
5. berechnet MD5 über **exakt `fileSize` Bytes des Puffers**,
6. erzeugt daraus den 32-stelligen Hexstring,
7. normalisiert die erwartete MD5 auf Großschreibung,
8. vergleicht den berechneten String mit `otaDeviceInfo.fileMD5`.

Auffällig: Der Rückgabewert von `fread()` wird geloggt, aber nicht gegen `fileSize` als harte Gleichheitsbedingung geprüft. Bei einer kürzeren Datei sind die ungelesenen Bytes aufgrund des zuvor genullten Puffers 0 und fließen damit in die MD5 über die erwartete Länge ein. Eine echte kürzere Datei wird dadurch normalerweise an der MD5 scheitern, aber es existiert keine separate Dateigrößenprüfung an dieser Stelle.

---

## 23. Separate Board-Metadaten C357

`set_ota_bin_info()` @ `0x1CEA0` baut einen eigenen FC10-Metadatenframe für:

```text
Register 0xC357
Quantity 19 Register = 38 Datenbytes
```

Datenbereich:

```text
SSID       2 Byte, big-endian
fileSize   4 Byte, big-endian
fileMD5    32 ASCII-Byte
```

Vor dem Kopieren wird die MD5 für diesen Boardframe von ASCII `A-Z` nach `a-z` normalisiert.

Danach folgt wieder `crc16()` und `uart485_send_data_to_board()`.

Das Board erhält damit Dateigröße und erwartete MD5 separat vom eigentlichen C5A8-Blockstrom.

---

## 24. Kein erkannter Firmware-Dateiheader im C5A8-Transferpfad

`set_board_update_bin()` behandelt `/cache/phnixIot_device_OTA` als opaken Bytestrom.

Im untersuchten Transferpfad gibt es **keinen Parser**, der am Dateianfang etwa prüft:

```text
Magic/Header
softwareCode im Binärfile
softwareVer im Binärfile
SSID im Binärfile
interne Firmwarelänge
interne Firmware-CRC
```

`softwareCode`, `softwareVer` und `ssid` stammen aus OTA-/Board-Metadaten und werden protokollseitig verwendet; sie werden in diesem Pfad nicht mit einem eingebetteten Firmwareheader verglichen.

---

## 25. Streaming-MD5 in `set_board_update_bin()` ist keine wirksame Integritätsprüfung

`set_board_update_bin()` initialisiert bei Offset 0 zusätzlich einen globalen MD5-Kontext und finalisiert ihn am Transferende.

Allerdings wird der an `MD5Update()` übergebene lokale Längenwert bei Funktionsbeginn auf 0 gesetzt:

```text
0x1C7E8..0x1C7EC -> local length = 0
```

Im vollständigen Funktionskörper wurde keine spätere Zuweisung eines von 0 verschiedenen Wertes an genau diese lokale Variable gefunden.

Der Aufruf bei:

```text
0x1CD3C -> MD5Update(ctx, data, local_length)
```

arbeitet daher in diesem Build effektiv mit Länge 0. `MD5Final()` am EOF wird anschließend lediglich ausgegeben; eine Prüfung gegen die erwartete Cloud-MD5 findet hier nicht statt.

Die produktive Firmwareintegritätsprüfung vor dem Transfer ist somit `ota_check_device_otaFile_md5()` nach dem HTTP-Download.

---

## 26. SoftwareCode / SoftwareVer / SSID

### `softwareCode` / `softwareVer`

Nach erfolgreichem Download werden OTA-Code/-Version über `sys_set_dev_otavercode()` persistent gespeichert. `dev_otavercode_compare()` wird später für Resume-/Versionszustände verwendet.

Im C5A8-Datenstrom selbst werden Code und Version nicht mitgesendet und nicht gegen Binärdaten geprüft.

### `SSID`

SSID wird persistent gespeichert und in mehreren OTA-RS485-Frames verwendet, unter anderem C350, C357 und C5A8. Im C5A8-Block steht SSID direkt vor total/current block.

Auch SSID wird im untersuchten Code nicht aus der Firmwaredatei selbst gelesen oder gegen einen Dateikopf geprüft.

---

## 27. Gesamtfluss nach erfolgreichem Download

```text
0033
 -> otaDeviceInfo füllen
 -> app+0x3C=3
 -> C350 server code/version handshake
 -> C36E status 2
 -> board_ota_step=1
 -> cloud/status request succeeds
 -> fileSize !=0
 -> board_ota_step=3
 -> HTTP download
 -> MD5 check
 -> persist offset=0, fileLen, MD5, OTA code/version
 -> board_ota_step=6
 -> C5A8 block #1
 -> C371 ACK
 -> persist offset += blockSize
 -> C5A8 next block
 -> ...
 -> final ACK advances offset to >=fileLen (or sets fileLen directly)
 -> next set_board_update_bin() returns 0
 -> board_ota_step=12
 -> wait for Board completion/result handlers
```

---

## 28. Besonders geeignete Breakpoints für einen isolierten Labortest

Nur zur Beobachtung, ohne Download-/Dateiänderung:

```gdb
b *0x19064
```

JSON ist dort vollständig ausgewertet, aber Zustands-/Datei-/Persistenzeingriffe des `0033`-Parsers haben noch nicht begonnen.

Für State-Transition-Beobachtung:

```gdb
b *0x1BCA0   # unmittelbar bei Step 1
b *0x1D79C   # Step 3
b *0x1D860   # unmittelbar vor board_ota_http_download()
```

Für späteren Blocktransfer:

```gdb
b *0x1CE78   # unmittelbar vor set_board_update_bin()
b *0x1CDF0   # unmittelbar vor uart485_send_data_to_board() des C5A8-Frames
b *0x1B72C   # Eingang des C371-ACK-Handlers
```

Der Breakpoint `0x1D860` ist der letzte direkte Callsite-Punkt vor dem HTTP-Download aus der Step-3-State-Machine.
