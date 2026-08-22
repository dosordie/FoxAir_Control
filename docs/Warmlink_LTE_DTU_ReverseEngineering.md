# Warmlink-/LTE-DTU Reverse Engineering und OTA-Firmware

Stand: 2026-08-22

Diese Dokumentation sammelt die aktuellen Reverse-Engineering-Erkenntnisse zum in der untersuchten FoxAir/PHNIX-Wärmepumpe eingesetzten Warmlink-/LTE-DTU. Schwerpunkt sind Hardware, SIMCom/OpenLinux-Zugriff, PHNIX-Cloudkommunikation und der OTA-Pfad für die Firmware des Wärmepumpen-Mainboards.

> **Wichtig:** Die folgenden Ergebnisse beziehen sich auf das konkret untersuchte Gerät. Andere PHNIX-/FoxAir-DTU-Varianten können abweichen. Eindeutige IMEI-, DeviceSecret-, Token- oder sonstige gerätespezifische Zugangsdaten werden bewusst nicht veröffentlicht.

## Kurzfassung

Der bisher rekonstruierte Pfad ist:

```text
PHNIX / Linked-Go / Aliyun Cloud
        |
        | MQTT, aktuell TCP/1883
        v
SIMCom SIM7600E-H mit OpenLinux
        |
        | /data/phnixIot4G
        |
        | Firmwaredownload -> /cache/phnixIot_device_OTA
        | MD5-Prüfung
        v
/dev/ttyHSL2
        |
        | UART -> DTU/RS485
        v
Wärmepumpen-Mainboard
```

Ein bereits vorhandenes Mainboard-Firmwareimage konnte direkt aus dem LTE-Modem gesichert werden:

```text
Pfad: /cache/phnixIot_device_OTA
Größe: 287598 Byte
MD5:   ceb6a4bf386ff644e23e410023e74673
```

Das Image enthält die Kennung:

```text
824006440033
```

Sehr wahrscheinlich bedeutet dies:

- Softwarecode: `82400644`
- Softwareversion: `0033` -> V3.3

Damit ist die im Cache gefundene Datei sehr wahrscheinlich die Mainboard-Firmware **82400644 V3.3**.

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

Die vollständige PN `S2-107EQ-Z30AN` gehört zum **SIMCom SIM7600E-H**.

Diese Identifikation wurde inzwischen zusätzlich direkt per AT-Kommandos bestätigt.

Beispielausgaben:

```text
Manufacturer: SIMCOM INCORPORATED
Model: SIMCOM_SIM7600E-H
Revision: SIM7600M22_V1.1
```

`AT+CGMR` bzw. `AT+SIMCOMATI` ergaben unter anderem:

```text
LE11B04SIM7600M22_2U_OL
SIM7600M22_B04V02_191014
```

Das Suffix `_OL` passt zum vorhandenen OpenLinux-System.

Die konkrete IMEI wird hier absichtlich nicht dokumentiert.

---

## 2. USB-Schnittstelle und Windows-Treiber

Der Micro-USB-Anschluss der MXL290-Platine führt tatsächlich zum SIM7600E-H. Nach Installation des SIMCom-Treibers erscheinen unter Windows mehrere SimTech-Interfaces, unter anderem:

- SIMCom HS-USB AT Port 9001
- SIMCom HS-USB Diagnostics 9001
- SIMCom HS-USB NMEA 9001
- weitere SIMCom-USB-Funktionen

Der AT-Port war im Test als COM-Port nutzbar.

Bei den virtuellen USB-COM-Ports ist die im Terminal eingestellte Baudrate nicht mit einer physischen UART-Baudrate gleichzusetzen. Der USB-CDC-/virtuelle COM-Pfad kann unabhängig von dieser Einstellung funktionieren.

---

## 3. ADB / OpenLinux-Zugang

Der SIM7600E-H unterstützt ADB. Das wurde über AT bestätigt:

```text
AT+CUSBADB=?
+CUSBADB: (0-1)
```

ADB war aktiviert:

```text
+CUSBADB: 1
```

Mit den offiziellen Android Platform Tools wurde das Gerät erkannt:

```text
adb devices
0123456789ABCDEF    device
```

