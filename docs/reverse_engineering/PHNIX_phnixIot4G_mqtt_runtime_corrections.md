# PHNIX `phnixIot4G` – MQTT Runtime-Korrekturen und statische Einordnung

Stand: 2026-08-22

Diese Datei dokumentiert die inzwischen erfolgreiche isolierte TLS/MQTT-Ausführung des unveränderten Originalprogramms und gleicht die dynamischen Beobachtungen mit der statischen Analyse des ARM-ELF ab.

## 1. Isolierter TLS/MQTT-Laborpfad erfolgreich bestätigt

Das originale `phnixIot4G` konnte in einer vollständig netzisolierten Laborumgebung bis zu einem lokalen TLS-MQTT-Testserver ausgeführt werden.

Dynamisch bestätigt:

```text
TLS version       = TLS 1.2
Cipher            = AES256-SHA256
CA verification   = aktiv
Hostname verify   = aktiv
MQTT protocol     = 3.1.1
CONNECT flags     = 0xC0
Clean Session     = 0
Timestamp         = 2524608000000
Keepalive         = 180 s
Password          = 40-stellige HMAC-SHA1-Hexdarstellung
partner_id        = example.demo.partner-id
module_id         = example.demo.module-id
```

Die MQTT-Authentisierung stimmt damit bis auf die unten dokumentierten statischen Korrekturen mit der vorherigen Rekonstruktion überein.

## 2. Keepalive ist effektiv 180 s, nicht 300 s

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

## 3. Partner-ID und Module-ID sind nicht leer

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

## 4. Bestätigte CONNECT-Parameter

Der isolierte Lauf bestätigt:

```text
TLS            = TLS 1.2
MQTT           = 3.1.1
CONNECT flags  = 0xC0
CleanSession   = 0
Timestamp      = 2524608000000
Username       = <deviceName>&<productKey>
Password       = 40 Hex-Zeichen aus HMAC-SHA1
Keepalive      = 180 s
```

Der Client-ID-Aufbau ist damit:

```text
<productKey>.<deviceName>|securemode=2,timestamp=2524608000000,signmethod=hmacsha1,gw=0,ext=0,partner_id=example.demo.partner-id,module_id=example.demo.module-id|
```

Der tatsächliche TLS-Cipher im erfolgreichen Laborlauf war:

```text
AES256-SHA256
```

## 5. Automatische MQTT-Reihenfolge nach CONNACK

Der erfolgreiche isolierte Lauf zeigt unmittelbar nach CONNACK folgende automatische Reihenfolge:

```text
1. Aliyun-Statusmeldung
2. SDK-Version 2.2.1.1
3. AliOS-Aktivierungsinformation
4. OTA-Modemversion app-1.0.0-20180101.1000
5. SUBSCRIBE /<productKey>/<deviceName>/user/OTA_GET, QoS 1
6. SUBSCRIBE /<productKey>/<deviceName>/user/get, QoS 1
7. Fehler-/Statusmeldung auf /<productKey>/<deviceName>/user/update/error
```

Die ersten PUBLISH-Pakete wurden zunächst wiederholt, weil der Recorder QoS-1-PUBLISH noch nicht mit PUBACK quittierte. Nach Ergänzung der PUBACK-Behandlung lassen sich die einmaligen Publishes sauber voneinander trennen.

Wichtig: Während dieses Laufs wurde **keine Nachricht an `OTA_GET` oder `user/get` gesendet**. Damit wurde weder ein OTA-Vorgang noch ein MQTT→RS485-Transfer ausgelöst.

## 6. Statische Einordnung der Post-Connect-Reihenfolge

Die statische Analyse von `ali_mqtt_init()` zeigt nach erfolgreichem `IOT_MQTT_Construct()` mindestens diesen applikationsseitigen Teil:

```text
SUBSCRIBE OTA_GET, QoS 1
SUBSCRIBE user/get, QoS 1
IOT_MQTT_Yield(...)
MQTT-ready Flag = 1
http_ommunicationDeviceLog(...)
aliMqtt_push_error_topic_to_phnix()
uart485_get_device_info()
```

