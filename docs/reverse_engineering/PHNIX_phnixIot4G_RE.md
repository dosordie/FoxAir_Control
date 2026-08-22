# PHNIX/FoxAir LTE-Modem – statische OTA-Analyse

Stand: 2026-08-22  
Arbeitsweise: ausschließlich offline/read-only auf den drei bereitgestellten Artefakten. Es wurde weder auf das LTE-Modem geschrieben noch ein MQTT-/OTA-Befehl gesendet, ein Prozess beendet, ein Neustart ausgelöst oder Firmware geflasht. Gefundene Credential-Strukturen werden beschrieben, aber keine Werte dokumentiert.

## Kurzfazit

1. **Kein aktueller Firmware-Link ist statisch im Programm oder in `phnixIot_device_OTA_INFO` enthalten.** Das vorhandene Firmwareimage enthält ebenfalls keinen Download-Link.
2. **Die vollständige URL wird von der Cloud in einer MQTT-Nachricht geliefert.** `ota_device_set_ota_file_download_info()` liest `param.otaFileDownloadAddr`; `ota_download_device_otaFile()` übergibt diesen String unverändert als `CURLOPT_URL` an libcurl.
3. **Für Mainboard-Firmware ist die relevante eingehende Cloud-Antwort Code `0033`.** Sie kommt auf `/<productKey>/<deviceName>/user/OTA_GET` an.
4. **Die Anfrage geht auf `/<productKey>/<deviceName>/user/OTA_UPDATE` hinaus.** Der Versionsbericht ist Code `0003`. `board_request_upgrade()` sendet dagegen Code `0023`; der zunächst vermutete Call-Graph war an dieser Stelle nicht korrekt.
5. **Die Mainboard-Übertragung ist Modbus-RTU-ähnlich:** Slave `0x63`, Funktion `0x10`, Metadatenregister `0xC357`, Datenregister `0xC5A8`, Modbus-CRC16. Standardblockgröße: 168 Byte, vom Mainboard änderbar. Fortschritt/Resume beruhen auf einem persistenten Byte-Offset.
6. **Es gibt keine anwendungsseitige Signaturprüfung der Mainboard-Firmware.** Geprüft werden Dateigröße und MD5. Die MQTT-Verbindung ist geräteauthentifiziert, läuft aber über unverschlüsseltes TCP/1883. Im OTA-JSON selbst werden keine Signatur, kein Nonce und kein Token ausgewertet.

## 1. Artefakte und Integrität

| Datei | Größe | MD5 | SHA-256 |
|---|---:|---|---|
| `phnixIot4G` | 747440 | `CDCF34DA5F039CEB1084DA835425F3A1` | `7C573431F0A67620D473419644A83A4F4DC04B8A91BDE5923C74A63BA1EAEDB7` |
| `phnixIot_device_OTA_INFO` | 220 | `CD77BA83CE4D646174F814F2E660AE1A` | `2A8F2207089B2A99F390EDE4D1E7170E2F1FDA135E4C1DD59AD4383194B5C4A4` |
| `phnixIot_device_OTA` | 287598 | `CEB6A4BF386FF644E23E410023E74673` | `6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A` |

`phnixIot4G` ist ein ungestripptes 32-Bit-ARM-ELF (`EM_ARM`, little endian, `ET_EXEC`), Entry `0xA0C8`, Interpreter `/lib/ld-linux.so.3`. Build-ID: `af4dcae12639bedce833ee5efa5da009777b6319`; Compilerstring: GCC 4.9.2. Es enthält 2544 Symbole und partielle DWARF-Debugdaten. Relevante Bibliotheken sind unter anderem `libcurl.so.5`, `libjson-c.so.3`, `libmosquitto.so.1`, OpenSSL 1.0.0 sowie die Aliyun-IoT-SDK-Komponenten im Binary.

## 2. MQTT-Richtung und OTA-Dispatcher

### Topics

In `ali_mqtt_init()` bei `0x1F034`:

- Publish normal: `/<productKey>/<deviceName>/user/update`
- **Publish OTA:** `/<productKey>/<deviceName>/user/OTA_UPDATE` (Formatstring VA `0x853D8`)
- Subscribe normal: `/<productKey>/<deviceName>/user/get`
- **Subscribe OTA:** `/<productKey>/<deviceName>/user/OTA_GET` (Formatstring VA `0x8546C`)

