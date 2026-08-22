# Warmlink-/LTE-DTU Reverse Engineering und OTA-Firmware

Stand: 2026-08-22

Diese Dokumentation sammelt den aktuellen Reverse-Engineering-Stand zum in der untersuchten FoxAir/PHNIX-Wärmepumpe eingesetzten Warmlink-/LTE-DTU. Schwerpunkt sind Hardware, SIMCom/OpenLinux-Zugriff, PHNIX-/Linked-Go-/Aliyun-Cloudkommunikation, OTA-Download und das Mainboard-Firmware-Update über RS485.

> **Datenschutz/Sicherheit:** Eindeutige Gerätekennungen, IMEI, DeviceCode, DeviceName, DeviceSecret, ProductKey, Tokens und ähnliche Werte werden hier nicht veröffentlicht. Beispiele verwenden `XXX` bzw. Platzhalter. Die Untersuchung erfolgte zunächst read-only/offline; aktive OTA-/Flash-Versuche sind gesondert zu behandeln.

## Kurzfassung

Der rekonstruierte Pfad ist:

```text
PHNIX / Linked-Go / Aliyun Cloud
        |
        | MQTT über TCP/1883
        | OTA_UPDATE -> Cloud
        | OTA_GET    <- Cloud
        v
SIMCom SIM7600E-H / OpenLinux
        |
        | /data/phnixIot4G
        | otaFileDownloadAddr aus MQTT-Code 0033
        | libcurl-Download
        v
/cache/phnixIot_device_OTA
        |
        | Dateigröße + MD5 prüfen
        | OTA-State/Resume in /data/phnixIot_device_OTA_INFO
        v
/dev/ttyHSL2, 9600 8N1
        |
        | Modbus-RTU-ähnliches proprietäres OTA-Profil
        v
Wärmepumpen-Mainboard
```

Ein vorhandenes Mainboard-Firmwareimage wurde direkt aus dem LTE-Modem gesichert:

```text
Pfad:   /cache/phnixIot_device_OTA
Größe:  287598 Byte
MD5:    CEB6A4BF386FF644E23E410023E74673
SHA256: 6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Im Image steht bei Dateioffset `0x42780`:

```text
824006440033
```

Sehr wahrscheinlich:

- Softwarecode: `82400644`
- Versionscode: `0033`
- Cloud-/Anzeigedarstellung: **V3.3**

---

## 1. Hardware des LTE-DTU

### Trägerplatine

Auf der untersuchten DTU-Platine ist aufgedruckt:

- `MXL290`
- Board-Datum `2021-05-25`
- B/T `1.6 mm`
- C/T `1 oz`

Eine öffentliche technische Dokumentation der MXL290-Platine wurde bisher nicht gefunden. Es handelt sich sehr wahrscheinlich um eine kundenspezifische PHNIX-/Warmlink-DTU-Trägerplatine.

### Mobilfunkmodul

Auf dem Modul ist sichtbar:

```text
Z30AN S2-107EQ
```

Die vollständige PN `S2-107EQ-Z30AN` gehört zum **SIMCom SIM7600E-H**. Dies wurde anschließend direkt per AT-Kommandos bestätigt.

Beispiel:

```text
Manufacturer: SIMCOM INCORPORATED
Model: SIMCOM_SIM7600E-H
Revision: SIM7600M22_V1.1
```

Weitere Firmwareangaben:

```text
LE11B04SIM7600M22_2U_OL
SIM7600M22_B04V02_191014
```

Das Suffix `_OL` passt zum vorhandenen OpenLinux-System.

Gerätespezifische IMEI/Seriennummern werden ausschließlich als `XXX` dokumentiert.

---

## 2. USB, Windows-Treiber und AT

Der Micro-USB-Anschluss der MXL290-Platine führt zum SIM7600E-H. Nach Installation des SIMCom-Treibers erscheinen unter Windows mehrere SimTech-Interfaces, u. a.:

- SIMCom HS-USB AT Port 9001
- SIMCom HS-USB Diagnostics 9001
- SIMCom HS-USB NMEA 9001
- weitere SIMCom-USB-Funktionen

Der AT-Port funktioniert. Bei den virtuellen USB-COM-Ports ist die im Terminal eingestellte Baudrate nicht mit einer realen UART-Baudrate gleichzusetzen.

Nützliche Identifikationsbefehle:

```text
AT
ATI
AT+SIMCOMATI
AT+CGMR
AT+CGMM
AT+CGMI
```

---

## 3. ADB / OpenLinux-Zugang

ADB-Unterstützung ist vorhanden:

```text
AT+CUSBADB=?
+CUSBADB: (0-1)
```

ADB war aktiviert:

```text
+CUSBADB: 1
```

Mit Android Platform Tools:

```text
adb devices
0123456789ABCDEF    device
```

Root-Shell:

```text
adb shell
/ # id
uid=0(root) gid=0(root)
```

System:

```text
Linux mdm9607-perf 3.18.20
ARMv7
Qualcomm Technologies, Inc MDM9607
```

Kernel-Build:

```text
Linux version 3.18.20
#1 PREEMPT Fri Oct 18 11:45:05 CST 2019
```

CPU:

```text
ARMv7 Processor rev 5
Hardware: Qualcomm Technologies, Inc MDM9607
```

---

## 4. Dateisystem und Persistenz

Wichtige Mounts:

```text
ubi0:rootfs   /          ubifs ro
ubi0:usrfs    /data      ubifs rw
ubi0:cachefs  /cache     ubifs rw
/dev/ubi1_0   /firmware  ubifs ro
```

Ungefähre Größen:

```text
/          ~49 MB
/data      ~10 MB
/cache     ~40 MB
/firmware  ~38 MB
```

Wichtig: `/data` und `/cache` sind **persistente UBIFS-Dateisysteme**, keine tmpfs-Verzeichnisse. Damit überleben insbesondere

```text
/cache/phnixIot_device_OTA
/data/phnixIot_device_OTA_INFO
```

einen normalen Reboot bzw. Spannungsausfall. Das ist Teil des vorgesehenen Resume-Mechanismus.

Ein vollständiges read-only Backup wurde per `adb pull` von `/data` und `/cache` erstellt. Unix-Sockets/FIFOs werden von `adb pull` erwartungsgemäß übersprungen.

---

## 5. PHNIX-Anwendung auf dem LTE-Modem

Hauptprozess:

```text
/data/phnixIot4G
```

Größe und Hashes:

```text
Größe:  747440 Byte
MD5:    CDCF34DA5F039CEB1084DA835425F3A1
SHA256: 7C573431F0A67620D473419644A83A4F4DC04B8A91BDE5923C74A63BA1EAEDB7
```

ELF-Eigenschaften:

- 32-Bit ARM, little endian
- `ET_EXEC`
- Entry `0xA0C8`
- Interpreter `/lib/ld-linux.so.3`
- Build-ID `af4dcae12639bedce833ee5efa5da009777b6319`
- GCC 4.9.2
- nicht stripped
- 2544 Symbole
- partielle DWARF-Debugdaten

Relevante Bibliotheken:

- `libcurl.so.5`
- `libjson-c.so.3`
- `libmosquitto.so.1`
- OpenSSL 1.0.0
- Aliyun-IoT-SDK-Komponenten

Watchdog:

```text
/data/helloworld
```

Das Skript prüft zyklisch `phnixIot4G` und startet den Prozess bei Bedarf neu.

---

## 6. Serielle Schnittstellen

Die laufende `phnixIot4G`-Instanz hat u. a. offen:

```text
/dev/ttyHSL2
```

Die tatsächliche Termios-Konfiguration wurde live gelesen:

```text
speed 9600 baud
8 Datenbits
keine Parität
1 Stopbit
kein Hardware-Flow-Control
```

Kurz: **9600 8N1**.

`ttyHSL2` hängt an:

```text
/sys/devices/78b0000.serial/tty/ttyHSL2
```

Zusätzlich läuft eine Linux-Konsole auf:

```text
/sbin/getty -L ttyHSL0 115200 console
```

Damit:

- `ttyHSL0` = Linux-Konsole, 115200 Baud
- `ttyHSL2` = PHNIX-UART Richtung Mainboard/RS485, 9600 8N1

Die sichtbare `TTL`-Beschriftung der MXL290-Platine dürfte zu einem UART-/Konsolenbereich gehören; Pinout/Pegel sind nicht vollständig verifiziert.

---

## 7. Laufende Threads und File Descriptors

`phnixIot4G` läuft mit 13 Threads. Die Threadnamen sind nicht individualisiert und heißen sämtlich `phnixIot4G`.

Beobachtete Kernel-Waits:

- `hrtimer_nanosleep`
- `poll_schedule_timeout`
- `select`
- `diagchar_read`

Ein Thread wartet eindeutig auf dem Qualcomm-DIAG-Pfad (`diagchar_read`). Andere Threads warten in `poll`/`select` und gehören sehr wahrscheinlich zu UART/MQTT/weiteren I/O-Pfaden.

Wichtige offene FDs:

```text
fd 0  -> /dev/null
fd 1  -> /dev/null
fd 2  -> /dev/null
fd 21 -> /dev/ttyHSL2
fd 22 -> MQTT-TCP-Socket
```

Daraus folgt auch, warum normale Debugausgaben nicht über `logread` sichtbar werden: stdout/stderr zeigen auf `/dev/null`.

`gdb` und `gdbserver` sind auf dem System vorhanden. Live-Debugging ist grundsätzlich möglich, wurde aber für die bisherigen Ergebnisse nicht benötigt.

---

## 8. PHNIX-/Aliyun-Cloudverbindung

Live beobachtet:

```text
lokal:  10.x.x.x:<ephemeral>
remote: 8.209.64.105:1883
status: ESTABLISHED
prozess: phnixIot4G
```

Die konkrete lokale Carrier-IP wird nicht dokumentiert.

Im Binary:

```text
tcp://%s.iot-as-mqtt.eu-central-1.aliyuncs.com:1883
```

Damit ist bestätigt:

- MQTT über **unverschlüsseltes TCP/1883**
- Internetverkehr über `rmnet_data0`
- `bridge0` war `NO-CARRIER` und transportierte den LTE-Verkehr nicht

---

## 9. Linked-Go-/PHNIX-HTTP-Endpunkte

Statisch vorhanden:

```text
http://cloud.linked-go.com:84
```

```text
/cloudservice/api/phnixiot/queryiotdevice.json?appKey=%s
/cloudservice/api/communicationDevice/queryiotdevice.json?appKey=%s
/cloudservice/api/communicationDevice/createDeviceBySign
/cloudservice/api/communicationDevice/create_communicationDeviceLog.json
/.../dtuLog/report.json
```

Diese APIs dienen Geräteidentität/Registrierung/Logging. Ein statischer Mainboard-Firmware-Endpunkt existiert im Binary **nicht**.

---

## 10. MQTT Topics und Richtung

In `ali_mqtt_init()` (`0x1F034`):

```text
Publish normal: /<productKey>/<deviceName>/user/update
Publish OTA:    /<productKey>/<deviceName>/user/OTA_UPDATE
Subscribe:      /<productKey>/<deviceName>/user/get
Subscribe OTA:  /<productKey>/<deviceName>/user/OTA_GET
```

OTA_GET wird mit QoS 1 und Callback

```text
aliMqtt_topic_ota_get_msg_arrive
```

abonniert.

Gerätespezifische `productKey`, `deviceName` und `deviceSecret` werden in dieser Doku ausschließlich als `XXX` dargestellt.

---

## 11. Geräteidentität und Credentials

RAM-Strukturen im Binary:

| Variable | VA | Größe | Bedeutung |
|---|---:|---:|---|
| `productKey` | `0x94EB8` | 33 | Aliyun ProductKey |
| `deviceName` | `0x94EDC` | 33 | Cloudfeld `device_code` |
| `deviceSecret` | `0x94F00` | 65 | Cloudfeld `device_secret` |
| `deviceID` | `0x94F44` | 13 | Gerätekennung |

Cloudantworten liefern sinngemäß:

```json
{
  "error_code": 0,
  "object_result": {
    "device_code": "XXX",
    "product_key": "XXX",
    "device_secret": "XXX"
  }
}
```

Eine Gerätekennung wird außerdem persistent in `/data/phnixIot_device_statisic` gespeichert. Der konkrete Wert wird nicht veröffentlicht und als `XXX` behandelt.

---

## 12. OTA-Kommandos

### DTU-OTA

```json
{"cmd":"CMD_OTA","code":"0002","param":{"deviceCode":"XXX","dtuHardwareCode":"%s","dtuSoftwareCode":"%s","dtuSoftwareVer":"%s"}}
```

```json
{"cmd":"CMD_OTA","code":"0022","param":{"deviceCode":"XXX","isAllowDtuOTA":"%d"}}
```

```json
{"cmd":"CMD_OTA","code":"0042","param":{"deviceCode":"XXX","progress":"%d"}}
```

```json
{"cmd":"CMD_OTA","code":"0052","param":{"deviceCode":"XXX","progress":"100"}}
```

Fehler:

```json
{"cmd":"CMD_OTA","code":"0082","param":{"deviceCode":"XXX","upgradeFailed":"1"}}
```

```json
{"cmd":"CMD_OTA","code":"0092","param":{"deviceCode":"XXX","FirmwareDownloadFailed":"1"}}
```

### Mainboard-/Device-OTA

Versions-/Checkbericht:

```json
{
  "cmd":"CMD_OTA",
  "code":"0003",
  "param":{
    "deviceCode":"XXX",
    "deviceSoftwareCode":"82400644",
    "deviceSoftwareVer":"0033",
    "ssid":"0033"
  }
}
```

Freigabe-/Statusmeldung:

```json
{"cmd":"CMD_OTA","code":"0023","param":{"deviceCode":"XXX","isAllowDtuOTA":"1","ssid":"0033"}}
```

Fortschritt/Erfolg/Fehler:

```json
{"cmd":"CMD_OTA","code":"0043","param":{"deviceCode":"XXX","progress":"%d","ssid":"%04x"}}
{"cmd":"CMD_OTA","code":"0053","param":{"deviceCode":"XXX","progress":"100","ssid":"%04x"}}
{"cmd":"CMD_OTA","code":"0083","param":{"deviceCode":"XXX","upgradeFailed":"1","ssid":"%04x"}}
{"cmd":"CMD_OTA","code":"0093","param":{"deviceCode":"XXX","FirmwareDownloadFailed":"1","ssid":"%04x"}}
{"cmd":"CMD_OTA","code":"0113","param":{"deviceCode":"XXX","Initialization":"%d"}}
```

Wichtige Korrektur: `board_request_upgrade()` sendet **Code `0023`**, nicht `0003`. `0003` ist der Versions-/Checkbericht.

---

## 13. Eingehender OTA-Dispatcher

Empfangspfad:

```text
Aliyun MQTT /user/OTA_GET
  -> aliMqtt_topic_ota_get_msg_arrive()       0x1ED98
  -> MQTT_get_data                            0x94AB4
  -> ota_code_handle()                        0x19958
  -> json_tokener_parse()
  -> Feld "code" als Integer
  -> ota_hanldle[]                            0x91C20
