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

---

## 1. MQTT-Topics und Subscription

`ali_mqtt_init()` (`0x1F034`) erzeugt:

- normaler Publish: `/<productKey>/<deviceName>/user/update`
- normaler Subscribe: `/<productKey>/<deviceName>/user/get`
- OTA Publish: `/<productKey>/<deviceName>/user/OTA_UPDATE`
- OTA Subscribe: `/<productKey>/<deviceName>/user/OTA_GET`

Der normale `/user/get`-Topic wird bei `0x1F534–0x1F54C` mit QoS 1 und Callback `aliMqtt_topic_get_msg_arrive()` (`0x1EED0`) registriert.

---

## 2. Cloud -> Mainboard: `aliMqtt_topic_get_msg_arrive()`

Funktion: `0x1EED0`, Länge 356 Byte.

Der Callback greift auf das vom Aliyun-SDK gelieferte Topic-/Message-Objekt zu und verwendet:

- Payload-Zeiger aus dem Messageobjekt,
- Payload-Länge aus dem Messageobjekt.

Nach Debugausgaben passiert funktional fast nichts:

1. Kommunikations-LED wird gestartet.
2. Topic/Payload werden geloggt.
3. Wenn die ersten sechs Payloadbytes exakt ASCII `status` sind, wird ein internes Fehler-/Retrybyte bei `0x988FC+0x14` auf 0 gesetzt.
4. **Danach wird die komplette Payload unverändert an `uart485_send_data_to_board(payload, payload_len)` übergeben.**
5. Zwei Statistikzähler werden inkrementiert.
6. Kommunikations-LED wird gestoppt.

Es gibt in diesem Callback:

- kein `json_tokener_parse()`,
- keinen Base64-Decoder,
- keinen Modbus-Neuaufbau,
- keine CRC-Neuberechnung,
- keine Register-Whitelist.

### Konsequenz

Für den normalen Cloudkanal muss der Server offenbar bereits ein vollständig sendefertiges Binärtelegramm liefern. `phnixIot4G` fungiert als Transportbrücke.

Das unterscheidet sich deutlich vom OTA-Kanal, wo eingehende JSON-Nachrichten (`0033` usw.) semantisch ausgewertet und daraus lokale RS485-Pakete erzeugt werden.

---

## 3. `uart485_send_data_to_board()` ist eine Queue, kein direkter `write()`

Funktion: `0x1562C`.

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

Damit schreibt der MQTT-Callback nicht selbst auf den UART. Er legt nur das Telegramm in den gemeinsamen Sendepuffer. Der UART-Pfad übernimmt die eigentliche Ausgabe.

Pakete >2048 Byte werden verworfen und geloggt.

---

## 4. Mainboard -> Cloud: `getDevParameter()`

Funktion: `0x14D58`.

`getDevParameter()` ist die zentrale Empfangsschleife des normalen Mainboardkanals. Sie liest von dem in `uart485_init()` geöffneten `/dev/ttyHSL2`, sammelt empfangene Bytes in `uart485ReadBuf` (`0x920DC`) und prüft anschließend das Telegramm.

### Zulässige Modbus-Funktionscodes

Nach erfolgreicher CRC-Prüfung werden für den regulären Dispatcher nur diese Funktionscodes akzeptiert:

- `0x10`
- `0x03`
- `0x83`

Andere Funktionscodes werden verworfen und als falscher Modbus-Befehl geloggt.

Danach folgt:

```text
unpack_mcu_modbus(uart485ReadBuf, recv_len)
```

Wenn dieser interne Dispatcher `0` zurückgibt, wird das Telegramm **nicht** normal in die Cloud weitergereicht. Das ist unter anderem der Mechanismus, mit dem lokal behandelte OTA-/Sonderregister abgefangen werden.

Wenn `unpack_mcu_modbus()` ungleich 0 zurückgibt, läuft das Telegramm in den normalen Bridgepfad weiter.

---

## 5. Sonderfälle vor dem normalen MQTT-Publish

### 5.1 Fünf-Byte-Exception-Frame

Wenn die empfangene Länge exakt 5 Byte beträgt und die ersten fünf Bytes exakt

```text
63 83 01 21 2E
```

sind, wird das Paket direkt über `ali_mqtt_push_msg()` publiziert und die weitere Verarbeitung dieses Durchlaufs beendet.