`adb shell` liefert eine Root-Shell:

```text
/ # id
uid=0(root) gid=0(root)
```

### Systemdaten

```text
Linux mdm9607-perf 3.18.20
ARMv7
Qualcomm Technologies, Inc MDM9607
```

Kernel:

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

## 4. Dateisystem

Wichtige Mounts:

```text
ubi0:rootfs   /          ubifs ro
ubi0:usrfs    /data      ubifs rw
ubi0:cachefs  /cache     ubifs rw
/dev/ubi1_0   /firmware  ubifs ro
```

Damit ist insbesondere `/data` der persistente beschreibbare Bereich für die kundenspezifische DTU-Anwendung.

Ungefähre Größen im untersuchten System:

```text
/          ~49 MB
/data      ~10 MB
/cache     ~40 MB
/firmware  ~38 MB
```

---

## 5. PHNIX-Anwendung auf dem LTE-Modem

Der entscheidende Prozess ist:

```text
./phnixIot4G
```

Die Binärdatei liegt unter:

```text
/data/phnixIot4G
```

Größe im untersuchten Gerät:

```text
747440 Byte
```

Ein Watchdog-Skript hält den Prozess am Laufen:

```text
/data/helloworld
```

Das Skript prüft zyklisch, ob `phnixIot4G` läuft, und startet es bei Bedarf erneut:

```sh
PRO_NAME=phnixIot4G
...
cd /data
./${PRO_NAME} &
```

Damit ist bestätigt, dass die eigentliche PHNIX-/Warmlink-IoT-Logik direkt im OpenLinux-System des SIM7600E-H läuft.

---

## 6. Serielle Schnittstellen

Die laufende `phnixIot4G`-Instanz hatte unter anderem folgenden File Descriptor offen:

```text
/dev/ttyHSL2
```

Dies ist derzeit der stärkste Hinweis auf den UART-Pfad der PHNIX-Anwendung Richtung DTU-/RS485-Seite und damit zum Wärmepumpen-Mainboard.

Zusätzlich läuft eine Linux-Konsole auf:

```text
/sbin/getty -L ttyHSL0 115200 console
```

Daraus folgt:

- `ttyHSL0` = Linux-Konsole, 115200 Baud
- `ttyHSL2` = von `phnixIot4G` aktiv verwendeter UART, sehr wahrscheinlich Richtung Mainboard/RS485

Die sichtbare `TTL`-Beschriftung auf der MXL290-Platine könnte zu diesem UART-/Konsolenbereich gehören. Pinout und elektrische Pegel sind jedoch noch nicht vollständig bestätigt.

---

## 7. Laufende PHNIX-Cloudverbindung

`phnixIot4G` hatte eine aktive TCP-Verbindung:

```text
lokal:  10.214.199.17:<ephemeral>
remote: 8.209.64.105:1883
status: ESTABLISHED
```

Damit ist bestätigt, dass die untersuchte DTU aktuell MQTT über **TCP Port 1883** nutzt.

Im Binary befindet sich außerdem das Aliyun-Schema:

```text
tcp://%s.iot-as-mqtt.eu-central-1.aliyuncs.com:1883
```

Der Datenverkehr läuft über:

```text
rmnet_data0
```

mit einer Mobilfunk-IP im privaten Carrier-Netz.

Das lokale `bridge0`-Interface war im Test `NO-CARRIER` und transportierte den eigentlichen LTE-/MQTT-Verkehr nicht.

---

## 8. Linked-Go-/PHNIX-HTTP-Endpunkte

In `/data/phnixIot4G` wurden unter anderem folgende URLs bzw. Templates gefunden:

```text
http://cloud.linked-go.com:84
```

```text
/cloudservice/api/phnixiot/queryiotdevice.json?appKey=%s
/cloudservice/api/communicationDevice/queryiotdevice.json?appKey=%s
/cloudservice/api/communicationDevice/createDeviceBySign
/cloudservice/api/communicationDevice/create_communicationDeviceLog.json
```

Weitere Strings:

```text
queryIotDevice
httpAPI_queryiotdevice
httpAPI_createDeviceBySign
httpAPI_communicationDevice_queryiotdevice
```