Die dynamisch beobachteten Aliyun-Status-/SDK-/AliOS-/Modemversions-Publishes entstehen damit teilweise bereits innerhalb des Aliyun-SDK-/Startup-Pfads vor bzw. um die PHNIX-spezifischen Subscriptions herum.

Die abschließende Nachricht auf `/user/update/error` passt zum statisch bekannten `aliMqtt_push_error_topic_to_phnix()`-Pfad.

Nach erfolgreichem MQTT-Init wird anschließend `uart485_get_device_info()` ausgelöst. Diese Funktion erzeugt den bekannten Mainboard-Read:

```text
63 03 00 04 00 01 CD 89
```

Eine spätere gültige Mainboard-Antwort darauf würde über den normalen Binärpfad als `/user/update` erscheinen.

## 7. Sicherheitskontrolle des Laborlaufs

Für den dynamischen Test wurde explizit kontrolliert:

```text
Network namespace : ausschließlich Loopback 127.0.0.1
Default route      : keine
External cloud     : nicht erreichbar
Original binary    : unverändert
Lab trust anchor   : separate Laborkopie mit eigener CA
Original SHA256    : 7c573431…eaedb7
```

Damit ist der beobachtete TLS-/MQTT-Verkehr ausschließlich dem lokalen Testserver zuzuordnen.

## 8. Nächster sicherer Test: synthetischer `user/get`-Downlink

Vor einem Test von `OTA_GET` ist der normale MQTT-Downlink der sinnvollere nächste Schritt.

Statisch erwarteter Pfad:

```text
Broker PUBLISH /user/get
  -> Aliyun MQTT callback
  -> aliMqtt_topic_get_msg_arrive()
  -> uart485_send_data_to_board(payload, len)
  -> uart485WriteBuf
  -> UART send flag
  -> /dev/ttyHSL2
```

Der Callback prüft dabei selbst weder Modbus-Funktionscode noch CRC.

Für einen ersten rein synthetischen Transporttest eignet sich deshalb bewusst ein acht Byte langes Frame mit ungültiger CRC:

```text
63 03 00 04 00 01 00 00
```

Erwartete Sequenz:

```text
Broker -> Client:
PUBLISH QoS1 /<productKey>/<deviceName>/user/get
payload = 63 03 00 04 00 01 00 00

Client -> Broker:
PUBACK

Client -> ttyHSL2:
63 03 00 04 00 01 00 00
```

Solange der Board-Stub darauf nicht antwortet, wird aus diesem Test kein `/user/update` erwartet.

Erst in einer zweiten Stufe sollte ein gültiger, bereits bekannter Read verwendet werden:

```text
63 03 00 04 00 01 CD 89
```

Damit lässt sich anschließend die komplette normale Rundstrecke prüfen:

```text
/user/get
  -> UART
  -> synthetische Boardantwort
  -> getDevParameter()
  -> /user/update
```

Dieser Test bleibt vollständig außerhalb des OTA-Protokolls.

## 9. Beweisstand

### Dynamisch bestätigt

- TLS 1.2;
- vollständige CA- und Hostnameprüfung;
- Cipher `AES256-SHA256`;
- MQTT 3.1.1;
- CONNECT flags `0xC0`;
- Clean Session aus;
- Keepalive 180 s;
- fester Timestamp `2524608000000`;
- 40-stelliges HMAC-Passwortformat;
- Partner-/Module-ID aktiv;
- beide Subscriptions `OTA_GET` und `user/get`, jeweils QoS 1;
- automatische Startup-Publishes einschließlich `/user/update/error`;
- keine eingehende OTA-/user/get-Nachricht während des Baseline-Laufs.

### Statisch bestätigt

- Keepalive-Cap bei 180 s;
- Herkunft von Partner-/Module-ID;
- normaler `/user/get`-Callback reicht Payload unverändert Richtung UART weiter;
- `/user/update/error` stammt aus dem PHNIX-Fehlerstatuspfad;
- nach erfolgreichem MQTT-Init wird Register `0x0004` am Mainboard gelesen.
