# PHNIX `phnixIot4G` – OTA-/Firmware-Update-Pfad

Stand: 2026-08-23

Grundlage ist die statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`. Diese Datei konzentriert sich auf die Firmware-Update-Logik für **DTU/LTE-Modul** und **Mainboard**. Detailanalysen einzelner Teilpfade liegen zusätzlich in den weiteren `PHNIX_phnixIot4G_*.md`-Dateien im selben Verzeichnis.

## Kurzfazit

`phnixIot4G` besitzt zwei getrennte OTA-Pfade:

```text
DTU-Self-Update
MQTT OTA_GET -> JSON Code 0032 -> URL/MD5/Size übernehmen
 -> HTTP/curl Download nach /data/phnixIot4G_OTA
 -> MD5 über das erwartete fileSize-Fenster prüfen
 -> chmod +x
 -> mv auf /data/phnixIot4G_OTA /data/phnixIot4G
 -> killall -9 phnixIot4G
```

und:

```text
Mainboard-Update
MQTT OTA_GET -> JSON Code 0033 -> URL/MD5/Size/SSID übernehmen
 -> HTTP/curl Download nach /cache/phnixIot_device_OTA
 -> MD5 über das erwartete fileSize-Fenster prüfen
 -> Metadaten persistent speichern
 -> Mainboard-OTA-State-Machine
 -> RS485 OTA-Register C350/C357/C36C/C36E/C371/C378/C5A8/C544
```

Die beiden Pfade teilen MQTT/JSON-Dispatcher und Download-/Progress-Infrastruktur, sind danach aber klar getrennt.

Wichtige Korrektur gegenüber älteren Fassungen: `fileSize` wird in den lokalen MD5-Prüffunktionen **nicht als tatsächliche Dateilänge validiert**. Die Funktionen lesen höchstens `fileSize` Bytes in einen vorher genullten Puffer und hashen anschließend immer exakt `fileSize` Bytes. `fileSize` ist damit praktisch das MD5-Prüffenster.

---

## 1. Exakte OTA_GET-Code-Dispatch-Tabelle

`ota_code_handle()` (`0x19958`) parst das JSON-Feld `code`, wandelt es numerisch um und durchsucht eine feste Tabelle bei `0x91C20`.

| Code dezimal | MQTT-String | Handler | Bedeutung |
|---:|---:|---|---|
| 12 | `0012` | `ota_dtu_set_ota_info()` | DTU-OTA-Metadaten / Cloud-Version setzen |
| 32 | `0032` | `down_dtu_ota_url_handle()` | DTU-OTA Download/Install starten |
| 33 | `0033` | `down_board_ota_url_handle()` | Mainboard-OTA Downloaddaten übernehmen |
| 62 | `0062` | `down_check_dtu_ver_handle()` | erneutes DTU-Version-Reporting anfordern |
| 63 | `0063` | `down_check_board_ver_handle()` | erneutes Mainboard-Version-Reporting anfordern |
| 73 | `0073` | `down_board_cancel_ota_handle()` | Mainboard-OTA abbrechen |
| 58 | `0058` | `down_dtu_cancel_ota_handle()` | DTU-OTA abbrechen |
| 103 | `0103` | `down_board_ver_bcakroll_handle()` | Mainboard-Rollback anfordern |
| 114 | `0114` | `device_reset_handle()` | DTU Reset/Reboot-Command |

---

## 2. DTU-Self-Update

`ota_dtu_set_ota_info()` übernimmt mindestens:

```text
softwareCodeCloud
softwareVerCloud
fileMD5
fileSize
```

`ota_dtu_set_ota_file_download_info()` übernimmt zusätzlich `otaFileDownloadAddr`.

Downloadziel:

```text
/data/phnixIot4G_OTA
```

Installation nach erfolgreicher lokaler Prüfung:

```sh
chmod a+x /data/phnixIot4G_OTA
mv /data/phnixIot4G_OTA /data/phnixIot4G
killall -9 phnixIot4G
```

Der Neustart erfolgt damit offenbar über einen Plattform-/Supervisor-Mechanismus außerhalb dieses ELF. Welcher konkrete Supervisor verantwortlich ist, ist aus diesem Binary allein nicht belegt.

DTU-Cloudcodes:

```text
0042 Progress
0052 Erfolg
0082 Upgrade fehlgeschlagen
0092 Firmwaredownload fehlgeschlagen
```

---

## 3. Download-/MD5-Prüfung

Der Progresscallback `assetsManagerProgressFunc()` meldet nur exakt:

```text
25
50
75
100 Prozent
```

Für Board-OTA wird dazu `ota_device_send_ota_progress()` / Code `0043` verwendet.

### 3.1 Keine echte Dateilängenvalidierung

Sowohl:

```text
ota_check_dtu_otaFile_md5()    @ 0x1A0C8
ota_check_device_otaFile_md5() @ 0x1A370
```

arbeiten sinngemäß so:

```c
expected = fileSize;
buf = malloc(expected + 1);
memset(buf, 0, expected + 1);

nread = fread(buf, 1, expected, fp);

MD5Init(&ctx);
MD5Update(&ctx, buf, expected);   // nicht nread
MD5Final(...);
```

`nread` wird zwar geloggt, aber nicht als Akzeptanzbedingung gegen `expected` geprüft.

Folgen:

```text
Datei kürzer als fileSize:
  fehlende Bytes bleiben 0x00 im vorbereiteten Puffer und werden so gehasht.

Datei länger als fileSize:
  nur die ersten fileSize Bytes werden gehasht.