```

Rekonstruierte Dispatch-Tabelle:

| Code | Darstellung | Handler |
|---:|---|---|
| 12 | `0012` | `ota_dtu_set_ota_info` `0x1841C` |
| 32 | `0032` | `down_dtu_ota_url_handle` `0x19580` |
| **33** | **`0033`** | **`down_board_ota_url_handle` `0x19688`** |
| 62 | `0062` | Handler bei `0x19704` |
| 63 | `0063` | `down_check_board_ver_handle` `0x19734` |
| 73 | `0073` | `down_board_cancel_ota_handle` `0x19764` |
| 58 | `0058` | `down_dtu_cancel_ota_handle` `0x19828` |
| 103 | `0103` | `down_board_ver_bcakroll_handle` `0x197F4` |
| 114 | `0114` | Handler bei `0x1986C` |

`cmd` wird im zentralen Dispatcher nicht validiert; ausgewertet wird der numerische `code`.

---

## 14. Exaktes eingehendes Mainboard-OTA-JSON

`ota_device_set_ota_file_download_info()` (`0x18DB8`) liest aus `param` genau:

| Feld | Typ | Verwendung |
|---|---|---|
| `softwareCode` | String | Ziel-Softwarecode |
| `softwareVer` | String | z. B. `V3.3`, wird intern zu `0033` |
| `ssid` | String | Update-/Sessionkennung |
| `fileMD5` | String | erwarteter MD5, 32 Zeichen |
| `fileSize` | Integer | erwartete Bytezahl |
| `otaFileDownloadAddr` | String | vollständige Download-URL |

Semantisch vollständiges Beispiel:

```json
{
  "cmd": "CMD_OTA",
  "code": "0033",
  "param": {
    "softwareCode": "82400644",
    "softwareVer": "V3.3",
    "ssid": "0033",
    "fileMD5": "CEB6A4BF386FF644E23E410023E74673",
    "fileSize": 287598,
    "otaFileDownloadAddr": "http://XXX/XXX"
  }
}
```

Für diesen Handler sind `deviceCode`, Token oder Signatur nicht erforderlich.

---

## 15. Woher die Download-URL kommt

**Bewiesen:** Die vollständige URL kommt von der Cloud.

In `ota_device_set_ota_file_download_info()` wird `param.otaFileDownloadAddr` gelesen und direkt in den OTA-Puffer kopiert.

In `ota_download_device_otaFile()` (`0x19E70`) wird dieser String unverändert als `CURLOPT_URL` an libcurl übergeben.

Zieldatei:

```text
/cache/phnixIot_device_OTA
```

Es gibt keine statische Firmware-Basis-URL und keine Zusammensetzung aus Base-URL + Dateiname.

Für den Boarddownload setzt die Anwendung keine eigenen HTTP-Header, Cookies, Bearer-Tokens oder Basic-Auth-Daten. Falls der Download autorisiert ist, muss die Authentisierung in der URL selbst liegen (z. B. Query-Signatur) oder der Download ist anonym.

Aktueller Stand: **Ein neuer/alternativer echter Firmware-Link wurde noch nicht gefunden**, weil die dafür nötige live eingehende MQTT-Code-0033-Nachricht fehlt.

---

## 16. Firmwaredownload und Prüfung

Ablauf:

```text
ota_device_set_ota_file_download_info() 0x18DB8
  -> dtu_upgrade_pro()                  0x1D5C0
  -> board_ota_http_download()         0x1D520
     -> ota_download_device_otaFile()  0x19E70
     -> ota_check_device_otaFile_md5() 0x1A370