Diese Endpunkte scheinen zur Geräte-/Cloudregistrierung und Geräteabfrage zu gehören. Ob der eigentliche Firmwaredownload über denselben Host oder über eine dynamisch gelieferte andere URL erfolgt, ist noch nicht abschließend geklärt.

---

## 9. Aliyun-MQTT-Topics

Im Binary wurden die OTA-Topics gefunden:

```text
/%s/%s/user/OTA_UPDATE
/%s/%s/user/OTA_GET
```

Außerdem existieren Debugstrings für:

```text
productKey
DeviceName / deviceName
deviceSecret
TOPIC_GET
TOPIC_OTA_GET
TOPIC_UPDATE
TOPIC_OTA_UPDATE
TOPIC_ERROR
```

Gerätespezifische Secrets werden nicht dokumentiert.

---

## 10. OTA-Kommandos

### DTU-OTA

Im Binary sind separate OTA-Nachrichten für die Firmware des DTU selbst vorhanden:

```json
{"cmd":"CMD_OTA","code":"0002","param":{"deviceCode":"%s","dtuHardwareCode":"%s","dtuSoftwareCode":"%s","dtuSoftwareVer":"%s"}}
```

```json
{"cmd":"CMD_OTA","code":"0022","param":{"deviceCode":"%s","isAllowDtuOTA":"%d"}}
```

```json
{"cmd":"CMD_OTA","code":"0042","param":{"deviceCode":"%s","progress":"%d"}}
```

```json
{"cmd":"CMD_OTA","code":"0052","param":{"deviceCode":"%s","progress":"100"}}
```

Fehlercodes für DTU-OTA:

```json
{"cmd":"CMD_OTA","code":"0082","param":{"deviceCode":"%s","upgradeFailed":"1"}}
```

```json
{"cmd":"CMD_OTA","code":"0092","param":{"deviceCode":"%s","FirmwareDownloadFailed":"1"}}
```

### Mainboard-/Device-OTA

Für die eigentliche Wärmepumpen-Mainboard-Firmware existiert ein eigener OTA-Pfad:

```json
{"cmd":"CMD_OTA","code":"0003","param":{"deviceCode":"%s","deviceSoftwareCode":"%s","deviceSoftwareVer":"%s","ssid":"%04X"}}
```

Weitere Nachrichten:

```json
{"cmd":"CMD_OTA","code":"0023","param":{"deviceCode":"%s","isAllowDtuOTA":"%d","ssid":"%04x"}}
```

```json
{"cmd":"CMD_OTA","code":"0043","param":{"deviceCode":"%s","progress":"%d","ssid":"%04x"}}
```

```json
{"cmd":"CMD_OTA","code":"0053","param":{"deviceCode":"%s","progress":"100","ssid":"%04x"}}
```

Fehler-/Statusmeldungen:

```json
{"cmd":"CMD_OTA","code":"0083","param":{"deviceCode":"%s","upgradeFailed":"1","ssid":"%04x"}}
```

```json
{"cmd":"CMD_OTA","code":"0093","param":{"deviceCode":"%s","FirmwareDownloadFailed":"1","ssid":"%04x"}}
```

```json
{"cmd":"CMD_OTA","code":"0113","param":{"deviceCode":"%s","Initialization":"%d"}}
```

Die genaue Semantik aller Codes ist noch nicht vollständig bewiesen. Die Aufteilung `...2` für DTU und `...3` für Mainboard/Device ist durch die zugehörigen Felder und Funktionen jedoch sehr deutlich.

---

## 11. OTA-Funktionen im Binary

`phnixIot4G` ist für das Reverse Engineering besonders geeignet, weil zahlreiche Funktions-/Symbolnamen erhalten geblieben sind.

Relevante Funktionen sind unter anderem:

```text
ota_device_send_version_to_phnix
ota_device_send_is_can_ota_to_phnix
ota_device_set_ota_file_download_info
ota_download_device_otaFile
ota_check_device_otaFile_md5
```

```text
down_board_ota_url_handle
down_board_cancel_ota_handle
board_ota_http_download
fota_board_thread_handle
```