```

Damit ist `fileSize` lokal ein **MD5-Prüffenster**.

Für den PHNIX-Pfad wurde keine zusätzliche RSA-/ECDSA-/Firmware-Signaturprüfung gefunden. Generischer Aliyun-OTA-Code im ELF ist vom hier beschriebenen PHNIX-`CMD_OTA`-Pfad zu unterscheiden.

---

## 4. Mainboard-OTA: eingehende Daten und Persistenz

`down_board_ota_url_handle()` ruft:

```text
ota_device_set_ota_file_download_info()
```

auf. Übernommen werden:

```text
softwareCode
softwareVer
ssid
fileMD5
fileSize
otaFileDownloadAddr
```

Firmwaredatei:

```text
/cache/phnixIot_device_OTA
```

Persistenz:

```text
/data/phnixIot_device_statisic
/data/phnixIot_device_OTA_INFO
```

Relevante persistente Felder sind unter anderem:

```text
Board-OTA-SSID
Firmware-MD5
Firmware-Länge
bestätigter Dateioffset
SoftwareCode
SoftwareVersion
```

`board_ota_step` selbst ist RAM-only. Resume basiert auf persistenten Firmwaremetadaten und Offset plus erneutem C544/C350/C357-Handshake.

---

## 5. Mainboard-OTA-State-Machine

Der permanente Thread:

```text
fota_board_thread_handle()
```

führt `dtu_upgrade_pro()` aus.

Zentrale Eingangssperre:

```c
if (get_dtu_run_step() != 11)
    return;
```

Bestätigte Zustände:

| Step | Bedeutung |
|---:|---|
| `1` | Upgrade-Erlaubnis / Cloud-Anfrage |
| `3` | Board-Firmware herunterladen und MD5 prüfen |
| `6` | Firmware via RS485 übertragen |
| `12` | Warte-/Abschlusszustand; Boardantworten treiben weiter |
| `5` | Erfolg an Cloud melden |
| `10` | Fehler an Cloud melden |
| `7` | Cancel-/Recovery-Pfad |
| `8` | Rollback-/Backroll-Steuerung |
| `9` | Rollback-Ergebnis an Cloud melden |

Regulär:

```text
Step 1
 -> Step 3
 -> HTTP Download + MD5
 -> Persistenz
 -> Step 6
 -> RS485 Firmwaretransfer
 -> Step 12
 -> Board-Ergebnis
 -> Step 5 oder Step 10
```

---

## 6. Mainboard-RS485-OTA-Register

| Register | Handler |
|---:|---|
| `0xC350` | `board_set_ser_ver_handle()` |
| `0xC357` | `board_set_bin_info_handle()` |
| `0xC36C` | `board_recv_cancel_upgrade_handle()` |
| `0xC36E` | `board_is_allow_upg_handle()` |
| `0xC371` | `board_updata_bin_handle()` |
| `0xC378` | `board_reply_verbackroll_handle()` |
| `0xC5A8` | `board_set_updata_bin_handle()` |
| `0xC544` | `board_softcode_ver_handle()` |

Parserseitig sind OTA und normaler Modbusbetrieb getrennt. Auf der UART-TX-Seite teilen sie sich dagegen denselben Sendeslot.

---

## 7. Version / Cloud-Handshake

Ausgehend:

```text
ota_dtu_send_version_to_phnix()    -> 0002
ota_device_send_version_to_phnix() -> 0003
```

Mainboard-Version `0003` enthält:

```text
deviceCode
deviceSoftwareCode
deviceSoftwareVer
ssid
```

Upgrade-/Allow-Report Mainboard:

```text
0023
```

---

## 8. UART-/Warmlink-Abhängigkeit

### 8.1 Gemeinsamer Single-Slot

`uart485_send_data_to_board()`:

```text
0x1562C
```

schreibt nicht direkt auf `/dev/ttyHSL2`, sondern nur in:

```text
uart485WriteBuf   0x928DC   2048 Byte
uart485SendFlag   0x930DC
uart485SendLen    0x930E0
UART-FD           0x930E4
```

Pseudocode:

```c
if (len <= 2048) {
    memcpy(uart485WriteBuf, data, len);
    uart485SendLen = len;
    uart485SendFlag = 1;
}
```

Es ist **keine Queue**.

### 8.2 Kein Mutex im Sendeslot

In diesem Pfad wurde keine Absicherung über:

```text
pthread_mutex_lock/unlock
sem_wait/sem_post
```

oder eine atomare Reservierung gefunden.

Damit ist statisch folgende Race-Condition möglich:

```text
Producer A schreibt OTA-Frame
 -> flag = 1

Producer B schreibt vor dem physischen write() einen normalen Frame
 -> gleicher Puffer überschrieben
 -> Länge überschrieben
```

### 8.3 Physisches Senden

Der permanente UART-Thread läuft über `getDevParameter()` und führt bei gesetztem Sendeflag schließlich:

```c
write(uart_fd, uart485WriteBuf, uart485SendLen);
```

aus.

Danach werden bei jedem Rückgabewert ungleich `-1` Länge und Flag gelöscht. Ein partieller `write()` wird nicht gegen die gewünschte Länge geprüft.

### 8.4 Normaler RX läuft während OTA weiter

Der UART-RX-Thread wird durch Mainboard-OTA nicht grundsätzlich beendet. OTA-Register werden intern behandelt; anderer Modbusverkehr kann weiterhin den normalen Warmlink-/MQTT-Uplink erreichen.

---

# 9. Cloud-Abhängigkeiten des Mainboard-OTA – Offline-VM und statische Zuordnung

Dieser Abschnitt ergänzt gezielt die bisher offene Frage, **welche Cloudzustände und MQTT-Publishes die lokale Mainboard-OTA-State-Machine tatsächlich blockieren**.

## 9.1 Dynamisch auf Offline-VM bestätigt

Im isolierten Lauf wurde mit dem unveränderten Originaldienst bestätigt:

```text
Cloud/Credential-Pfad bleibt ohne erfolgreiche Cloud bei dtu_run_step 7.