Die OTA-Subscription wird bei `0x1F47C–0x1F494` mit QoS 1 und Callback `aliMqtt_topic_ota_get_msg_arrive` eingerichtet. `ali_mqtt_push_OTA_msg()` bei `0x1F9B0` publiziert auf `TOPIC_OTA_UPDATE`.

### Empfangspfad

```text
Aliyun MQTT /user/OTA_GET
  -> aliMqtt_topic_ota_get_msg_arrive()       0x1ED98
  -> Payload-Kopie nach MQTT_get_data         0x94AB4
  -> ota_code_handle()                        0x19958
  -> json_tokener_parse()
  -> top-level Feld "code" als Integer
  -> ota_hanldle[] Dispatch-Tabelle            0x91C20
  -> Code 33: down_board_ota_url_handle()      0x19688
  -> ota_device_set_ota_file_download_info()   0x18DB8
```

Die Dispatch-Tabelle ist vollständig statisch rekonstruierbar:

| Integercode | Übliche vierstellige Darstellung | Handler |
|---:|---|---|
| 12 | `0012` | `ota_dtu_set_ota_info` `0x1841C` |
| 32 | `0032` | `down_dtu_ota_url_handle` `0x19580` |
| **33** | **`0033`** | **`down_board_ota_url_handle` `0x19688`** |
| 62 | `0062` | Funktion bei `0x19704` |
| 63 | `0063` | `down_check_board_ver_handle` `0x19734` |
| 73 | `0073` | `down_board_cancel_ota_handle` `0x19764` |
| 58 | `0058` | `down_dtu_cancel_ota_handle` `0x19828` |
| 103 | `0103` | `down_board_ver_bcakroll_handle` `0x197F4` |
| 114 | `0114` | Funktion bei `0x1986C` |

`ota_code_handle()` liest nur `code`; `cmd` wird beim Dispatch nicht validiert. JSON-C konvertiert den Wert mit `json_object_get_int()`. Die ausgehenden Nachrichten verwenden einen Stringcode (`"0033"`-Stil); der Dispatcher vergleicht anschließend den numerischen Wert.

## 3. Exaktes eingehendes Mainboard-OTA-JSON

`ota_device_set_ota_file_download_info()` bei `0x18DB8` liest genau diese Felder aus dem Objekt `param`:

| Feld | Typ im Code | Verwendung |
|---|---|---|
| `softwareCode` | String | Ziel-Softwarecode, Kopie nach `otaDeviceInfo+0x00` |
| `softwareVer` | String | erwartet Format wie `V3.3`; Zeichen 1 und 3 werden zu `0033` umgebaut |
| `ssid` | String | vierstellige dezimale/BCD-artige Darstellung; Zeichen 2 und 3 werden zu einem Byte, z. B. `"0033" -> 0x33` |
| `fileMD5` | String | erwarteter MD5, 32 Zeichen |
| `fileSize` | Integer | erwartete Bytezahl |
| `otaFileDownloadAddr` | String | vollständige Download-URL |

Rekonstruiertes, semantisch vollständiges Beispiel:

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
    "otaFileDownloadAddr": "http://<cloud-gelieferter-host>/<cloud-gelieferter-pfad>"
  }
}
```

**Bewiesen:** Diese sechs `param`-Felder werden gelesen. `deviceCode`, `productCode`, Token oder Signatur sind für diesen Handler nicht erforderlich und werden dort nicht ausgewertet. `cmd` gehört zum verwendeten Protokoll, wird im zentralen Handler aber nicht geprüft. Die genaue Feldreihenfolge ist JSON-typisch irrelevant.

**Wahrscheinlich:** Die Cloud sendet `code` und `ssid` als Strings, weil alle ausgehenden PHNIX-Nachrichten so formatiert sind. Für `ssid` muss die Implementierung praktisch eine mindestens vier Zeichen lange Ziffernfolge liefern.

## 4. Woher die Download-URL kommt

### Beweis

In `ota_device_set_ota_file_download_info()`:

- `0x19010–0x1901C`: Lookup von `"otaFileDownloadAddr"` (String-VA `0x8379C`)
- `0x19024–0x19048`: `json_object_get_string()`, `strlen()`, direkte Kopie in `otaDeviceInfo+0x35` (`0x933E1`)

In `ota_download_device_otaFile()` bei `0x19E70`:

- `0x19E7C`: Ziel `/cache/phnixIot_device_OTA`
- `0x19EB4`: `curl_easy_init()`
- `0x19ED4–0x19EE4`: Option `0x2712` = `CURLOPT_URL`, Wert aus `0x933E1`
- `0x19EF0–0x19F20`: Write-Callback und Zieldatei
- `0x19FB4`: `curl_easy_perform()`

Damit ist **bewiesen**, dass die URL vollständig serverseitig geliefert wird. Es gibt keine Zusammensetzung aus Firmware-Basis-URL und Dateiname. Die statische Basis `http://cloud.linked-go.com:84` wird nur für Geräteidentität und Logging verwendet, nicht für den Firmwaredownload.