Die Bytefolge ist ein Modbus-Exception-ähnliches Frame (`slave 0x63`, Funktion `0x83`, Exceptioncode `0x01`, CRC `21 2E`).

### 5.2 Acht-Byte-Paket

Bei einer empfangenen Gesamtlänge von exakt 8 Byte wird das Telegramm ebenfalls unmittelbar mit `ali_mqtt_push_msg()` publiziert und anschließend nicht weiter verarbeitet.

### 5.3 Register 500: lokaler DTU-Info-Request

Ein spezieller Read-Request mit:

- Slave `0x60` **oder** `0x63`
- Funktion `0x03`
- Registeradresse `500` (`0x01F4`)

wird nicht zur Cloud geschickt. Stattdessen ruft die Firmware `response_DTU_info_request()` (`0x14A84`) auf und erzeugt die Antwort lokal.

Damit ist Register 500 ein echtes DTU-lokales Service-/Info-Register.

### 5.4 ProductKey-Sonderpfad

Ein weiterer Sonderfall behandelt einen Mainboard-Rückkanal für den ProductKey. Wenn dieser noch nicht im internen `aliMqtt_get_product_buf()` gesetzt ist, wird er aus dem Mainboardtelegramm übernommen. Ist bereits ein ProductKey vorhanden, wird die Meldung verworfen bzw. nur geloggt.

Dieser Pfad erklärt, warum der UART-Worker vor dem eigentlichen Normalbetrieb zunächst wiederholt `uart485_get_productKey()` ausführt.

---

## 6. Normaler Publish: `ali_mqtt_push_msg()`

Funktion: `0x1F6FC`, Länge 692 Byte.

Signatur nach Aufrufern:

```c
int ali_mqtt_push_msg(void *payload, uint32_t payload_len)
```

Vorbedingungen:

1. `UimAPI_get_card_status() == 1`
2. `IOT_MQTT_CheckStateNormal(mqtt_client) > 0`

Wenn MQTT nicht im Normalzustand ist, wird ein Fehlerzähler erhöht und `-1` zurückgegeben.

### MQTT-Message-Struktur

Die Funktion initialisiert eine ca. 20-Byte große Message-Struktur bei `0x98AC4` und setzt unter anderem:

- QoS = 1
- Retain = 0
- Duplicate = 0
- Payload-Zeiger = Funktionsargument `payload`
- Payload-Länge = Funktionsargument `payload_len`

Danach:

```text
IOT_MQTT_Publish(mqtt_client, TOPIC_UPDATE, &message)
```

Das Topic ist der zuvor erzeugte String

```text
/<productKey>/<deviceName>/user/update
```

### Entscheidend

Es gibt **keine Transformation der Nutzdaten** zwischen `getDevParameter()` und `IOT_MQTT_Publish()`:

- kein JSON,
- keine Hexdarstellung,
- keine Base64-Kodierung,
- keine zusätzliche PHNIX-Hülle.

Die RS485-Bytes werden als Binärpayload publiziert.

---

## 7. FC `0x10`: lokales ACK nach dem Cloud-Publish

Nach dem normalen `ali_mqtt_push_msg()` prüft `getDevParameter()` zusätzlich:

```text
uart485ReadBuf[0] == 0x63
uart485ReadBuf[1] == 0x10
```

Wenn beides zutrifft, baut die Firmware aus den ersten sechs Bytes des empfangenen Requests ein acht Byte langes Standard-Modbus-Write-Multiple-Registers-ACK:

```text
[slave]
[0x10]
[register_hi]
[register_lo]
[count_hi]
[count_lo]
[CRC_hi/lo nach implementierter helper-Reihenfolge]
```

und queued dieses mit `uart485_send_data_to_board(..., 8)` zurück zum Mainboard.

Damit ist für normale `0x10`-Meldungen die Reihenfolge:

```text
Mainboard -> DTU: FC10 Datenframe
DTU -> Cloud: identischer Binärframe auf /user/update
DTU -> Mainboard: lokales 8-Byte-FC10-ACK
```

Das ACK hängt nicht von einer Cloudantwort ab.

---

## 8. UART-Worker-Startup

`uart485_thread_handle()` (`0x14918`) macht vor der eigentlichen Endlosschleife:

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

