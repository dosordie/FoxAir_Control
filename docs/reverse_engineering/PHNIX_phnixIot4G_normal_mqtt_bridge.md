# PHNIX `phnixIot4G` – normaler MQTT↔RS485-Pfad

Stand: 2026-08-22

Diese Datei ergänzt `PHNIX_phnixIot4G_RE.md` um den **normalen** Datenpfad außerhalb des OTA-Protokolls. Grundlage ist ausschließlich statische Analyse des bereitgestellten, ungestrippten ARM-ELF `phnixIot4G`.

## Kurzfazit

Der normale Cloudkanal ist wesentlich einfacher als der OTA-Kanal:

```text
Mainboard /dev/ttyHSL2
  -> getDevParameter()
  -> CRC/Modbus-Prüfung
  -> unpack_mcu_modbus()
  -> ali_mqtt_push_msg(raw_frame, len)
  -> /<productKey>/<deviceName>/user/update

/<productKey>/<deviceName>/user/get
  -> aliMqtt_topic_get_msg_arrive()
  -> MQTT-Payload unverändert
  -> uart485_send_data_to_board(raw_payload, payload_len)
  -> uart485WriteBuf + send flag
  -> UART-Worker schreibt zum Mainboard
```

**Wichtig:** Der normale `/user/get`-Callback interpretiert kein JSON. Die Nutzlast wird binär und unverändert Richtung Mainboard weitergereicht. Ebenso publiziert `ali_mqtt_push_msg()` den übergebenen RS485-Puffer direkt als MQTT-Payload. Damit implementiert `phnixIot4G` im normalen Kanal im Kern eine binäre MQTT↔RS485-Bridge.

Die vollständige Zerlegung von `unpack_mcu_modbus()` zeigt außerdem: **Es gibt dort keine zweite normale Registertabelle.** Die einzige Dispatch-Tabelle umfasst genau acht OTA-/Boardservice-Register. Alle übrigen gültigen Frames fallen grundsätzlich durch den Dispatcher zurück in den transparenten MQTT-Pfad, abgesehen von wenigen Sonderfällen in `getDevParameter()` selbst.

---

## 1. MQTT-Topics und Subscription

`ali_mqtt_init()` (`0x1F034`) erzeugt:

- normaler Publish: `/<productKey>/<deviceName>/user/update`
- normaler Subscribe: `/<productKey>/<deviceName>/user/get`
- OTA Publish: `/<productKey>/<deviceName>/user/OTA_UPDATE`
- OTA Subscribe: `/<productKey>/<deviceName>/user/OTA_GET`

Der normale `/user/get`-Topic wird mit QoS 1 und Callback `aliMqtt_topic_get_msg_arrive()` (`0x1EED0`) registriert.

---

## 2. Cloud -> Mainboard: `aliMqtt_topic_get_msg_arrive()`

Funktion: `0x1EED0`.

Der Callback greift auf das vom Aliyun-SDK gelieferte Messageobjekt zu und verwendet dessen Payload-Zeiger und Payload-Länge. Nach Debugausgaben wird die komplette Payload unverändert an

```text
uart485_send_data_to_board(payload, payload_len)
```

übergeben. Anschließend werden Statistikzähler erhöht.

Es gibt in diesem Callback:

- kein `json_tokener_parse()`,
- keinen Base64-Decoder,
- keinen Modbus-Neuaufbau,
- keine CRC-Neuberechnung,
- keine Register-Whitelist.

### Korrektur zur früheren Interpretation von `status`

Bei `0x1EF74` ruft der Callback zwar

```c
memcmp(payload, "status", 6)
```

auf, **wertet den Rückgabewert aber nicht aus**. Direkt danach wird das Byte `0x988FC+0x14` auf 0 gesetzt. Das Zurücksetzen ist daher **nicht von einem `status`-Präfix abhängig**, sondern passiert bei jedem normalen `/user/get`-Callback. Der `memcmp()`-Aufruf ist in diesem Build funktional wirkungslos (wahrscheinlich liegengebliebener/fehlerhafter Code).

### Konsequenz

Für den normalen Cloudkanal liefert der Server bereits ein vollständig sendefertiges Binärtelegramm. `phnixIot4G` fungiert als Transportbrücke.

---

## 3. `uart485_send_data_to_board()` ist eine Queue, kein direkter `write()`

Funktion: `0x1562C`.

Sinngemäß:

```c
if (len <= 2048) {
    memcpy(uart485WriteBuf, payload, len);
    uart485SendLen = len;
    send_flag = 1;
}
```