Wird der Schreibversuch auf dtu_run_step 7 am Eingang von
set_dtu_run_step() nur zur Laufzeit auf 11 umgebogen,
verarbeitet der Dienst ein lokal eingespeistes 0033.

Danach:
C350 -> Boardstatus 1.

Ohne erfolgreiche Rückgaben von ali_mqtt_push_OTA_msg()
stoppt der weitere Ablauf dort.

Werden die für den Pfad relevanten OTA-Publishes lokal mit Rückgabewert 0
bestätigt, folgen:
Firmwaredownload -> MD5 -> C357 -> Status 2 -> C5A8.

Der resultierende RS485-Verkehr war bytegenau identisch mit dem
cloudgesteuerten Referenzlauf.
```

Damit ist dynamisch bestätigt, dass die Cloud im eigentlichen Board-Transfer nicht die Firmwareblöcke transformiert. Sie liefert Metadaten/Steuerzustand und erwartet Statuspublishes; Download-, MD5-, State-Machine- und RS485-Funktionen können danach unverändert lokal laufen.

---

## 10. `dtu_run_step`: vollständige Setter und Bedeutung

Storage:

```text
app            @ 0x988FC
dtu_run_step   = app + 0x07 = 0x98903
```

Accessor:

```text
set_dtu_run_step() @ 0x1D2F8
get_dtu_run_step() @ 0x1D328
```

`set_dtu_run_step()` selbst macht nur:

```c
app[7] = (uint8_t)value;
```

### 10.1 Alle direkten Setter

Im gesamten ELF wurden nur vier direkte konstante Aufrufer gefunden:

| Adresse | Funktion | Wert | Bedeutung |
|---:|---|---:|---|
| `0x141AC` | `uart485_init()` | `4` | UART-/Board-Identitätsinitialisierung beginnen |
| `0x147AC` | `uart485_get_productKey()` | `5` | initialer Board-ProductKey-Request wurde gesendet |
| `0x1FD5C` | `aliMqtt_handle_thread()` | `7` | Cloud-Geräte-/Credential-Abfrage läuft / DeviceSecret fehlt |
| `0x1FDE8` | `aliMqtt_handle_thread()` | `11` | `ali_mqtt_init()` erfolgreich; regulärer MQTT-Betriebszustand |

### 10.2 Bedeutung von 7

Der relevante Code liegt in `aliMqtt_handle_thread()`:

```c
set_Error_Flag(9);

while (deviceSecret[0] == 0) {
    set_dtu_run_step(7);
    httpAPI_communicationDevice_queryiotdevice();
    sleep(5);
}
```

Damit ist `7` **nicht allgemein "irgendein Cloudfehler"**, sondern genauer:

> Board-/Modemidentität ist weit genug initialisiert, aber die Cloud-Geräte-/Credential-Phase ist noch nicht abgeschlossen; `deviceSecret` fehlt und der HTTP-Query wird wiederholt.

Ein dauerhafter Fehler dieser Abfrage hält den Dienst deshalb praktisch auf 7.

Nach vorhandenem DeviceSecret folgt:

```c
ret = ali_mqtt_init();
while (ret == -1) {
    ret = ali_mqtt_init();
    sleep(3);
}