```

Prüfung:

- erwartet exakt `fileSize` Bytes
- liest Firmware aus `/cache/phnixIot_device_OTA`
- berechnet MD5
- vergleicht MD5-String
- **keine RSA/ECDSA/HMAC-Signaturprüfung im Mainboard-OTA-Pfad**

Bei Downloadfehler wird Code `0093` gemeldet.

Daraus folgt: Eine Firmware eines anderen Gerätes mit identischem Mainboard-/Softwareprofil ist grundsätzlich sehr wahrscheinlich übertragbar, sofern Softwarecode, Version/SSID, Dateigröße und MD5 korrekt gesetzt werden. Eine geräteindividuelle Bindung der Firmware wurde im untersuchten OTA-Pfad nicht gefunden.

---

## 17. Trigger des Firmware-Checks

Rekonstruierter Ablauf:

```text
Mainboard-Info über RS485, Register 0xC544
  -> unpack_mcu_modbus()                 0x1DDE8
  -> board_softcode_ver_handle()         0x1C1BC
  -> Upload-Flag / Boardcodes
  -> fota_board_thread_handle()          0x1DD4C
  -> dtu_upgrade_pro()                   0x1D5C0
  -> dtu_upload_board_info()             0x1D408
  -> ota_device_send_version_to_phnix()  0x18A38
  -> MQTT OTA_UPDATE Code 0003
  -> Cloud OTA_GET Code 0033