```text
aliMqtt_topic_ota_get_msg_arrive
ali_mqtt_push_OTA_msg
```

```text
OTA_getDtuFwInfo
OTA_fwInfo
OTA_UpdateUrl
board_request_upgrade
TOPIC_OTA_UPDATE
TOPIC_OTA_GET
```

Weitere Mainboard-OTA-Funktionen:

```text
dtu_upload_board_info
board_dowmload_rep
board_upgrade_fail_rep
board_request_upgrade
board_ota_http_download
board_ota_rep
board_verbackroll_result_repo
```

UART-/OTA-bezogene Funktionen:

```text
uart485_get_device_info
uart485_get_productKey
set_ota_bin_info_by_485
sys_get_board_ota_ssid
sys_set_board_ota_ssid
```

Diese Symbolnamen stützen den Ablauf:

```text
Mainboard-/Versionsinformationen
        -> CMD_OTA / Code 0003
        -> MQTT OTA_GET / OTA_UPDATE
        -> Download-Metadaten
        -> HTTP-Download
        -> MD5-Prüfung
        -> Firmwaretransfer zum Mainboard über UART/RS485
```

---

## 12. Download-URL / OTA-Metadaten

Im Binary existieren die Felder/Strings:

```text
otaFileDownloadAddr
otaDtuInfo.otaFileDownloadAddr=%s
otaDeviceInfo.otaFileDownloadAddr=%s
downLoadPackage
```

Außerdem:

```text
otaDeviceInfo.fileMD5=%s
otaDeviceInfo.fileSize=%d
otaDeviceInfo.softwareCodeCloud=%s
```

Daraus folgt mit hoher Wahrscheinlichkeit, dass der Server mindestens folgende Informationen an `phnixIot4G` übermittelt:

- Downloadadresse / URL
- MD5
- Dateigröße
- Softwarecode
- Softwareversion
- ggf. SSID / Update-Session-ID

### Aktueller Erkenntnisstand zur URL

Ein statischer kompletter Mainboard-Firmware-Downloadlink wurde bisher **nicht** im Binary gefunden.

Die stärkste Hypothese ist deshalb:

> Die konkrete Download-URL wird dynamisch über die PHNIX-/Aliyun-Cloud als OTA-Metadatum an `phnixIot4G` geliefert und nur für den jeweiligen Updatevorgang verwendet.

Der zentrale Parser dafür ist sehr wahrscheinlich:

```text
aliMqtt_topic_ota_get_msg_arrive
```

und der anschließende Downloadpfad läuft über Funktionen wie:

```text
down_board_ota_url_handle
board_ota_http_download
ota_device_set_ota_file_download_info
```

Die exakte JSON-Struktur der eingehenden Serverantwort ist noch Gegenstand der Analyse.

---

## 13. Bereits gefundenes Mainboard-Firmwareimage

Im Cache des LTE-Modems lag bereits folgende Datei:

```text
/cache/phnixIot_device_OTA
```

Eigenschaften:

```text
Größe: 287598 Byte
MD5:   ceb6a4bf386ff644e23e410023e74673
```

Der Hash stimmt exakt mit dem in `/data/phnixIot_device_OTA_INFO` gespeicherten MD5 überein.

Damit ist eindeutig, dass die beiden Dateien zusammengehören.

### OTA-Info

`/data/phnixIot_device_OTA_INFO` ist 220 Byte groß.

Relevante Inhalte:

```text
V1.2
CEB6A4BF386FF644E23E410023E74673
82400644
0033
```

Hex-Auszug:

```text
00000000  4d b7 00 00 ...
00000010  ... 56 31 2e 32
...
000000a0  ... 43 45 42 36 41 34 42 46 33 38 36 ...
000000c0  ... 37 34 36 37 33 00 38 32 34 30 30 36 34 34 00 30
000000d0  30 33 33 00 ...
```

### SSID-Hypothese

Die ersten Bytes sind:

```text
4D B7
```

Als Little Endian ergibt das:

```text
0xB74D
```

Da die OTA-Funktionen ein `ssid`-Feld mit `%04X` bzw. `%04x` verwenden, ist `0xB74D` ein plausibler Kandidat für die gespeicherte OTA-SSID/Session-ID. Dies ist jedoch noch **nicht bewiesen**.