set_dtu_run_step(11);
```

Während dieser MQTT-Init-Retryschleife wird nicht erneut ein anderer run_step gesetzt; typischerweise bleibt daher der vorherige Wert 7 erhalten, bis `ali_mqtt_init()` erfolgreich ist.

### 10.3 Bedeutung von 11

Nach erfolgreichem `ali_mqtt_init()`:

```c
Clear_Error_Flag(10);
set_dtu_run_step(11);
set_dtu_sta(4);
led_communication_on();
ota_dtu_send_version_to_phnix();
```

`11` bedeutet daher statisch:

> MQTT-Initialisierung des normalen Cloudpfads erfolgreich; FOTA darf produktiv laufen.

`dtu_upgrade_pro()` prüft explizit auf exakt 11.

### 10.4 Leser von `dtu_run_step`

Direkte `get_dtu_run_step()`-Aufrufer im ELF:

```text
uart485_get_productKey()
dtu_upgrade_pro()
```

Es wurden keine direkten Leser in Watchdog-, Restart- oder Statistikfunktionen gefunden.

### 10.5 Bewertung eines dauerhaften Force-11

**Permanent ab Prozessstart: unsicher.**

Grund: `uart485_init()` möchte zunächst Step 4 setzen. `uart485_get_productKey()` sendet seinen aktiven 8-Byte-Identitätsrequest nur, wenn `get_dtu_run_step()==4`, und setzt anschließend 5. Ein globaler Hook, der schon diese Werte auf 11 umbiegt, kann daher die normale Board-Identitätsinitialisierung stören.

**Erst nach bereits erfolgreicher UART-/Boardidentität und nur während des lokalen OTA: vertretbar.**

Wichtig: Das Erzwingen von 11 erzeugt **keinen MQTT-Handle** und setzt auch nicht automatisch:

```text
dtu_sta = 4
LED-Status
Error-Flags
DeviceSecret
```

Der Cloudthread kann weiterhin alle fünf Sekunden seinen Credential-HTTP-Query versuchen.

Das Erzwingen von 11 aktiviert direkt nur die beiden bekannten Leserpfade; praktisch entscheidend ist dabei `dtu_upgrade_pro()`.

---

## 11. `ali_mqtt_push_OTA_msg()` – Erfolgssemantik

Funktion:

```text
ali_mqtt_push_OTA_msg() @ 0x1F9B0
```

Sie prüft zunächst:

```text
SIM card status == 1
IOT_MQTT_CheckStateNormal(handle) > 0
```

ansonsten:

```text
return -1
```

Danach ruft sie:

```text
IOT_MQTT_Publish(...)
```

auf.

Bei Publish-Rückgabewert `< 0`:

```text
MQTT handle destroy
app+0x14 Fehlerzähler ++
return -1
```

Bei Publish-Rückgabewert `>= 0` gilt der Publish als erfolgreich. Die Board-OTA-Wrapper normalisieren diesen Fall auf `0`.

Damit ist für einen lokalen Stub:

```text
return 0
```

vollständig ausreichend und entspricht der von der State-Machine erwarteten Erfolgssemantik.

Hinweis: Ein Stub direkt am Eingang von `ali_mqtt_push_OTA_msg()` überspringt die normalen MQTT-/Statistik-Nebenwirkungen. Das ist für einen isolierten Test erwünscht, bedeutet aber, dass die Cloud-TX-Statistik nicht dem echten Cloudlauf entspricht.

---

## 12. Alle Mainboard-OTA-Publishes über `ali_mqtt_push_OTA_msg()`

### 12.1 Mainboard-Version `0003`

```text
ota_device_send_version_to_phnix() @ 0x18A38
ali_mqtt_push_OTA_msg() call       @ 0x18B48
```

Verwendet über:

```text
dtu_upload_board_info() @ 0x1D408
```

In `dtu_upgrade_pro()` wird dieser Pfad nur ausgeführt, wenn `ota_info+0x19 != 0`. Das Flag wird unter anderem durch eingehendes Cloudkommando `0063` gesetzt.

Bei Publishfehler bricht der aktuelle `dtu_upgrade_pro()`-Durchlauf früh ab.

**Bewertung:** bedingter Blocker, aber **nicht Teil der kleinsten normalen 0033-Sequenz**, solange `ota_info+0x19 == 0`.

### 12.2 Upgrade-Erlaubnis / Boardstatus `0023`

```text
ota_device_send_is_can_ota_to_phnix() @ 0x18D04
ali_mqtt_push_OTA_msg() call          @ 0x18DA4
Rückkehrstelle                        @ 0x18DA8
JSON code                             = 0023
```

Format:

```json
{"cmd":"CMD_OTA","code":"0023","param":{"deviceCode":"...","isAllowDtuOTA":"...","ssid":"..."}}
```

Aufrufer:

```text
board_request_upgrade() @ 0x1D4E4
  -> in Step 1 bei 0x1D760

direkter Statusreport in dtu_upgrade_pro()
  -> 0x1D69C
```

Fehlersemantik:

```c
if (publish < 0)
    return aus dtu_upgrade_pro();
```

Im Step-1-Pfad bleibt dadurch `board_ota_step == 1`.

Auch der direkte Statusreport bei `0x1D69C` blockiert den restlichen Durchlauf, solange Code `0023` nicht erfolgreich publiziert wird.

**Bewertung:** zwingend lokal zu bestätigen.

### 12.3 Progress `0043`

```text
ota_device_send_ota_progress() @ 0x1910C
ali_mqtt_push_OTA_msg() call   @ 0x191AC
Rückkehrstelle                 @ 0x191B0
JSON code                      = 0043
```

Es existieren zwei semantisch unterschiedliche Verwendungen desselben Codes.

#### A: HTTP-Downloadfortschritt

`assetsManagerProgressFunc()` ruft `ota_device_send_ota_progress()` bei 25/50/75/100 % auf.

Der Rückgabewert wird **ignoriert**; der curl-Progresscallback gibt anschließend immer `0` zurück.

```c
ota_device_send_ota_progress(percent); // return ignoriert
return 0;
```

**Bewertung:** nicht state-machine-blockierend. Für den kleinsten Hook müsste dieser Publish nicht bestätigt werden.

#### B: RS485-Transferfortschritt

`board_updata_bin_handle()` setzt bei bestätigtem Transfer ungefähr alle 30 Blöcke:

```text
app[0] = 4
```

bei:

```text
0x1B938..0x1B944
```

`dtu_upgrade_pro()` sieht dies und ruft:

```text
board_dowmload_rep() @ 0x1D434
 -> ota_device_send_ota_progress()
```

bei `0x1D6F8` auf.

Schlägt dieser Publish fehl, springt `dtu_upgrade_pro()` direkt zum Ende. Solange `app[0] == 4` bestehen bleibt, wird der Fortschrittsreport erneut versucht und die weitere State-Machine nicht abgearbeitet.

**Bewertung:** Transfer-Progress `0043` ist blockierend und muss lokal bestätigt werden.

Da Download- und Transferfortschritt denselben JSON-Code verwenden, ist es in einem eng gescopten lokalen OTA-Stub einfacher und unkritisch, **alle `0043` während der aktiven lokalen Session mit 0 zu bestätigen**.

### 12.4 Erfolg `0053`

```text
ota_device_send_ota_finish() @ 0x191C0
ali_mqtt_push_OTA_msg() call  @ 0x19250
JSON code                     = 0053
wrapper                        board_ota_rep() @ 0x1D568
```

In `board_ota_step == 5`:

```c
if (board_ota_rep() == 0)
    set_board_ota_step(12);