Der normale RS485-Bridgebetrieb startet also erst, nachdem ein ProductKey verfügbar ist.

Das ist ein wichtiger Zusammenhang zur Cloudinitialisierung: UART- und MQTT-Thread laufen parallel, teilen aber ProductKey/Device-ID-Zustände.

---

## 9. Gegenrichtung `/user/get` ist vollständig transparent

Aus statischer Sicht ist der normale Downlink besonders eindeutig:

```text
MQTT payload
  -> aliMqtt_topic_get_msg_arrive()
  -> uart485_send_data_to_board(payload, payload_len)
  -> uart485WriteBuf
  -> UART send flag
  -> /dev/ttyHSL2
```

Der Callback validiert weder Slaveadresse noch Funktionscode noch CRC. Die eigentliche Protokollgültigkeit muss daher entweder:

- bereits serverseitig sichergestellt sein, oder
- vom Mainboard selbst geprüft werden.

Die einzige erkennbare Sonderbehandlung im Callback ist der ASCII-Präfix `status`, der einen internen Retry-/Fehlerzähler zurücksetzt; auch dieses Payload wird anschließend trotzdem zum UART weitergereicht.

---

## 10. Architektur: zwei getrennte Cloudprotokolle

Die Firmware besitzt damit zwei klar verschiedene Kommunikationsmodelle:

### Normaler Kanal

```text
/user/update  : rohe RS485-/Modbus-Bytes nach oben
/user/get     : rohe Binärbytes nach unten
```

### OTA-Kanal

```text
/user/OTA_UPDATE : PHNIX JSON mit CMD_OTA / Codes wie 0003, 0023 ...
/user/OTA_GET    : PHNIX JSON mit Codes wie 0033, 0073 ...
```

Die OTA-Logik ist also **nicht** einfach Teil der normalen transparenten Bridge. Sie ist ein eigener semantischer Protokollstack im selben Prozess.

---

## 11. Relevanz für weitere Analyse / Work

Für die Rekonstruktion der normalen Warmlink/PHNIX-Kommunikation ist jetzt bewiesen:

1. Ein aufgezeichnetes `/user/update`-MQTT-Payload kann direkt als RS485-Frame interpretiert werden.
2. Ein `/user/get`-Payload ist sehr wahrscheinlich bereits das komplette Frame, das das Mainboard sehen soll.
3. Für normale Register muss deshalb primär der Inhalt von `unpack_mcu_modbus()` und die Mainboard-Registersemantik zerlegt werden; es existiert keine zusätzliche JSON-Zuordnungsschicht.
4. OTA muss separat behandelt werden, weil dort JSON-Codes in lokale RS485-OTA-Kommandos übersetzt werden.
5. Die lokal behandelten Sonderfälle (DTU-Info Register 500, ProductKey, OTA-Register) dürfen nicht mit normalen Cloudregistertelegrammen vermischt werden.

## 12. Beweisgrad

### Bewiesen

- normaler `/user/get` Callback bei `0x1EED0` gibt Payload unverändert an `uart485_send_data_to_board()`;
- `uart485_send_data_to_board()` kopiert max. 2048 Byte in den UART-Sendepuffer und setzt ein Sendeflag;
- `ali_mqtt_push_msg()` publiziert den übergebenen Puffer unverändert auf `/user/update`;
- QoS 1 für normalen Publish und Subscribe;
- `getDevParameter()` akzeptiert nach CRC-Prüfung FC `0x10`, `0x03`, `0x83` für den Dispatcher;
- `unpack_mcu_modbus()==0` verhindert normalen Cloud-Publish;
- Register 500 wird lokal beantwortet;
- bei normalen Slave-`0x63`/FC10-Meldungen wird lokal ein 8-Byte-ACK erzeugt.

### Noch offen

- vollständige Registerliste des **normalen** `unpack_mcu_modbus()`-Dispatchers;
- genaue Bedeutung aller internen Statistik-/Fehlerfelder um `0x988FC` und `0x91B60`;
- genaue UART-Senderoutine hinter dem Sendeflag und deren Timing/Retrylogik;
- ob einzelne normale Cloudframes außerhalb des Callbacks noch vor dem physikalischen UART-Write verändert werden (bisher kein Hinweis darauf).