Das Programm setzt für den Boarddownload keine eigenen HTTP-Header, Cookies, Bearer-Tokens oder Basic-Auth-Daten. Eventuelle Authentisierung muss daher in der URL selbst stecken (zum Beispiel Query-Signatur) oder der Download ist anonym. libcurl wird nicht auf HTTP beschränkt; statisch findet sich jedoch kein FTP-Template und die Logtexte sprechen ausschließlich von HTTP/HTTPS.

### Statisch vorhandene HTTP-Endpunkte

- `http://cloud.linked-go.com:84/cloudservice/api/phnixiot/queryiotdevice.json?appKey=%s`
- `http://cloud.linked-go.com:84/cloudservice/api/communicationDevice/queryiotdevice.json?appKey=%s`
- `http://cloud.linked-go.com:84/cloudservice/api/communicationDevice/createDeviceBySign`
- `.../create_communicationDeviceLog.json`
- `.../dtuLog/report.json`

Diese Endpunkte liefern/registrieren Geräteidentität; im Binary existiert kein statischer Board-Firmware-API-Endpunkt.

## 5. Firmwaredownload und Prüfung

```text
ota_device_set_ota_file_download_info() 0x18DB8
  -> löscht per Programmcode ggf. alten Cache und leert OTA_INFO
  -> Zustandsmaschine dtu_upgrade_pro() 0x1D5C0
  -> board_ota_http_download()          0x1D520
     -> ota_download_device_otaFile()   0x19E70
     -> ota_check_device_otaFile_md5()  0x1A370
```

`board_ota_http_download()` ruft erst den Download, dann die MD5-Prüfung auf. Bei Downloadfehler wird Code `0093` gemeldet. Die Prüfroutine:

- allokiert exakt `fileSize+1`,
- liest exakt `fileSize` Bytes aus `/cache/phnixIot_device_OTA`,
- berechnet MD5,
- wandelt den erwarteten Hash in Großschreibung um,
- vergleicht beide Strings.

Es gibt keine RSA-/ECDSA-/HMAC-Prüfung der Mainboarddatei. Ein im Binary vorhandener TLS-/RSA-Code gehört den eingebetteten Bibliotheken und ist nicht an diesen OTA-Prüfpfad angebunden.

## 6. Normaler und manueller Firmware-Check

### Tatsächlicher Ablauf

```text
Gültiges Mainboard-Info-Telegramm über RS485, Register 0xC544
  -> CRC-Prüfung im UART-Empfangspfad
  -> unpack_mcu_modbus()                 0x1DDE8
  -> indirekter Dispatch über Tabelle    0x91C68
  -> board_softcode_ver_handle()         0x1C1BC
     -> Boarddaten in otaDeviceInfo schreiben
     -> ota_info+0x19 inkrementieren
     -> 596-Byte-Snapshot in FIFO 0x98AE4 einreihen
  -> fota_board_thread_handle()          0x1DD4C
  -> dtu_upgrade_pro()                   0x1D5C0
  -> dtu_upload_board_info()             0x1D408
  -> ota_device_send_version_to_phnix()  0x18A38
  -> ali_mqtt_push_OTA_msg()             0x1F9B0
  -> MQTT OTA_UPDATE, Code 0003
```