else
    return;
```

**Bewertung:** zwingend. Ohne erfolgreichen `0053` bleibt Step 5 hängen.

### 12.5 Upgradefehler `0083`

```text
ota_device_send_ota_Failed() @ 0x19264
ali_mqtt_push_OTA_msg() call  @ 0x19304
JSON code                     = 0083
wrapper                        board_upgrade_fail_rep() @ 0x1D4B8
```

In `board_ota_step == 10`:

```c
sys_set_board_file_offset(0);
if (board_upgrade_fail_rep() == 0)
    set_board_ota_step(12);
else
    return;
```

**Bewertung:** zwingend für sauberen Fehler-/Cancel-Abschluss. Ohne erfolgreichen `0083` bleibt Step 10 bestehen.

### 12.6 Rollback-/Initialisierungsergebnis `0113`

```text
ota_device_send_Initialization() @ 0x19318
ali_mqtt_push_OTA_msg() call      @ 0x193A8
JSON code                         = 0113
wrapper                           board_verbackroll_result_repo() @ 0x1D594
```

In Step 9 wird nur bei erfolgreichem Publish auf 12 gewechselt.

**Bewertung:** nur erforderlich, wenn der lokale Lauf den Rollback-/Backroll-Pfad benutzt.

### 12.7 Firmwaredownloadfehler `0093`

```text
ota_device_send_ota_FirmwareDownloadFailed() @ 0x193BC
ali_mqtt_push_OTA_msg() call                 @ 0x1944C
JSON code                                    = 0093
```

`board_ota_http_download()` ruft diesen Report bei curl-/Transportfehler auf:

```c
ota_device_send_ota_FirmwareDownloadFailed(); // return ignoriert
return -1;
```

Der Rückgabewert des Publishes beeinflusst die weitere Fehlerbehandlung nicht. Die State-Machine zählt den Downloadfehler unabhängig davon und wechselt nach den vorgesehenen Retries zu Step 10.

**Bewertung:** nicht erforderlich, um die lokale State-Machine weiterlaufen zu lassen.

---

## 13. Kleinste notwendige lokale Publish-Menge

Für einen normalen lokal ausgelösten Mainboard-OTA über bereits eingespeistes `0033`:

| Code | Zweck | Muss lokal Erfolg liefern? | Grund |
|---:|---|---|---|
| `0023` | Upgrade-Erlaubnis / Boardstatus | **ja** | blockiert Step 1 und Statuspreamble |
| `0043` Download | HTTP-Progress | nein | Callback ignoriert Rückgabewert |
| `0043` Transfer | RS485-Transferprogress | **ja** | blockiert `dtu_upgrade_pro()` |
| `0053` | Upgrade erfolgreich | **ja** | sonst Step 5 bleibt stehen |
| `0083` | Upgrade fehlgeschlagen | **ja** | sonst Step 10 bleibt stehen |
| `0093` | Download fehlgeschlagen | nein | Return wird ignoriert |
| `0113` | Rollback-Ergebnis | nur Rollback | sonst Step 9 bleibt stehen |
| `0003` | Board-Version | bedingt | nur wenn `ota_info+0x19` aktiv ist |

Praktische Minimalmenge für den Standardpfad:

```text
0023
0043
0053
0083
```

Optional:

```text
0113   nur bei Rollback
0003   nur wenn Version-Refreshflag aktiv ist
```

Da `0043` für Download- und Transferprogress identisch ist, kann der lokale Stub während einer aktiven Session beide Arten gefahrlos mit `0` beantworten; nötig für die State-Machine ist davon nur der Transferprogress.

---

## 14. Weitere bedingte Cloudblocker vor dem eigentlichen Board-Step

`dtu_upgrade_pro()` besitzt vor den normalen Step-Blöcken zusätzliche Cloudreport-Pfade.

### 14.1 `ota_info+0x0D`

Wenn gesetzt:

```text
dtu_pub_devinfo() @ 0x1D3DC
 -> aliMqtt_push_error_topic_to_phnix()
```

Bei Fehler wird der aktuelle `dtu_upgrade_pro()`-Durchlauf beendet.

Dieses Flag gehört nicht zum normalen lokalen `0033`-Pfad. Für einen reproduzierbaren Offline-Lauf sollte vor Aktivierung geprüft werden, dass es 0 ist, statt einen weiteren globalen Cloudstub einzuführen.

### 14.2 `ota_info+0x19`

Wenn ungleich 0, wird:

```text
dtu_upload_board_info()
 -> code 0003