---

## 14. Welche Version ist die gefundene OTA-Firmware?

Die separate OTA-Info enthält zwar den String:

```text
V1.2
```

Das Firmwareimage `/cache/phnixIot_device_OTA` selbst enthält jedoch die Zeichenfolge:

```text
824006440033
```

Sehr plausible Interpretation:

```text
82400644 0033
|        |
|        +-- Version 3.3
+----------- Softwarecode
```

Das passt zum bekannten Mainboard-Softwarecode `82400644` und zur aktuellen Mainboard-Version V3.3.

Zusätzlich enthält das Firmwareimage in der Nähe eine zweite strukturierte Kennung:

```text
823003140000
```

Die genaue Bedeutung dieser zweiten Kennung ist noch offen.

### Bewertung

**Sehr wahrscheinlich:**

> `/cache/phnixIot_device_OTA` ist die Mainboard-Firmware **82400644 V3.3**.

Der String `V1.2` in `phnixIot_device_OTA_INFO` bezeichnet damit wahrscheinlich **nicht** die Version des gespeicherten Firmwareimages. Seine genaue Bedeutung muss noch aus der Struktur bzw. den Code-Referenzen rekonstruiert werden.

---

## 15. Technischer Aufbau des Mainboard-Firmwareimages

Das Firmwareimage beginnt mit:

```text
90 EB 00 20
D1 27 09 08
A3 AF 08 08
A5 AF 08 08
...
```

Little Endian interpretiert:

```text
Initial Stack Pointer: 0x2000EB90
Reset Handler:         0x080927D1
weitere Handler:       0x0808AFA3, 0x0808AFA5, ...
```

Das ist eine typische ARM-Cortex-M-Vektortabelle.

Damit handelt es sich nicht um ZIP, TAR oder einen PHNIX-Downloadcontainer, sondern sehr wahrscheinlich um ein bereits direkt flashbares MCU-Firmwareimage.

Die Adressen deuten auf einen Flashbereich ungefähr um:

```text
0x08080000
```

Der Code ist Thumb/ARM-Cortex-M-Code.

In der Firmware selbst wurden nur wenige brauchbare Klartextstrings gefunden, was für ein kompiliertes Embedded-MCU-Image normal ist.

---

## 16. Verhältnis zum PHNIX-Patent / dokumentierten OTA-Verfahren

Das von PHNIX beschriebene OTA-Verfahren passt sehr gut zu den praktischen Funden:

1. Wireless-/LTE-Terminal erhält Firmwareinformationen und Downloadadresse.
2. Terminal lädt das Firmwarepaket vollständig herunter.
3. Datei wird geprüft.
4. Firmware wird in kleinere Datenpakete zerlegt.
5. Pakete werden über die 485-Kommunikationsleitung an das Mainboard gesendet.
6. Mainboard quittiert korrekt/falsch/weiter/fertig.
7. Retry und Wiederaufnahme sind vorgesehen.

Die Dateien und Funktionen auf dem untersuchten LTE-Modem passen genau zu dieser Architektur:

```text
Cloud
 -> otaFileDownloadAddr
 -> /cache/phnixIot_device_OTA
 -> MD5
 -> phnixIot4G
 -> /dev/ttyHSL2
 -> RS485
 -> Mainboard
```

---

## 17. Noch offene Fragen

### Höchste Priorität

- Wie lautet die exakte aktuelle Firmware-Download-URL?
- Welche MQTT-/JSON-Nachricht liefert `otaFileDownloadAddr`?
- Wie kann ein manueller Firmware-Check reproduzierbar und möglichst risikolos ausgelöst werden?
- Ist der Downloadlink dauerhaft, zeitlich begrenzt oder signiert?
- Kann ein neueres Image als V3.3 abgefragt werden?

### Zweite Priorität: RS485-Flashprotokoll

Zu rekonstruieren sind:

- Start-/Bootloaderkommando
- Paketgröße
- Paketheader
- Sequenznummer
- CRC/Checksumme
- ACK/NACK
- Retry
- Resume
- Abschlusskommando
- eventuelle Flashadresse
- eventuelle Versions-/Produktprüfung