Es gibt genau einen direkten Aufrufer von `ota_device_send_version_to_phnix()`: `dtu_upload_board_info()` bei `0x1D410`. Dessen einziger direkter Aufrufer ist `dtu_upgrade_pro()` bei `0x1D658`; diese Funktion wird ausschließlich aus `fota_board_thread_handle()` bei `0x1DDE0` aufgerufen.

`fota_board_thread_handle()` schläft nur **einmal beim Start** eine Sekunde, liest anschließend die persistenten Parameter, setzt `board_ota_step=12` und ruft danach `dtu_upgrade_pro()` in einer kontinuierlichen Schleife auf. Die frühere Beschreibung als „1-s-Schleife“ war ungenau.

### Exakte Bedingungen für das Erzeugen von `0003`

Alle folgenden Bedingungen müssen erfüllt sein:

1. **Vollständige DTU-/Cloudinitialisierung:** `get_dtu_run_step()` muss exakt `11` liefern (`0x1D5C8–0x1D5D8`). Der Wert `11` wird in `aliMqtt_handle_thread()` erst bei `0x1FDE4–0x1FDE8` gesetzt, nachdem `ali_mqtt_init()` nicht mehr `-1` zurückgibt. Vorher durchläuft die Initialisierung unter anderem UART (`4/5`), Geräte-/Credential-Abfrage (`7`) und MQTT-Aufbau.
2. **Nicht gerade im HTTP-Downloadzustand:** `get_board_ota_step()` darf nicht `3` sein (`0x1D5DC–0x1D5E8`). Bei Schritt `3` wird der gesamte vorgelagerte Uploadzweig übersprungen; ein bereits gesetzter Boardinfo-Zähler bleibt dabei bestehen und wird später abgearbeitet.
3. **Kein vorrangiger allgemeiner Geräteinfo-Upload:** `ota_info+0x0D` muss `0` sein (`0x1D5EC–0x1D624`). Ist dieses Flag gesetzt, wird es gelöscht und zunächst `dtu_pub_devinfo()` ausgeführt. Der Boardinfo-Zähler wird in diesem Schleifendurchlauf nicht verbraucht.
4. **Mindestens ein ausstehendes Boardinfo-Ereignis:** Das Byte `ota_info+0x19` muss ungleich `0` sein (`0x1D624–0x1D638`). `board_softcode_ver_handle()` erhöht dieses Byte bei jeder gültig dispatchten Mainboardmeldung `0xC544` (`0x1C3E0–0x1C3FC`). `dtu_upgrade_pro()` dekrementiert es unmittelbar vor dem Aufruf von `dtu_upload_board_info()` (`0x1D638–0x1D658`).
5. **Passender Datensatz in der FIFO:** `board_softcode_ver_handle()` reiht bei `0x1C460–0x1C494` einen 596-Byte-Snapshot in die FIFO mit Kopfzeiger `0x98AE4` ein. `ota_device_send_version_to_phnix()` entfernt genau einen Datensatz mit `get_data_from_line()` und verwendet dessen Werte. Zähler und FIFO werden im normalen Pfad gemeinsam befüllt.
6. **SIM und MQTT beim eigentlichen Publish betriebsbereit:** `ali_mqtt_push_OTA_msg()` verlangt `UimAPI_get_card_status()==1` (`0x1F9CC–0x1F9E0`) und `IOT_MQTT_CheckStateNormal()>0` (`0x1F9E4–0x1FA2C`). Erst danach ruft es `IOT_MQTT_Publish()` auf dem Topic `TOPIC_OTA_UPDATE` auf. Ein negativer Publish-Rückgabewert wird als Fehler behandelt.

`board_softcode_ver_handle()` vergleicht zwar die gemeldeten Codes über `dev_otavercode_compare()` mit persistenten Resume-Daten. Das Ergebnis kann Resume-/OTA-Zustände vorbereiten, **sperrt den Versionsbericht aber nicht**: Beide Vergleichspfade vereinigen sich vor dem Aufbau der aktuellen Softwareversion, dem Inkrementieren von `ota_info+0x19` und dem Einreihen des FIFO-Datensatzes.

Der ausgehende Versionsbericht besitzt exakt dieses Format:

```json
{
  "cmd": "CMD_OTA",
  "code": "0003",
  "param": {
    "deviceCode": "<redigiert>",
    "deviceSoftwareCode": "<RS485-Datensatz+0x235>",
    "deviceSoftwareVer": "<RS485-Datensatz+0x23E>",
    "ssid": "<RS485-Datensatz+0x252 als %04X>"
  }
}
```

`deviceCode` kommt nicht aus dem RS485-Datensatz, sondern aus `aliMqtt_get_deviceName()`. Die drei übrigen Werte werden unverändert beziehungsweise bei SSID als vierstelliger Hexwert aus dem entnommenen 596-Byte-Datensatz formatiert. Für die live beobachtete Mainboardmeldung sind dies `82400644`, `V3.3` und das SSID-Byte `0x63`, also der String `"0063"`. Die frühere Beispielangabe `deviceSoftwareVer="0033"`/`ssid="0033"` war daher keine exakte Wiedergabe dieses Live-Datensatzes.

### Wichtige Korrektur zu `board_request_upgrade()`

`board_request_upgrade()` bei `0x1D4E4` ruft `ota_device_send_is_can_ota_to_phnix()` bei `0x18D04` auf. Diese Funktion sendet **Code `0023`**, nicht `0003`:

```json
{
  "cmd": "CMD_OTA",
  "code": "0023",
  "param": {
    "deviceCode": "<redigiert>",
    "isAllowDtuOTA": "1",
    "ssid": "0033"
  }
}
```

`0003` ist der Versions-/Checkbericht; `0023` ist die Freigabe-/Statusmeldung. **`0023` ist keine Voraussetzung für `0003`.** Im Gegenteil:

- Im frühen Teil von `dtu_upgrade_pro()` wird `0023` nur in einem nachgeordneten Geschwisterzweig gesendet, wenn kein Boardinfo-Zähler abgearbeitet wird und sich der lokale Freigabestatus von `otaDeviceInfo+0x253` unterscheidet (`0x1D66C–0x1D6C4`). Ein ausstehendes Boardinfo-Ereignis nimmt vorher den `0003`-Zweig.
- `board_request_upgrade()` wird erst bei `board_ota_step==1` aufgerufen (`0x1D750–0x1D760`) und sendet dann `0023`. Dieser Zustand gehört zum Ablauf **nach** einer angenommenen `0033`-OTA-Antwort beziehungsweise zur anschließenden Board-Freigabephase.
- Kein eingehender MQTT-/Cloudcode ruft `ota_device_send_version_to_phnix()` auf. Insbesondere sind weder `0033` noch ein anderes Cloudkommando Trigger oder Vorbedingung für `0003`.

### Triggerbewertung

- **Bewiesen:** Der Check wird durch ein gültiges RS485-Mainboard-Informationsereignis `0xC544` ausgelöst und anschließend von der kontinuierlich laufenden Zustandsmaschine abgearbeitet.
- **Bewiesen:** Es gibt keinen zyklischen HTTP-Firmwarepoller und keinen statischen Firmware-API-Call.
- **Sehr wahrscheinlich:** Das Mainboard liefert seine Info periodisch oder nach einer Abfrage; das Modem meldet sie dann an die Cloud. `uart485_get_device_info()` selbst ist in diesem Build nur ein Stub.
- **Live bestätigt:** Ein syntaktisch gültiger manueller `0003`-Publish ist möglich; bei den kontrollierten Tests wurde jedoch keine `OTA_GET`-/`0033`-Antwort beobachtet.

## 7. Geräteidentität und Credentials

### RAM-Strukturen

| Variable | VA | Größe | Inhalt |
|---|---:|---:|---|
| `productKey` | `0x94EB8` | 33 | Aliyun ProductKey |
| `deviceName` | `0x94EDC` | 33 | aus Cloudfeld `device_code` |
| `deviceSecret` | `0x94F00` | 65 | aus Cloudfeld `device_secret` |
| `deviceID` | `0x94F44` | 13 | Gerätekennung |
| Board-ProductKey-Puffer | via `aliMqtt_get_product_buf()` | 33 | über UART/RS485 gelesen |

`httpAPI_queryiotdevice_callback()` (`0x15C58`) und `httpAPI_communicationDevice_queryiotdevice_callback()` (`0x16960`) lesen aus einer erfolgreichen Cloudantwort:

```json
{
  "error_code": 0,
  "object_result": {
    "device_code": "<redigiert>",
    "product_key": "<redigiert>",
    "device_secret": "<redigiert>"
  }
}
```

Eine ältere API-Variante erwartet `object_result` als Array und nimmt Index 0. Die Werte werden über `aliMqtt_set_deviceName()`, `aliMqtt_set_productKey()` und `aliMqtt_set_deviceSecret()` in die genannten BSS-Puffer kopiert und danach an das Aliyun-SDK übergeben.

Der Board-ProductKey und eine Gerätekennung werden über `/dev/ttyHSL2` ermittelt. Die Gerätekennung wird in `/data/phnixIot_device_statisic` innerhalb des 128-Byte-Blocks `statistic_para` gespeichert (unter anderem Bereich um Offset `0x6C`). Die untersuchten drei Dateien enthalten keine live befüllten MQTT-Secrets; diese BSS-Felder sind im ELF naturgemäß leer.

## 8. RS485-/UART-Protokoll

### Transport

`uart485_init()` bei `0x14188` öffnet `/dev/ttyHSL2` mit `O_RDWR|O_NOCTTY` und ruft `set_opt(fd, 9600, 8, 'N', 1)` auf: **9600 Baud, 8N1**.

`getDevParameter()` bei `0x14D58` liest die Daten, prüft `Check_crc()` und ruft `unpack_mcu_modbus()` bei `0x1DDE8` auf. Dieser akzeptiert für den OTA-Pfad Slave `0x63`, Funktion `0x10` und dispatcht anhand der Registeradresse.

### Register-/Handler-Tabelle

| Register | Richtung/Bedeutung | Handler |
|---:|---|---|
| `0xC350` | Serverversion/Bestätigung | `board_set_ser_ver_handle` |
| `0xC357` | OTA-Metadaten/Bestätigung | `board_set_bin_info_handle` |
| `0xC36C` | Abbruchbestätigung | `board_recv_cancel_upgrade_handle` |
| `0xC36E` | OTA-Freigabe/Status | `board_is_allow_upg_handle` |
| `0xC371` | Block-ACK/Fortschritt | `board_updata_bin_handle` |
| `0xC378` | Rollback/Initialisierung | `board_reply_verbackroll_handle` |
| `0xC5A8` | Firmwareblock/Bestätigung | `board_set_updata_bin_handle` |
| `0xC544` | Mainboard-HW/SW-Info | `board_softcode_ver_handle` |

Die Tabelle enthält intern `0x1Cxxx`; auf dem Draht werden die unteren 16 Bit (`0xCxxx`) verwendet.

### CRC

`crc16()` bei `0x137C8` verwendet die klassischen Modbus-CRC-Tabellen (Init `0xFFFF`, Polynom `0xA001`). Die beiden CRC-Bytes werden in Modbus-Drahtreihenfolge angehängt. Testvektor `123456789` ergibt auf dem Draht `37 4B` (numerischer Standardwert `0x4B37`).

### Metadatenpaket – Start/Initialisierung

Erzeugt von `set_ota_bin_info()` bei `0x1CEA0`:

| Offset | Länge | Inhalt |
|---:|---:|---|
| 0 | 1 | Slave `0x63` |
| 1 | 1 | Funktion `0x10` |
| 2 | 2 | Register `0xC357`, big endian |
| 4 | 2 | Registerzahl `0x0013` (19) |
| 6 | 1 | Datenlänge `0x26` (38) |
| 7 | 2 | SSID, big endian |
| 9 | 4 | Firmwaregröße, big endian |
| 13 | 32 | MD5 als kleingeschriebener ASCII-Hexstring |
| 45 | 2 | Modbus-CRC16 |

Gesamtlänge: **47 Byte**. Dieses Paket ist der praktische Start der Mainboard-OTA-Initialisierung. Ein gesondertes Flash-Adressfeld existiert nicht.

### Firmwareblock

Erzeugt von `set_board_update_bin()` bei `0x1C7CC`:

| Offset | Länge | Inhalt |
|---:|---:|---|
| 0 | 1 | `0x63` |
| 1 | 1 | `0x10` |
| 2 | 2 | Register `0xC5A8` |
| 4 | 2 | `(payload_len + 6 + 1) / 2`, Registerzahl |
| 6 | 1 | `payload_len`, bei >255 auf `0xFF` begrenzt |
| 7 | 2 | SSID |
| 9 | 2 | Gesamtzahl Firmwarepakete, aufgerundet |
| 11 | 2 | 1-basierte Paketnummer: `offset / payload_len + 1` |
| 13 | N | Firmwaredaten |
| 13+N | 2 | CRC16 |

Standardmäßig setzt `main()` bei `0xB464` `payload_len = 0xA8 = 168`. Das Mainboard kann in einer sechs Byte langen Freigabeantwort einen positiven alternativen Wert in den Datenbytes 4/5 angeben (`board_is_allow_upg_handle`, `0x1BB3C–0x1BBA8`).

Hinweis: Byte 6 verhält sich in diesem proprietären Profil nicht wie der gewöhnliche Modbus-Bytecount des gesamten Datenfeldes; es enthält nur die Firmware-Nutzlastlänge. Die Registerzahl berücksichtigt dagegen die sechs Headerbytes SSID/Gesamtzahl/Paketnummer.

### Block-ACK, Retry und Abschluss

`board_updata_bin_handle()` bei `0x1B72C` verarbeitet die Antwort auf Register `0xC371`. Nach den ersten zwei SSID-Bytes liest es drei 16-Bit-Werte:

1. Erfolgsmarker, erwartet `1`
2. ACK-Art: `1` = Block angenommen, `2` = Transfer vollständig
3. bestätigte Paketnummer

Bei ACK-Art 1 muss die Paketnummer `offset/payload_len + 1` entsprechen. Dann wird der persistente Offset um `payload_len` erhöht. Bei ACK-Art 2 wird der Offset auf die Dateilänge gesetzt.

Retry-Verhalten:

- pro Block anfänglich drei Sendeversuche (`app+0x4C = 3`),
- erneutes Senden nach Ablauf eines 5-Tick-Timers (`app+0x48 = 5`),
- ein gültiges ACK setzt Timer zurück und stellt drei Versuche für den nächsten Block bereit,
- Status 4 bedeutet Push-Fehler; Status 6 bedeutet Mainboard-Upgradefehler,
- der komplette Push-/Upgradevorgang wird höchstens zweimal erneut versucht; danach wird abgebrochen und Code `0083` gemeldet,
- Status 5 bedeutet Upgradeerfolg und führt zu Code `0053` (100 %).

Es gibt kein vom Modem übertragenes separates Flashadressfeld. Das Image ist für seinen Zielbereich gelinkt; anhand der Vektoren ist `0x08080000` sehr wahrscheinlich die Basis, aber die tatsächliche Bootloader-Flashlogik liegt auf dem Mainboard und ist im LTE-Binary nicht enthalten.

### Resume

`/data/phnixIot_device_OTA_INFO` ist die 220-Byte-Struktur `sys_para`:

| Dateioffset | Inhalt im vorhandenen Beispiel |
|---:|---|
| `0x00` | 32-Bit gespeicherte Prüfsumme; CRC über die folgenden 216 Byte |
| `0x1C` | `V1.2` (DTU-/Strukturversion) |
| `0xA5` | MD5, 32 Zeichen plus NUL |
| `0xC6` | Softwarecode, 8 Zeichen plus NUL |
| `0xCF` | Versionscode, 4 Zeichen plus NUL |
| `0xD4` | bestätigter Firmware-Byteoffset, 32 Bit little endian |
| `0xD8` | Firmwaredateilänge, 32 Bit little endian |

SSID wird separat in `/data/phnixIot_device_statisic` bei Struktur-Offset `0x7C` gespeichert. Nach jedem bestätigten Block schreibt `sys_set_board_file_offset()` die aktualisierte OTA_INFO-Struktur. `board_softcode_ver_handle()` vergleicht gemeldete Boardcodes mit den gespeicherten Werten und kann damit nach Stromausfall in den Resume-Pfad wechseln.

## 9. Vorhandenes Firmwareimage

- Größe: 287598 Byte
- MD5: `CEB6A4BF386FF644E23E410023E74673`
- SHA-256: `6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A`
- Initial Stack Pointer: `0x2000EB90`
- Reset Handler: `0x080927D1`
- String `824006440033` exakt bei Dateioffset `0x42780` (272256)
- Softwarecode: `82400644`
- Versionscode: `0033`, entsprechend sehr wahrscheinlich Clouddarstellung `V3.3`
- wahrscheinliche Imagebasis: `0x08080000`