```

versucht. Bei Fehler wird ebenfalls der Durchlauf beendet.

Auch dieses Flag ist kein notwendiger Bestandteil der normalen `0033`-Sequenz. Deterministischer Minimalansatz:

```text
vor Start beide bedingten Reportflags prüfen/auf normalen Idlewert bringen
statt zusätzliche Cloudpfade pauschal zu faken.
```

---

## 15. Sicheres Scoping eines MQTT-Publish-Stubs

Ein globales `ali_mqtt_push_OTA_msg() -> 0` ist **unsicher**.

Die Funktion wird auch für DTU-OTA, Versionsreports und Resetpfade verwendet. Ein permanenter Stub könnte damit unabhängigen State-Machines einen nicht stattgefundenen Cloud-Erfolg vortäuschen.

### 15.1 `board_ota_step == 12` reicht nicht

Step 12 bedeutet sowohl:

```text
Idle/neutral nach Startup
```

als auch:

```text
aktiver Wartezustand nach C5A8/Boardaktion
```

und kann daher nicht allein als Aktivkriterium dienen.

### 15.2 `ota_info+0x16` allein reicht ebenfalls nicht bis zum Ende

Relevante Adresse:

```text
ota_info       @ 0x98A7C
ota_info+0x16  @ 0x98A92
```

Beim akzeptierten `0033` wird dieser Wert auf `2` gesetzt und im weiteren OTA-Pfad verwendet. Beim finalen Board-Erfolg kann er jedoch bereits auf 0 gehen, **bevor** der abschließende Cloud-Erfolgsreport `0053` publiziert wurde.

Deshalb darf der Publish-Stub nicht allein an dieses Byte gekoppelt werden.

### 15.3 Empfohlen: eigener `local_ota_active`-Latch

Aktivieren nur, wenn ein **bewusst lokal eingespeistes Mainboard-`0033` erfolgreich verarbeitet wurde**.

Geeigneter statischer Marker im Parser:

```text
ota_device_set_ota_file_download_info()
0x19080: ota_info+0x16 = 2
```

Der Laufzeitcontroller kann den eigenen Latch direkt nach diesem bestätigten lokalen Parserpfad setzen.

Beenden **erst nach terminalem Rücksprung auf Step 12**, weil dann der jeweilige Abschlussreport bereits erfolgreich behandelt wurde:

```text
Fehler / Cancel -> Step 10 -> 0083 -> set Step 12 @ ca. 0x1D744
Erfolg          -> Step 5  -> 0053 -> set Step 12 @ ca. 0x1DA38
Rollback        -> Step 9  -> 0113 -> set Step 12 @ ca. 0x1DC90
```

Damit bleibt der Stub auch für den letzten notwendigen Publish aktiv und wird anschließend sicher abgeschaltet.

Prozessende/Restart muss den externen Latch ebenfalls zwangsweise löschen.

---

## 16. Minimaler Laufzeit-Hook ohne ELF-Änderung

Ziel:

```text
keine echte Cloudverbindung notwendig
keine permanente Änderung der ELF
Original-Download bleibt unverändert
Original-MD5 bleibt unverändert
Original-board_ota_step bleibt unverändert
Original-RS485-OTA-Funktionen bleiben unverändert
```

### 16.1 Hook A: nur Step 7 während lokaler OTA-Session auf 11 umbiegen

Buildspezifischer Einstieg:

```text
set_dtu_run_step() @ 0x1D2F8
```

Pseudocode des Laufzeit-Hooks:

```c
on_enter_set_dtu_run_step(value):
    if (local_ota_active && value == 7)
        value = 11;

    call_original(value);
```

Wichtig:

```text
4 nicht verändern
5 nicht verändern
11 normal durchlassen
```

Damit wird die UART-/ProductKey-Initialisierung nicht beschädigt.

Der Hook soll erst nach bereits vorhandener Boardidentität und nach bewusst lokal akzeptiertem `0033` aktiv sein.

### 16.2 Hook B: gezielter OTA-Publish-Erfolg

Einstieg:

```text
ali_mqtt_push_OTA_msg() @ 0x1F9B0
```

Nur bei `local_ota_active` wird der JSON-Payload geprüft.

Pseudocode:

```c
if (!local_ota_active)
    return original_ali_mqtt_push_OTA_msg(buf, len);

code = parse_local_json_code(buf);

switch (code) {
case 23:   // 0023
case 43:   // 0043
case 53:   // 0053
case 83:   // 0083
    return 0;

case 113:  // 0113, nur wenn bewusst Rollback getestet wird
    return rollback_test_enabled ? 0 : original(...);

default:
    return original(...);
}
```

Für einen strikt cloudfreien Offline-Lauf sollte bei aktivem lokalen Hook ein nicht explizit freigegebener Code **nicht automatisch als Erfolg gefälscht** werden. Besser ist dort Halt/Logging, damit keine fremde OTA- oder Reset-State-Machine unbeabsichtigt fortgesetzt wird.

### 16.3 Build-spezifischer Debugger-/ptrace-Ansatz

Da `set_dtu_run_step()` und `ali_mqtt_push_OTA_msg()` interne direkte ARM-Funktionen sind, ist klassisches `LD_PRELOAD` für diese direkten `BL`-Aufrufe nicht zuverlässig geeignet.

Für Labortests ist ein flüchtiger Debugger-/ptrace-Hook passender:

```text
Breakpoint/Funktionshook an 0x1D2F8
 -> nur r0=7 bei local_ota_active zu 11 ändern

Breakpoint/Funktionshook an 0x1F9B0
 -> bei erlaubtem Board-OTA-Code r0=0 setzen
 -> Funktion ohne Ausführung zum LR zurückkehren