```

Bewiesen:

- kein zyklischer HTTP-Firmwarepoller
- kein statischer Firmware-API-Aufruf
- `0003` meldet Mainboard-Softwarecode/-version/-SSID an die Cloud
- `0023` ist Freigabe-/Statusmeldung

Ein manuelles MQTT-Publish von `0003` wäre ein aktiver OTA-Check und wurde bislang nicht ausgeführt.

---

## 18. RS485-/UART-OTA-Protokoll

### Transport

`uart485_init()` (`0x14188`) öffnet `/dev/ttyHSL2` und setzt:

```text
9600 Baud, 8N1
```

`getDevParameter()` (`0x14D58`) prüft CRC und ruft `unpack_mcu_modbus()` (`0x1DDE8`) auf.

Für OTA wird verwendet:

- Slave: `0x63`
- Funktion: `0x10`
- CRC: Modbus CRC16, Init `0xFFFF`, Polynom `0xA001`

Testvektor `123456789` ergibt numerisch `0x4B37`, auf dem Draht `37 4B`.

### Register-/Handler-Tabelle

| Register | Bedeutung | Handler |
|---:|---|---|
| `0xC350` | Serverversion/Bestätigung | `board_set_ser_ver_handle` |
| `0xC357` | OTA-Metadaten/Bestätigung | `board_set_bin_info_handle` |
| `0xC36C` | Abbruchbestätigung | `board_recv_cancel_upgrade_handle` |
| `0xC36E` | OTA-Freigabe/Status | `board_is_allow_upg_handle` |
| `0xC371` | Block-ACK/Fortschritt | `board_updata_bin_handle` |
| `0xC378` | Rollback/Initialisierung | `board_reply_verbackroll_handle` |
| `0xC5A8` | Firmwareblock/Bestätigung | `board_set_updata_bin_handle` |
| `0xC544` | Mainboard-HW/SW-Info | `board_softcode_ver_handle` |

Intern tauchen teils `0x1Cxxx`-Werte auf; auf dem Draht werden die unteren 16 Bit `0xCxxx` verwendet.

---

## 19. OTA-Metadatenpaket an das Mainboard

Erzeugt von `set_ota_bin_info()` (`0x1CEA0`).

| Offset | Länge | Inhalt |
|---:|---:|---|
| 0 | 1 | Slave `0x63` |
| 1 | 1 | Funktion `0x10` |
| 2 | 2 | Register `0xC357`, big endian |
| 4 | 2 | Registerzahl `0x0013` |
| 6 | 1 | Datenlänge `0x26` |
| 7 | 2 | SSID, big endian |
| 9 | 4 | Firmwaregröße, big endian |
| 13 | 32 | MD5 als kleingeschriebener ASCII-Hexstring |
| 45 | 2 | Modbus CRC16 |

Gesamtlänge: **47 Byte**.

Ein separates Flashadressfeld existiert nicht.

---

## 20. Firmwareblöcke

Erzeugt von `set_board_update_bin()` (`0x1C7CC`).

| Offset | Länge | Inhalt |
|---:|---:|---|
| 0 | 1 | `0x63` |
| 1 | 1 | `0x10` |
| 2 | 2 | Register `0xC5A8` |
| 4 | 2 | `(payload_len + 6 + 1) / 2` |
| 6 | 1 | `payload_len` |
| 7 | 2 | SSID |
| 9 | 2 | Gesamtzahl Firmwarepakete |
| 11 | 2 | 1-basierte Paketnummer |
| 13 | N | Firmwaredaten |
| 13+N | 2 | CRC16 |

Standardmäßig:

```text
payload_len = 0xA8 = 168 Byte
```

Das Mainboard kann in seiner Freigabeantwort einen alternativen positiven Wert angeben.

Hinweis: Byte 6 entspricht in diesem proprietären Profil nur der Firmware-Nutzlastlänge, nicht dem gesamten üblichen Modbus-Bytecount.

---

## 21. ACK, Retry und Abschluss

`board_updata_bin_handle()` (`0x1B72C`) verarbeitet Register `0xC371`.

Nach SSID folgen drei 16-Bit-Werte:

1. Erfolgsmarker, erwartet `1`
2. ACK-Art: `1` = Block angenommen, `2` = Transfer vollständig
3. bestätigte Paketnummer

Bei ACK-Art 1 muss die Paketnummer dem erwarteten Block entsprechen. Danach wird der persistente Firmware-Byteoffset erhöht.

Retry:

- zunächst 3 Sendeversuche pro Block
- erneutes Senden nach 5-Tick-Timer
- gültiges ACK setzt Timer zurück und stellt 3 Versuche für nächsten Block bereit
- Status 4 = Push-Fehler
- Status 6 = Mainboard-Upgradefehler
- kompletter Push-/Upgradevorgang höchstens zweimal erneut
- danach Fehlercode `0083`
- Status 5 = Upgradeerfolg -> Code `0053` / 100 %

---

## 22. Resume und OTA_INFO

`/data/phnixIot_device_OTA_INFO` ist eine 220-Byte-Struktur.

Vorhandenes Beispiel enthält:

```text
V1.2
CEB6A4BF386FF644E23E410023E74673
82400644
0033
```

Rekonstruierte Struktur:

| Dateioffset | Inhalt |
|---:|---|
| `0x00` | 32-Bit gespeicherte Prüfsumme über die folgenden 216 Byte |
| `0x1C` | `V1.2` – DTU-/Strukturversion, nicht Mainboard V1.2 |
| `0xA5` | MD5, 32 Zeichen + NUL |
| `0xC6` | Softwarecode, 8 Zeichen + NUL |
| `0xCF` | Versionscode, 4 Zeichen + NUL |
| `0xD4` | bestätigter Firmware-Byteoffset, 32 Bit little endian |
| `0xD8` | Firmwaredateilänge, 32 Bit little endian |

SSID wird separat in `/data/phnixIot_device_statisic` bei Struktur-Offset `0x7C` gespeichert.

Nach jedem bestätigten Block schreibt `sys_set_board_file_offset()` den aktualisierten Offset. Damit kann ein Update nach Stromausfall fortgesetzt werden.

Die früher vermutete Interpretation von `V1.2` als Mainboard-Firmwareversion war falsch; es handelt sich nach statischer Analyse um eine DTU-/Strukturversionsinformation.

---

## 23. `phnixIot_device_statisic`

Datei:

```text
/data/phnixIot_device_statisic
```

Größe:

```text
128 Byte
```

Sie enthält persistente Geräte-/Statistikdaten und eine eindeutige Gerätekennung. Diese Kennung wird hier aus Datenschutzgründen ausschließlich als

```text
XXX
```

dokumentiert.

SSID für den Board-OTA-Pfad liegt bei Struktur-Offset `0x7C`.

---

## 24. Vorhandenes Firmwareimage

```text
/cache/phnixIot_device_OTA
```

Eigenschaften:

```text
Größe:   287598 Byte
MD5:     CEB6A4BF386FF644E23E410023E74673
SHA256:  6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
Initial SP:    0x2000EB90
Reset Handler: 0x080927D1
```

Das Image ist ein direktes ARM-Cortex-M-Firmwareimage, kein ZIP/Container.

Wahrscheinliche Imagebasis:

```text
0x08080000
```

Kennung bei Offset `0x42780`:

```text
824006440033
```

Daraus:

- Softwarecode `82400644`
- Versionscode `0033`
- sehr wahrscheinlich V3.3

Ein weiteres strukturiertes Feld im Image ist:

```text
823003140000
```

Die genaue Bedeutung ist noch offen.

---

## 25. Übertragbarkeit einer Firmware von einem anderen Gerät

Nach aktuellem Stand ist eine Firmware eines anderen Geräts mit identischem Mainboard-/Softwareprofil **technisch wahrscheinlich übertragbar**, weil:

- im Mainboard-OTA-Pfad keine Signaturprüfung gefunden wurde
- Firmwaredatei selbst keine erkennbare Gerätebindung benötigt
- geprüft werden Dateigröße und MD5
- Metadaten enthalten Softwarecode, Version, SSID, MD5 und Größe
- der eigentliche Transfer ist deterministisch über RS485 paketiert

Noch nicht praktisch bewiesen ist, ob zusätzlich server-/bootloaderseitige Kompatibilitätsregeln greifen.

Ein bloßes Kopieren einer neuen Datei nach `/cache/phnixIot_device_OTA` startet jedoch nicht automatisch den Flashvorgang; die OTA-State-Machine und passenden Metadaten müssen ebenfalls aktiv sein.

---

## 26. Neuer Firmware-Downloadlink – aktueller Stand

Kein aktueller oder alternativer Link ist statisch in den untersuchten Artefakten enthalten.

Insbesondere:

- keine URL in `phnixIot_device_OTA_INFO`
- keine URL im Firmwareimage
- keine Firmware-Basis-URL in `phnixIot4G`
- statische HTTP-APIs betreffen Geräteidentität/Logging

Die fehlende Information ist die live eingehende MQTT-Nutzlast **Code `0033`** für das konkrete Geräte-/Softwareprofil.

Mögliche Wege:

1. passiver Mitschnitt der unverschlüsselten MQTT-Verbindung auf TCP/1883 und Suche nach `/user/OTA_GET` bzw. `otaFileDownloadAddr`
2. bewusstes reproduziertes Senden des originalen `0003`-Versionsberichts und ausschließlich Empfang/Archivierung der Antwort

Ein aktiver `0003`-Check wurde bislang nicht durchgeführt.

---

## 27. Relevante Funktionen/Adressen

Auswahl:

```text
uart485_thread_handle                   0x14918
ota_device_send_version_to_phnix       0x18A38
ota_device_send_is_can_ota_to_phnix    0x18D04
ota_device_set_ota_file_download_info  0x18DB8
down_board_ota_url_handle              0x19688
ota_code_handle                        0x19958
ota_download_device_otaFile            0x19E70
ota_check_device_otaFile_md5           0x1A370
board_updata_bin_handle                 0x1B72C
board_is_allow_upg_handle               0x1BB3C
board_softcode_ver_handle               0x1C1BC
set_board_update_bin                    0x1C7CC
set_ota_bin_info                        0x1CEA0
set_ota_bin_info_by_485                 0x1D214
dtu_upload_board_info                   0x1D408
board_request_upgrade                   0x1D4E4
board_ota_http_download                 0x1D520
dtu_upgrade_pro                         0x1D5C0
fota_board_thread_handle                0x1DD4C
unpack_mcu_modbus                       0x1DDE8
aliMqtt_topic_ota_get_msg_arrive        0x1ED98
ali_mqtt_init                           0x1F034
ali_mqtt_push_OTA_msg                   0x1F9B0
```

---

## 28. Beweisgrade

### Bewiesen

- SIM7600E-H und OpenLinux/MDM9607
- ADB root möglich
- `phnixIot4G` ist die PHNIX-IoT-Anwendung
- `/dev/ttyHSL2` wird von `phnixIot4G` mit 9600 8N1 genutzt
- MQTT über TCP/1883
- Topic-Richtung `OTA_UPDATE` / `OTA_GET`
- vollständige Download-URL kommt aus `param.otaFileDownloadAddr`
- Mainboard-OTA-Code `0033` verarbeitet Download-Metadaten
- Download nach `/cache/phnixIot_device_OTA`
- Größen-/MD5-Prüfung, keine anwendungsseitige Signaturprüfung
- Slave `0x63`, Funktion `0x10`, OTA-Register und Paketlayouts
- Standardblockgröße 168 Byte
- ACK/Retry/Resume und persistenter Byteoffset
- `board_request_upgrade()` sendet `0023`, nicht `0003`
- `/cache` und `/data` sind persistent

### Sehr wahrscheinlich

- Firmwareimage `82400644 / 0033` = V3.3
- Imagebasis `0x08080000`
- Firmwaredownload ist anonym oder URL-basiert autorisiert
- Firmware eines anderen identischen Boards ist prinzipiell übertragbar

### Offen

- reale aktuelle Download-URL
- Ablaufzeit/Authentisierung einer echten URL
- ob die Cloud aktuell V3.5 oder eine andere neuere Version für `82400644` anbietet
- genaue Bootloader-Erase/Program/Verify-Schritte auf dem Mainboard
- genaue Bedeutung von `823003140000`
- praktische Validierung eines Updates mit fremdem Firmwareimage

---

## 29. Sicherheits-/Arbeitsregeln für weitere Tests

Vor aktiven Experimenten:

- vollständiges Backup von `/data`, `/cache` und vorhandener Firmware behalten
- eindeutige Gerätewerte immer als `XXX` veröffentlichen
- keine SIM7600-Modemfirmware auf Verdacht flashen
- neue Mainboard-Firmware zunächst offline auf Softwarecode, Version, Größe, Hash und Imagebasis prüfen
- bei einem Cloud-Check zunächst nur OTA-Metadaten/Download-Link erfassen
- Firmware erst nach separater Entscheidung auf das Mainboard schreiben

Diese Dokumentation ist Reverse Engineering der konkret untersuchten Anlage und keine offizielle PHNIX-/FoxAir-Herstelleranleitung.