Relevante globale Bereiche:

- `uart485WriteBuf` = `0x928DC`, 2048 Byte
- `uart485SendLen` = `0x930E0`
- Sendeflag = Byte bei `0x930DC`

Pakete über 2048 Byte werden ignoriert und geloggt.

---

## 4. Mainboard -> Cloud: `getDevParameter()`

Funktion: `0x14D58`.

`getDevParameter()` ist die zentrale Empfangsschleife des Mainboardkanals. Sie liest von `/dev/ttyHSL2`, sammelt die Daten in `uart485ReadBuf` (`0x920DC`) und prüft anschließend das Telegramm.

### Zulässige Modbus-Funktionscodes

Nach erfolgreicher CRC-Prüfung werden für die weitere Verarbeitung akzeptiert:

- `0x10`
- `0x03`
- `0x83`

Andere Funktionscodes werden verworfen und als falscher Modbus-Befehl geloggt.

Danach folgt:

```text
unpack_mcu_modbus(uart485ReadBuf, recv_len)
```

Wenn dieser Dispatcher `0` zurückgibt, ist der Frame lokal konsumiert und wird nicht über den normalen `/user/update`-Pfad publiziert. Bei Rückgabe `-1` läuft er weiter in die transparente Bridge.

---

## 5. `unpack_mcu_modbus()` vollständig zerlegt

Funktion: `0x1DDE8`.

### 5.1 Frameerkennung

Der Dispatcher sucht im übergebenen Puffer nach:

```text
byte +0 = 0x63
byte +1 = 0x10
byte +2/+3 = Registeradresse, big endian
byte +4/+5 = Registeranzahl, big endian
byte +7... = Nutzdaten
```

Nur Slave `0x63` + Funktion `0x10` werden intern dispatcht. Andere Frames bleiben unbehandelt (`-1`) und können damit normal zur Cloud gehen.

### 5.2 Zwei explizite lokale Bypass-Adressen

Noch vor der Tabelle prüft `unpack_mcu_modbus()` die Adresse auf:

- `0xC37B`
- `0xC5A8`

Für beide wird sofort `0` zurückgegeben. Damit werden diese Frames lokal konsumiert und **nicht** über `/user/update` weitergeleitet.

`0xC5A8` gehört zum OTA-Datenblockpfad. `0xC37B` ist ein weiterer lokaler Board-/OTA-Servicepfad; die genaue Gegenfunktion liegt außerhalb dieser Dispatch-Tabelle.

### 5.3 Die komplette Dispatch-Tabelle

Tabelle ab VA `0x91C68`, acht Einträge à 8 Byte:

| Index | Register | Handler | Adresse |
|---:|---:|---|---:|
| 0 | `0xC350` | `board_set_ser_ver_handle` | `0x1B480` |
| 1 | `0xC357` | `board_set_bin_info_handle` | `0x1B4B4` |
| 2 | `0xC36C` | `board_recv_cancel_upgrade_handle` | `0x1B51C` |
| 3 | `0xC36E` | `board_is_allow_upg_handle` | `0x1BA04` |
| 4 | `0xC371` | `board_updata_bin_handle` | `0x1B72C` |
| 5 | `0xC378` | `board_reply_verbackroll_handle` | `0x1B600` |
| 6 | `0xC5A8` | `board_set_updata_bin_handle` | `0x1B4E8` |
| 7 | `0xC544` | `board_softcode_ver_handle` | `0x1C1BC` |

Bei Treffer ruft der Dispatcher den Handler als

```c
handler(frame + 7, register_count * 2);
```

auf und setzt den Rückgabewert des Dispatchers auf `0`.

### 5.4 Entscheidender Befund für normale Register

**Es existieren in `unpack_mcu_modbus()` keine weiteren Registereinträge.**

Das bedeutet:

- `0xC350/C357/C36C/C36E/C371/C378/C5A8/C544` sind die acht intern interpretierten Register;
- `0xC37B` und `0xC5A8` besitzen zusätzlich den frühen lokalen Bypass;
- normale PHNIX-/Warmlink-Register werden hier **nicht semantisch decodiert**;
- sie bleiben Binärframes und werden über `ali_mqtt_push_msg()` zur Cloud übertragen.

Für Work ist damit die Suche nach einer großen versteckten „normalen Registertabelle“ in `phnixIot4G` beendet: **diese Tabelle gibt es in dieser Funktion nicht.** Die eigentliche Semantik normaler Mainboardregister liegt im Mainboard bzw. in Cloud/App, nicht im LTE-DTU.