```

Dies ist bewusst buildspezifisch und darf nur gegen das zu diesen Adressen passende ELF verwendet werden.

### 16.4 Wiederherstellung

Nach terminalem Step->12:

```text
local_ota_active = false
alle temporären Breakpoint-/Return-Hooks deaktivieren
kein weiteres Umschreiben von dtu_run_step
keine weiteren Publish-Fakes
```

Der Originaldienst läuft anschließend wieder mit seinen normalen Cloudbedingungen.

---

## 17. Nebenwirkungen von `dtu_run_step == 11`

Statische Cross-Reference-Prüfung:

```text
get_dtu_run_step()
```

wird direkt nur von:

```text
uart485_get_productKey()
dtu_upgrade_pro()
```

verwendet.

Damit wurden **keine direkten** Watchdog-, Reboot-, Restart- oder Statistikpfade gefunden, die allein durch den Wert 11 aktiviert würden.

Trotzdem gilt:

- Der Cloudthread läuft unabhängig weiter.
- Fehlt `deviceSecret`, kann er weiterhin alle fünf Sekunden `httpAPI_communicationDevice_queryiotdevice()` versuchen.
- Error-Flag 9 kann bestehen bleiben.
- `dtu_sta` wird durch den Step-Hook allein nicht auf 4 gesetzt.
- LED-/Cloudstatus wird durch den Step-Hook allein nicht auf "normal" gesetzt.
- `ali_mqtt_push_OTA_msg()` würde ohne separaten Stub weiterhin an SIM-/MQTT-Statechecks scheitern.

Ein Entry-Stub von `ali_mqtt_push_OTA_msg()` überspringt außerdem die normalen Statistikinkremente des echten Publishpfads. Das ist eine erwartete Abweichung des Offline-Labors, beeinflusst aber nicht den Board-OTA-RS485-Datenstrom.

---

## 18. Vollständige TX-Produzenten des gemeinsamen UART-Slots

Direkte Aufrufer von `uart485_send_data_to_board()` im untersuchten ELF:

| Senderfunktion | Sendestelle | Typ | Während Board-OTA relevant? |
|---|---:|---|---|
| `check_mcu_get_sta()` | `0x14D44` | normale RX-getriggerte DTU-Statusantwort | **ja, möglich** |
| `getDevParameter()` | `0x15458` | normale Antwort/ACK auf Mainboardtelegramm | **ja, möglich** |
| `uart485_get_device_info()` | `0x156AC` | Initialisierung/Device-Info | normalerweise nein nach Startup |
| `Check485Statue()` | `0x156DC` | periodischer 8-Byte-485-Healthprobe | **ja** |
| `dtu_reply_recv_status()` | `0x1AF98` | OTA C37B-Statusreply | OTA, nicht pausieren |
| `reply_cancel_upgrade()` | `0x1B208` | OTA Cancel C36A | OTA, nicht pausieren |
| `dtu_to_board()` | `0x1B474` | OTA Rollback C375 | OTA, nicht pausieren |
| `set_sev_code_and_ver()` | `0x1C734` | OTA C350 | OTA, nicht pausieren |
| `set_board_update_bin()` | `0x1CDF0` | OTA C5A8 | OTA, nicht pausieren |
| `set_ota_bin_info()` | `0x1D208` | OTA C357 | OTA, nicht pausieren |
| `aliMqtt_topic_get_msg_arrive()` | `0x1EFEC` | normaler MQTT->RS485-Downlink | **ja bei echter Cloud** |

### 18.1 `Check485Statue()`

Wird aus `TimerHandler()` ungefähr bei `0xAE20` aufgerufen.

Die Funktion prüft vor dem Einlegen ihres 8-Byte-Probes immerhin:

```c
if (uart485SendFlag == 0)
    uart485_send_data_to_board(probe, 8);
```

Das reduziert Kollisionen, ersetzt aber keinen Mutex: zwischen Prüfung und `memcpy()` kann ein anderer Producer den Slot belegen.

### 18.2 Normaler MQTT-Downlink

`aliMqtt_topic_get_msg_arrive()` legt empfangene Cloud-Modbusframes direkt über:

```text
0x1EFEC -> uart485_send_data_to_board()
```

in denselben Slot.

Bei einem bewusst cloudfreien lokalen OTA tritt dieser Producer praktisch nicht auf. Bei einem echten cloudverbundenen OTA kann er dagegen statisch mit dem OTA-Thread konkurrieren.

### 18.3 RX-getriggerte normale Antworten

`check_mcu_get_sta()` und der Sendepfad in `getDevParameter()` laufen im UART-RX-Kontext.

Der gesamte UART-Thread darf für OTA **nicht pausiert werden**, weil derselbe Thread die benötigten C36E/C371/C378/... Antworten empfangen und dispatchen muss.

---

## 19. Welche Producer können für einen realen Transfer pausiert werden?

### Sicher/naheliegend

**Normaler MQTT->RS485-Downlink (`aliMqtt_topic_get_msg_arrive`)**

Während eines bewusst lokalen/cloudfreien OTA kann dieser Producer vollständig unterdrückt werden. Er ist weder für UART-RX noch für OTA-TX nötig.

**`uart485_get_device_info()`**

Ist ein Initialisierungspfad und sollte nach vollständig abgeschlossenem Startup nicht mehr für den OTA benötigt werden. Falls er unerwartet parallel auftritt, kann sein TX bis nach OTA verschoben werden.

### Mit überschaubarem Risiko, aber dynamisch zu validieren

**`Check485Statue()`**

Der periodische Probe-TX kann für das kurze OTA-Fenster unterdrückt werden, ohne den UART-RX-Thread anzuhalten. Statisch ist aber nicht vollständig belegt, welche Kommunikationsfehler-/Statistikfolgen ein längeres Unterdrücken besitzt. Für einen realen Transfer sollte dies zunächst im isolierten Trace geprüft werden.

### Nicht als ganzen Thread pausieren

**`getDevParameter()` / UART-RX-Thread**

Nicht pausieren. Er ist für die OTA-Antworten erforderlich.

**`check_mcu_get_sta()` und normale RX-getriggerte ACKs innerhalb `getDevParameter()`**

Die einzelnen TX-Aktionen könnten theoretisch während eines aktiven OTA-Fensters unterdrückt oder verzögert werden, aber ihre Protokollpflicht gegenüber dem Mainboard ist statisch nicht ausreichend geklärt. Daher derzeit **nicht als "gefahrlos pausierbar" bestätigt**.

### OTA-Producer

Folgende Sender niemals für den OTA pausieren:

```text
dtu_reply_recv_status
reply_cancel_upgrade
dtu_to_board
set_sev_code_and_ver
set_ota_bin_info
set_board_update_bin
```

---

## 20. Kollisionsbewertung während C5A8

`board_ota_step == 6` ist nur der aktive Sendeschritt. Nach erfolgreichem `set_update_board_bin_by_485()` wechselt der Dienst unmittelbar wieder auf Step 12 und wartet auf die Boardantwort.

Deshalb ist ein Schutz, der nur auf:

```text
board_ota_step == 6
```

achtet, zu eng.

Für die tatsächliche Transferphase ist besser:

```text
local_ota_active
&& gespeicherte file_len > 0
&& bestätigter offset < file_len
&& board_ota_step in {6,12}
```

zu betrachten.

Der Single-Slot erlaubt statisch tatsächlich folgendes Szenario:

```text
OTA-Thread legt C5A8 ab
 -> uart485SendFlag = 1