Dazu sind insbesondere die Symbolnamen und Call-Graph-Beziehungen in `phnixIot4G` weiter zu analysieren.

---

## 18. Empfohlene weitere Untersuchungen

### Offline

Priorität hat die Analyse von `/data/phnixIot4G`:

```text
aliMqtt_topic_ota_get_msg_arrive
board_request_upgrade
down_board_ota_url_handle
board_ota_http_download
ota_device_set_ota_file_download_info
ota_device_send_version_to_phnix
set_ota_bin_info_by_485
fota_board_thread_handle
```

Ziel ist ein vollständiger Call-Graph:

```text
Trigger
 -> OTA-Request
 -> MQTT-Response
 -> otaFileDownloadAddr
 -> HTTP-Download
 -> MD5-Prüfung
 -> RS485-Update
```

### Auf dem LTE-Modem

Weiterhin zunächst möglichst read-only arbeiten.

Besonders interessant sind:

- Dateisystemänderungen in `/cache` während eines echten OTA-Vorgangs
- MQTT-Verkehr auf `rmnet_data0`
- `/dev/ttyHSL2` während eines Firmwaretransfers
- persistente OTA-Strukturen in `/data`

Ein `tcpdump` ist im aktuellen Root-Dateisystem nicht vorhanden. Ein temporär nach `/cache` kopiertes statisches ARM-Binary wäre technisch möglich, sollte aber nur bewusst eingesetzt werden.

---

## 19. Sicherheits- und Dokumentationshinweise

- Keine zufällige SIM7600-Firmware flashen.
- Mainboard-OTA nicht aktiv starten, solange Protokoll und Recovery nicht verstanden sind.
- `phnixIot4G`, OTA-Info und Firmwareimage lokal sichern, bevor Veränderungen erfolgen.
- Eindeutige IMEI, DeviceSecrets, Tokens und Cloud-Credentials nicht öffentlich committen.
- Fundstellen und Hashes dokumentieren, damit Originaldateien später eindeutig verifiziert werden können.
- Zwischen **SIM7600-Modemfirmware**, **OpenLinux/DTU-Anwendung** und **Wärmepumpen-Mainboard-Firmware** strikt unterscheiden.

---

## 20. Aktueller Gesamtstand

### Bestätigt

- DTU-Trägerplatine: MXL290
- Mobilfunkmodul: SIMCom SIM7600E-H
- OpenLinux auf Qualcomm MDM9607
- ADB verfügbar und Root-Shell möglich
- PHNIX-Anwendung: `/data/phnixIot4G`
- Watchdog: `/data/helloworld`
- PHNIX-Anwendung nutzt `/dev/ttyHSL2`
- aktive PHNIX-MQTT-Verbindung über TCP/1883
- Linked-Go-/PHNIX-HTTP-Endpunkte im Binary
- getrennte DTU- und Mainboard-OTA-Codepfade
- Mainboard-OTA-Datei in `/cache/phnixIot_device_OTA`
- Firmwaregröße 287598 Byte
- MD5 `ceb6a4bf386ff644e23e410023e74673`
- OTA-Info enthält denselben MD5
- Firmware ist ein ARM-Cortex-M-Image
- Firmware enthält `824006440033`

### Sehr wahrscheinlich

- `824006440033` = Softwarecode `82400644`, Version V3.3
- `/dev/ttyHSL2` ist der UART Richtung Mainboard-/RS485-Pfad
- der konkrete Firmware-Downloadlink wird dynamisch über die Cloud geliefert
- `aliMqtt_topic_ota_get_msg_arrive` verarbeitet die entscheidenden OTA-Metadaten
- `0xB74D` in der OTA-Info könnte die OTA-SSID/Session-ID sein

### Noch offen

- exakter Downloadlink
- exakte eingehende OTA-JSON-Struktur
- reproduzierbarer manueller Firmware-Check
- genaue Bedeutung von `V1.2` in `phnixIot_device_OTA_INFO`
- genaue Bedeutung von `823003140000`
- vollständiges RS485-Firmware-Updateprotokoll