---

## 6. Sonderfälle in `getDevParameter()` außerhalb von `unpack_mcu_modbus()`

### 6.1 Fünf-Byte-Exception-Frame

Wenn die empfangene Länge exakt 5 Byte beträgt und der Frame exakt

```text
63 83 01 21 2E
```

ist, wird er direkt über `ali_mqtt_push_msg()` publiziert und nicht weiter verarbeitet.

### 6.2 Acht-Byte-Paket

Ein gültiges 8-Byte-Telegramm wird nach den lokalen Sonderchecks direkt über `ali_mqtt_push_msg()` publiziert.

### 6.3 Register 500 / `0x01F4`: lokaler DTU-Info-Request

Für einen 8-Byte-Read-Request mit:

```text
slave = 0x60 oder 0x63
FC    = 0x03
addr  = 0x01F4 (500)
```

wird `response_DTU_info_request()` (`0x14A84`) aufgerufen. Die Registeranzahl aus Bytes 4/5 wird auf ein Byte reduziert und als Argument übergeben.

Dieser Request geht **nicht** zur Cloud.

`response_DTU_info_request()` baut lokal eine Antwort:

```text
byte 0 = 0x63
byte 1 = 0x03
byte 2 = register_count * 2
byte 3.. = Daten aus Get_ErrorStatue()
CRC     = Modbus CRC16
```

Die ersten vier Datenbytes bestehen aus dem 32-Bit-Rückgabewert von `Get_ErrorStatue()` in der auffälligen Reihenfolge:

```text
status[15:8], status[7:0], status[31:24], status[23:16]
```

Der lokale Antwortpuffer ist 16 Byte groß und die Funktion schreibt in diesem Build fest 16 Byte auf den UART. Bei kleineren angeforderten Datenmengen bleiben nicht belegte Bytes nullinitialisiert.

### 6.4 Register `0x00C8` / 200: ProductKey vom Mainboard

Nach dem Dispatcher liest `getDevParameter()` die Registeradresse aus Bytes 2/3. Wenn sie **200 (`0x00C8`)** ist, wird ein lokaler Provisionierungszweig betreten:

```text
if aliMqtt_get_product_buf()[0] == 0:
    memcpy(product_buf, uart485ReadBuf + 7, 32)
else:
    nur loggen
```

Der ProductKey wird also direkt aus den 32 Nutzdatenbytes ab Offset 7 übernommen. Dieser Frame wird anschließend nicht normal zur Cloud weitergereicht.

Das erklärt den Startup-Pfad `uart485_get_productKey()`: Das DTU fragt den ProductKey beim Mainboard ab und speichert ihn im gemeinsamen MQTT-Puffer.

### 6.5 Feste lokale Read-Requests im Binary

Direkt in `.rodata` liegen mehrere vollständige 8-Byte-Modbus-Requests:

```text
63 03 00 06 00 01 6C 49
63 03 00 04 00 01 CD 89
63 03 07 D1 00 5A 9C FE
```

sowie der bereits bekannte Exceptionframe:

```text
63 83 01 21 2E
```

Die ersten drei Frames zeigen, dass das DTU selbst gezielt Mainboardregister liest. Die genaue Zuordnung der drei Requests zu ProductKey/Device-ID/weiteren Startupinformationen wird separat über die jeweiligen Aufrufer weiterverfolgt.

---

## 7. Normaler Publish: `ali_mqtt_push_msg()`

Funktion: `0x1F6FC`.

Vorbedingungen:

1. `UimAPI_get_card_status() == 1`
2. `IOT_MQTT_CheckStateNormal(mqtt_client) > 0`

Die Funktion füllt die Aliyun-Message-Struktur bei `0x98AC4` mit:

- QoS = 1
- Retain = 0
- Duplicate = 0
- Payload-Zeiger = Originalpuffer
- Payload-Länge = Originallänge

und ruft dann

```text
IOT_MQTT_Publish(mqtt_client, TOPIC_UPDATE, &message)
```

auf.

Es gibt **keine Nutzdatentransformation** zwischen UART und MQTT.

Bei negativem Publish-Rückgabewert wird der MQTT-Client sogar über `IOT_MQTT_Destroy()` verworfen; bei Erfolg werden mehrere Kommunikations-/Statistikzähler erhöht.

---

## 8. FC `0x10`: lokales ACK nach dem Cloud-Publish