bevor UART-Thread write() ausführt,
legt normaler Producer einen Frame ab
 -> C5A8 wird im globalen Puffer überschrieben
```

Es gibt im Sendeslot selbst keinen Schutz dagegen.

**Bewertung:** reale Überschreibung ist statisch möglich, aber für den konkreten Wärmepumpenbetrieb noch nicht dynamisch nachgewiesen.

Für einen realen Transfer ist daher die risikoärmste Reihenfolge:

1. normalen MQTT->RS485-Downlink während der lokalen OTA-Session sperren;
2. periodischen `Check485Statue()`-TX zunächst nur beobachten und bei tatsächlichem Auftreten gezielt unterdrücken;
3. UART-RX niemals anhalten;
4. RX-getriggerte Normalantworten zunächst loggen, nicht blind unterdrücken;
5. OTA-TX-Produzenten vollständig unverändert lassen.

---

## 21. Empfohlener minimaler Offline-Lauf

Vorbedingungen:

```text
UART/Boardidentität bereits vollständig vorhanden
kein aktiver DTU-Self-OTA
kein Rollback außer bewusst getestet
ota_info+0x0D == 0
ota_info+0x19 == 0
```

Ablauf:

```text
1. lokal 0033 in den Originaldispatcher einspeisen
2. nach bestätigtem Parserpfad local_ota_active setzen
3. nur set_dtu_run_step(7) -> 11 umbiegen
4. nur Board-OTA-Publishes 0023/0043/0053/0083 lokal mit 0 bestätigen
5. 0113 nur falls Rollback bewusst Teil des Tests ist
6. Original-HTTP-Download laufen lassen
7. Original-MD5 laufen lassen
8. Original-C350/C357/C5A8/C371-State-Machine laufen lassen
9. keine echte Cloudkommunikation erzeugen
10. nach terminalem Step->12 alle temporären Hooks entfernen
```

Damit werden nur die zwei künstlichen Offline-Abhängigkeiten ersetzt:

```text
Cloud-ready Gate dtu_run_step==11
notwendige Publish-Erfolgsrückgaben
```

Der eigentliche Firmware- und Buspfad bleibt Originalcode.

---

## 22. Sicherheitsbewertung

| Eingriff | Bewertung |
|---|---|
| `set_dtu_run_step(7)->11` permanent ab Start | **unsicher**, kann ProductKey-/UART-Startup stören |
| `7->11` nur bei lokal aktivem Board-OTA nach fertigem Startup | **vertretbar für isolierten Lauf** |
| `ali_mqtt_push_OTA_msg()->0` global | **unsicher**, beeinflusst fremde DTU-/Reset-/OTA-Pfade |
| gezielter Stub nur für aktive lokale Board-OTA-Codes | **vertretbar** |
| nur `board_ota_step==12` als Stub-Gate | **unsicher/mehrdeutig** |
| eigener `local_ota_active`-Latch bis terminal Step->12 | **empfohlen** |
| UART-RX-Thread pausieren | **nicht zulässig für OTA-Funktion** |
| normaler MQTT->RS485-Downlink während lokalem OTA sperren | **sinnvoll** |
| periodischen 485-Probe-TX temporär sperren | **wahrscheinlich sinnvoll, dynamisch validieren** |
| RX-getriggerte Normalantworten blind sperren | **noch nicht sicher bewertet** |

---

## 23. Noch offen

Nach dieser Analyse sind die wesentlichen Cloud-Abhängigkeiten des normalen lokalen `0033`-Pfads geschlossen.

Noch gezielt offen:

- exakte Zeitbasis und Semantik aller OTA-Timerfelder in `app @ 0x988FC`;
- dynamischer Nachweis, ob während eines echten C5A8-Transfers tatsächlich normale RX-getriggerte TX-Frames entstehen;
- dynamische Kollisionsprüfung des Single-Slot-Puffers unter realistischem Parallelverkehr;
- externer Supervisor des DTU-Self-Updates nach `killall -9 phnixIot4G`.

Für einen realen Wärmepumpentest sollte vor allem die UART-Slot-Konkurrenz noch mit einem rein beobachtenden Trace validiert werden; die Cloudabhängigkeit selbst kann dagegen jetzt gezielt und minimal lokal ersetzt werden.
