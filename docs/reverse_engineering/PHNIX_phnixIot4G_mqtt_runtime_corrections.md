# PHNIX `phnixIot4G` – MQTT Runtime-Korrekturen und statische Einordnung

Stand: 2026-08-22

Diese Datei korrigiert zwei Annahmen aus `PHNIX_phnixIot4G_mqtt_connect_exact.md` anhand des inzwischen erfolgreichen isolierten TLS/MQTT-Lauftests und gleicht sie mit dem ARM-ELF statisch ab.

## 1. Keepalive ist effektiv 180 s, nicht 300 s

`ali_mqtt_init()` setzt im lokalen MQTT-Parameterblock bei `0x989F4 + 0x20` zunächst tatsächlich:

```text
300000 ms
```

Die frühere statische Interpretation, daraus würden 300 s im CONNECT entstehen, war unvollständig.

In `iotx_mc_set_connect_params()` liegt bei `0x2A66C` eine explizite Obergrenze:

```text
ldr/ldrh keepalive
cmp keepalive, #180
bls use_requested_value
...
mov r2, #180
strh r2, [client + 0x500]
```

Damit wird jeder angeforderte MQTT-Keepalive >180 s auf **180 Sekunden** gekappt.

Der reale CONNECT mit Keepalive 180 s bestätigt genau diesen Codepfad.

### Korrigierter Ablauf

```text
ali_mqtt_init()
  requested keepalive = 300000 ms
    ↓
SDK wandelt auf Sekunden
    ↓
iotx_mc_set_connect_params()
    ↓
requested = 300 > 180
    ↓
effective CONNECT keepalive = 180 s
```

## 2. Partner-ID und Module-ID sind nicht leer

Im ELF sind die beiden HAL-Rückgabewerte statisch eingebettet:

```text
VA 0x081B4C: example.demo.partner-id
VA 0x081B64: example.demo.module-id
```

Die Funktionen:

```text
HAL_GetPartnerID() @ 0x465BC
HAL_GetModuleID()  @ 0x46628
```

kopieren diese Strings direkt in die vom Aliyun-Guider bereitgestellten Zielpuffer.

Daher enthält die tatsächlich erzeugte Client-ID zusätzlich:

```text
,partner_id=example.demo.partner-id
,module_id=example.demo.module-id
```

Die dynamische Aufzeichnung bestätigt das.

## 3. Was aus der bisherigen CONNECT-Rekonstruktion weiterhin bestätigt ist

Der isolierte Lauf bestätigt weiterhin:

```text
TLS            = TLS 1.2
MQTT           = 3.1.1
CONNECT flags  = 0xC0
CleanSession   = 0
Timestamp      = 2524608000000
Username       = <deviceName>&<productKey>
Password       = 40 Hex-Zeichen aus HMAC-SHA1
```

Der Client-ID-Grundaufbau bleibt:

```text
<productKey>.<deviceName>|securemode=2,timestamp=2524608000000,signmethod=hmacsha1,gw=0,ext=0,partner_id=example.demo.partner-id,module_id=example.demo.module-id|
```

## 4. Automatische Aktionen unmittelbar nach erfolgreichem MQTT-Connect

Die statische Analyse von `ali_mqtt_init()` zeigt nach erfolgreichem `IOT_MQTT_Construct()` diese Reihenfolge:

```text
1. Subscribe OTA_GET, QoS 1
2. Subscribe user/get, QoS 1
3. IOT_MQTT_Yield(..., 300)
4. globales MQTT-ready Flag = 1
5. http_ommunicationDeviceLog(...)
6. aliMqtt_push_error_topic_to_phnix()
7. uart485_get_device_info()
```

Damit ist mindestens ein automatischer Publish direkt aus `ali_mqtt_init()` selbst erklärbar: `aliMqtt_push_error_topic_to_phnix()`.

Danach wird mit `uart485_get_device_info()` das Mainboard-Register `0x0004` abgefragt. Sobald dessen Antwort über den normalen RS485-Pfad eintrifft, wird sie als rohe Binärpayload auf `/user/update` publiziert.

Weitere automatische Publishes können parallel aus den bereits laufenden Threads entstehen, insbesondere aus OTA-/Board-Info- und Statistikpfaden. Die nun eingeführten PUBACKs sind daher der richtige Weg, um die einmaligen Nachrichten ohne QoS-1-Wiederholungen sauber zu klassifizieren.

## 5. Konsequenz für die weitere Auswertung

Für die nächsten isolierten Runs sollten ausgehende QoS-1-PUBLISH-Pakete nach mindestens diesen Merkmalen gruppiert werden:

```text
topic
packet_id
payload_len
payload hex/ascii
DUP flag
QoS
retain
first_seen timestamp
```

Bei `/user/update` ist die Nutzlast voraussichtlich direkt als RS485-/Modbus-Frame interpretierbar.

Bei `/user/OTA_UPDATE` ist JSON mit `CMD_OTA` / Code-Feldern zu erwarten.

Damit lassen sich dynamische Publishes anschließend direkt auf ihre statischen Aufrufer zurückführen.