Nach dem normalen `ali_mqtt_push_msg()` prüft `getDevParameter()` zusätzlich auf

```text
uart485ReadBuf[0] == 0x63
uart485ReadBuf[1] == 0x10
```

Dann werden die ersten sechs Bytes kopiert, CRC16 ergänzt und ein acht Byte langes FC10-ACK lokal zurückgequeued:

```text
[slave][0x10][register_hi][register_lo][count_hi][count_lo][CRC]
```

Damit ist für einen normalen, nicht lokal abgefangenen FC10-Frame die Reihenfolge:

```text
Mainboard -> DTU: FC10 Datenframe
DTU -> Cloud: identischer Binärframe auf /user/update
DTU -> Mainboard: lokales FC10-ACK
```

Das ACK hängt nicht von einer Cloudantwort ab.

---

## 9. UART-Worker-Startup

`uart485_thread_handle()` (`0x14918`) führt vor dem normalen Bridgebetrieb aus:

```text
uart485_init()
set_Error_Flag(8)
loop:
    uart485_get_productKey()
    sleep(2)
    bis aliMqtt_get_productKey()[0] != 0
Clear_Error_Flag(8)
Device-ID prüfen/ggf. persistent übernehmen
init_line(...)
loop forever:
    getDevParameter()
```

Der Mainboard-UART ist damit nicht nur Datenbridge, sondern auch Quelle für Provisionierungsdaten.

---

## 10. Zwei getrennte Cloudprotokolle

### Normaler Kanal

```text
/user/update : rohe RS485-/Modbus-Bytes nach oben
/user/get    : rohe Binärbytes nach unten
```

### OTA-Kanal

```text
/user/OTA_UPDATE : PHNIX JSON mit CMD_OTA / Codes wie 0003, 0023 ...
/user/OTA_GET    : PHNIX JSON mit Codes wie 0033, 0073 ...
```

OTA ist ein eigener semantischer Stack und nicht bloß ein Teil der transparenten Bridge.

---

## 11. Ergebnis für Work

Für die weitere Registeranalyse ist jetzt statisch geklärt:

1. Ein `/user/update`-Payload kann direkt als Mainboard-RS485-Frame interpretiert werden.
2. `/user/get` wird praktisch unverändert zum Mainboard weitergegeben.
3. `unpack_mcu_modbus()` besitzt **nur acht echte Dispatch-Einträge**, allesamt OTA-/Boardservice-bezogen.
4. Normale Heizungs-/Status-/Parameterregister werden vom LTE-Programm nicht in eine eigene Struktur übersetzt.
5. Zwei zusätzliche lokal behandelte normale Sonderbereiche sind nachgewiesen: DTU-Info `0x01F4` und ProductKey `0x00C8`.
6. Für das unbekannte normale Registermapping muss die Semantik deshalb aus Mainboard-Firmware, passiven RS485-Mitschnitten oder Cloud/App-Decodierung gewonnen werden – nicht aus einer versteckten LTE-Registermap.

## 12. Beweisgrad

### Bewiesen

- komplette 8-Einträge-Tabelle von `unpack_mcu_modbus()`;
- Handleradresse und Register jedes Eintrags;
- keine weitere normale Dispatch-Tabelle in dieser Funktion;
- Register `0x00C8` wird lokal als 32-Byte-ProductKey übernommen;
- Register `0x01F4` wird lokal durch `response_DTU_info_request()` beantwortet;
- normaler `/user/get` Callback gibt Payload unverändert an den UART weiter;
- der scheinbare `memcmp(...,"status",6)` beeinflusst den Kontrollfluss nicht;
- `ali_mqtt_push_msg()` publiziert Originalpuffer und Originallänge unverändert;
- normale FC10-Frames erhalten nach dem Publish ein lokales ACK.

### Noch offen

- exakte Zweckbezeichnung von `0x0006` und die Bedeutung des einzelnen Registerwerts `0x0004`; dessen Ablaufwirkung als Trigger für acht Geräteinfoblöcke und späteres C544 ist inzwischen [live bestätigt](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md);
- genaue Bedeutung aller Statistik-/Fehlerfelder um `0x988FC` und `0x91B60`;
- komplette UART-Senderoutine hinter dem Sendeflag inklusive Timing;
- welche Mainboardregister die Cloud im normalen Betrieb aktiv über `/user/get` abfragt/schreibt – dafür ist Live-/Logkorrelation oder Cloud/App-Code nötig.