## 10. Aktueller Link: Ergebnis und passiver Nachweis

Es wurde **kein aktueller oder alternativer Link** in den untersuchten Artefakten gefunden. Insbesondere:

- kein URL-String in `phnixIot_device_OTA_INFO`,
- kein URL-String im Firmwareimage,
- keine Firmware-Basis-URL oder Dateinamenschablone in `phnixIot4G`,
- die statischen Cloud-APIs betreffen Geräteidentität/Logging, nicht Firmwareabfrage,
- öffentlich indexierte Suchen nach `otaFileDownloadAddr`, `CMD_OTA 0033` und den offiziellen Domains lieferten keine Treffer.

Die fehlende Information ist die **eingehende MQTT-Nutzlast Code `0033` für genau dieses Gerät/Softwareprofil**. Der sicherste read-only Nachweis ist ein passiver Mitschnitt außerhalb des Modems, beispielsweise Port-Mirroring/Router-Capture mit Filter:

```text
tcp port 1883 and host 8.209.64.105
```

Danach in Wireshark nach Topic-Suffix `/user/OTA_GET` oder Payloadstring `otaFileDownloadAddr` filtern. Weil MQTT unverschlüsselt ist, sind Topic und JSON sichtbar. Der Mitschnitt sollte lokal bleiben; ProductKey, DeviceName, DeviceSecret, IMEI und vollständige signierte URLs sind als vertraulich zu behandeln.

Alternativ wäre ein bewusst gesendeter `0003`-Versionsbericht reproduzierbar, aber das ist ein aktiver Cloud-/OTA-Vorgang und wurde nicht ausgeführt. Für eine spätere, ausdrücklich freigegebene Prüfung wären nötig:

1. live `productKey` und `deviceName` (nicht veröffentlichen),
2. die aktuelle Mainboardmeldung mit Softwarecode, Version und SSID,
3. die bestehende authentisierte MQTT-Sitzung oder das lokale DeviceSecret,
4. Publish des exakt rekonstruierten `0003` auf `OTA_UPDATE`,
5. ausschließlich Empfang/Archivierung der Antwort auf `OTA_GET`; noch kein Download/Flash.

Erst wenn die reale `otaFileDownloadAddr` vorliegt, kann gefahrlos mit einem reinen HTTP-HEAD bzw. einem Download auf einen Analyse-PC geprüft werden, ob sie ohne zusätzliche Authentisierung funktioniert. Ohne reale URL wäre jede Anfrage an vermutete Pfade spekulativ und nicht reproduzierbar.

## 11. Beweisgrade und offene Punkte

### Bewiesen

- vollständige URL aus `param.otaFileDownloadAddr`, direkt an libcurl;
- Topic-Richtung OTA_UPDATE/OTA_GET;
- JSON-Feldnamen und Codes `0003`, `0023`, `0033`, `0043`, `0053`, `0083`, `0093`, `0113`;
- MD5-/Größenprüfung, keine Firmware-Signaturprüfung im Mainboardpfad;
- 9600 8N1, Slave `0x63`, Funktion `0x10`, Register und Paketlayouts;
- Standardblockgröße 168 Byte, ACK/Retry und persistenter Offset;
- `board_request_upgrade()` sendet `0023`, nicht `0003`.

### Sehr wahrscheinlich

- Clouddarstellung der Version `V3.3` und SSID `"0033"`;
- Mainboard-Bootloader flasht das Image ab `0x08080000`;
- Download ist anonym oder über URL-Queryparameter autorisiert, da der Client keine separaten Authheader setzt.

### Offen ohne Live-Nachricht oder Mainboard-Bootloader

- reale aktuelle Download-URL und deren Ablaufzeit/Authentisierungsart;
- genaue Semantik jedes Statuswertes jenseits der im LTE-Code sichtbaren Reaktion;
- interne Erase/Program/Verify-Schritte und physische Flashadresse im Mainboard-Bootloader;
- ob die Cloud bei identischem Softwarecode derzeit überhaupt eine neuere Firmware anbietet.
