# PHNIX `phnixIot4G` – exakte MQTT-CONNECT-/TLS-Parameter

Stand: 2026-08-22

Ergänzung zu `PHNIX_phnixIot4G_tls_mqtt_trust.md`. Grundlage ist ausschließlich statische Analyse des bereitgestellten ungestrippten ARM-ELF `phnixIot4G`.

## Kurzfazit

Der Aliyun-SDK-Pfad baut in diesem Firmwarestand eine feste MQTT-3.1.1-Verbindung über TLS 1.2 auf. Besonders wichtig für das Labor ist, dass der verwendete Timestamp **nicht aus der aktuellen Uhrzeit kommt**, sondern als fester String im ELF liegt:

```text
2524608000000
```

Der Broker-Hostname für die in `ali_mqtt_init()` konfigurierte Region 4 ist:

```text
<productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com
```

Port:

```text
1883
```

TLS ist trotzdem aktiv, weil der Verbindungsdatensatz einen nicht-NULL `pub_key`-/CA-Zeiger enthält.

---

## 1. Region, Host und Port

`ali_mqtt_init()` setzt vor `IOT_SetupConnInfo()`:

```text
IOT_Ioctl(0, &domain_type)
domain_type = 4

IOT_Ioctl(2, &value)
value = 0
```

Die Domain-Tabelle des SDK enthält in dieser Reihenfolge:

```text
0  iot-as-mqtt.cn-shanghai.aliyuncs.com
1  iot-as-mqtt.ap-southeast-1.aliyuncs.com
2  iot-as-mqtt.ap-northeast-1.aliyuncs.com
3  iot-as-mqtt.us-west-1.aliyuncs.com
4  iot-as-mqtt.eu-central-1.aliyuncs.com
```

`iotx_guider_authenticate()` baut den Host mit dem Formatstring bei VA `0x0869C8`:

```text
%s.%s
```

Ergebnis:

```text
<productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com
```

Der Port wird bei `iotx_guider_authenticate()` als `0x075B` gesetzt:

```text
1883
```

---

## 2. Timestamp ist statisch fest eingebettet

`guider_get_timestamp_str()` bei `0x23E60` ruft `HAL_Snprintf()` mit:

```text
format: "%s"
source: VA 0x0869B0
```

Der String an `0x0869B0` lautet exakt:

```text
2524608000000
```

Damit verwendet dieser Build im normalen MQTT-Authentisierungspfad **keine Echtzeit-Uhr und keinen dynamisch erzeugten Unix-Timestamp**.

Das ist für einen lokalen Testbroker wichtig: Client-ID und HMAC sind reproduzierbar, solange ProductKey, DeviceName, DeviceID und DeviceSecret gleich bleiben.

---

## 3. Device-Info-Struktur für MQTT-Signatur

`iotx_device_info_set()` baut eine interne Device-Info-Struktur auf. Die für MQTT relevanten Felder liegen logisch bei:

```text
+0x00  productKey
+0x15  deviceName
+0x36  deviceID
+0x77  deviceSecret
```

`deviceID` wird aus ProductKey und DeviceName aufgebaut und entspricht im Standardfall:

```text
<productKey>.<deviceName>
```

Die eigentlichen produktiven PHNIX-Puffer bleiben separat:

```text
productKey    0x94EB8
deviceName    0x94EDC
deviceSecret  0x94F00
```

---

## 4. Exakter HMAC-SHA1-Eingabestring

`_calc_hmac_signature()` bei `0x23564` besitzt zwei Formatpfade. Im hier verwendeten Aufruf aus `iotx_guider_authenticate()` sind die optionalen Extension-Parameter 0, daher wird der einfache Formatstring bei `0x0867B4` verwendet:

```text
clientId%sdeviceName%sproductKey%stimestamp%s
```

Die vier Werte werden in dieser Reihenfolge eingesetzt:

```text
clientId   = deviceID = <productKey>.<deviceName>
deviceName = <deviceName>
productKey = <productKey>
timestamp  = 2524608000000
```

Der tatsächlich signierte ASCII-String ist damit:

```text
clientId<productKey>.<deviceName>deviceName<deviceName>productKey<productKey>timestamp2524608000000
```

HMAC-Key:

```text
<deviceSecret>
```

Algorithmus:

```text
HMAC-SHA1
```

`utils_hmac_sha1()` bei `0x3971C` wandelt die 20 Rohbytes anschließend nibbleweise mit `utils_hb2hex()` in ASCII-Hex um.

Ergebnisformat des Passworts:

```text
40 ASCII-Hexzeichen
```

Kein Base64.

---

## 5. MQTT Username

`iotx_guider_authenticate()` verwendet den Formatstring bei `0x0869D0`:

```text
%s&%s
```

Argumente:

```text
1. deviceName
2. productKey
```

Daher:

```text
username = <deviceName>&<productKey>
```

---

## 6. Exakte Client-ID

Der Client-ID-Formatstring liegt bei VA `0x0869D8`:

```text
%s|securemode=%d,timestamp=%s,signmethod=hmacsha1,gw=%d,ext=%d%s%s|
```

Für diesen Build:

```text
%s          = deviceID = <productKey>.<deviceName>
securemode  = 2
timestamp   = 2524608000000
gw          = 0
ext         = 0
partner_id  = leer, sofern HAL_GetPartnerID() nichts liefert
module_id   = leer, sofern HAL_GetModuleID() nichts liefert
```

Normalfall:

```text
<productKey>.<deviceName>|securemode=2,timestamp=2524608000000,signmethod=hmacsha1,gw=0,ext=0|
```

Falls Partner-/Module-ID gesetzt sind, werden zusätzlich diese Fragmente angehängt:

```text
,partner_id=<value>
,module_id=<value>
```

---

## 7. MQTT-CONNECT-Parameter aus `ali_mqtt_init()`

Der lokale MQTT-Parameterblock bei `0x989F4` wird in `ali_mqtt_init()` befüllt:

| Offset | Wert | Bedeutung |
|---:|---|---|
| `+0x00` | `1883` | Port |
| `+0x04` | Host-Pointer | `<productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com` |
| `+0x08` | Client-ID-Pointer | siehe oben |
| `+0x0C` | Username-Pointer | `<deviceName>&<productKey>` |
| `+0x10` | Password-Pointer | 40-stelliges HMAC-SHA1-Hex |
| `+0x14` | `pub_key` / CA-Pointer | `iotx_ca_crt` |
| `+0x18` | `0` | CleanSession |
| `+0x1C` | `2000` ms | Request timeout |
| `+0x20` | `300000` ms | Keepalive-Vorgabe |
| `+0x24` | TX buffer | 4096 Byte |
| `+0x28` | `4096` | TX buffer size |
| `+0x2C` | RX buffer | 4096 Byte |
| `+0x30` | `4096` | RX buffer size |
| `+0x34` | Event callback | PHNIX MQTT callback |

`iotx_mc_init()` teilt die Keepalive-Vorgabe durch 1000 und schreibt daher in den MQTT-CONNECT-Datensatz:

```text
keepAliveInterval = 300 Sekunden
```

---

## 8. MQTT-Protokoll und CONNECT-Flags

`iotx_mc_init()` kopiert zunächst die konstante 88-Byte-`MQTTPacket_connectData`-Initialstruktur von VA `0x087CB0`.

Deren Kennungen beginnen mit:

```text
"MQTC"
...
MQTTVersion default/overwrite
...
"MQTW"
```

Danach setzt der Code explizit:

```text
MQTTVersion       = 4
keepAliveInterval = 300
cleansession      = 0
clientID          = berechnete Client-ID
username          = <deviceName>&<productKey>
password          = HMAC-SHA1-Hex
```

`MQTTVersion = 4` entspricht **MQTT 3.1.1**.

Für die CONNECT-Flags folgt daraus:

```text
Username Flag    = 1
Password Flag    = 1
Will Retain      = 0
Will QoS         = 0
Will Flag        = 0
Clean Session    = 0
Reserved         = 0
```

CONNECT-Flags-Byte somit:

```text
0xC0
```

Das Programm fordert also eine **persistente MQTT-Session** an (`CleanSession=0`).

---

## 9. TLS-Version ist exakt TLS 1.2

In `_TLSConnectNetwork()` wird nach `mbedtls_ssl_config_defaults()` explizit aufgerufen:

```c
mbedtls_ssl_conf_max_version(conf, 3, 3);
mbedtls_ssl_conf_min_version(conf, 3, 3);
```

mbedTLS-Protokollversion:

```text
major = 3
minor = 3
```

entspricht:

```text
TLS 1.2
```

Damit akzeptiert dieser Pfad weder TLS 1.0/1.1 noch TLS 1.3.

Ein lokaler Broker muss daher TLS 1.2 anbieten.

---

## 10. Zertifikatsmodus

In `_TLSConnectNetwork()`:

```text
wenn CA/pub_key != NULL:
    mbedtls_ssl_conf_authmode(..., 2)

wenn CA/pub_key == NULL:
    mbedtls_ssl_conf_authmode(..., 0)
```

mbedTLS:

```text
2 = MBEDTLS_SSL_VERIFY_REQUIRED
0 = MBEDTLS_SSL_VERIFY_NONE
```

Im normalen PHNIX-Pfad ist `pub_key` gesetzt, daher:

```text
VERIFY_REQUIRED
```

Zusätzlich:

```text
mbedtls_ssl_set_hostname(ssl, mqtt_host)
mbedtls_ssl_handshake()
mbedtls_ssl_get_verify_result()
_real_confirm()
```

Das lokale Brokerzertifikat muss also sowohl von der verwendeten CA validiert werden als auch zum originalen MQTT-Hostname passen.

---

## 11. Client-Zertifikat / Client-Key

`_TLSConnectNetwork()` besitzt generischen mbedTLS-Code für:

```text
mbedtls_ssl_conf_own_cert()
```

Der normale Aliyun-MQTT-Aufruf von `HAL_SSL_Establish()` übergibt jedoch keine produktive PHNIX-Client-Zertifikat-/Private-Key-Konfiguration. Die MQTT-Authentisierung geschieht auf Anwendungsebene über:

```text
Username + HMAC-SHA1-Passwort
```

Für den lokalen Broker ist daher kein TLS-Clientzertifikat erforderlich.

---

## 12. Cipher-Suites

`_TLSConnectNetwork()` ruft **kein** `mbedtls_ssl_conf_ciphersuites()` auf. Es bleibt die statisch einkompilierte mbedTLS-Defaultliste aktiv.

`mbedtls_ssl_list_ciphersuites()` iteriert eine feste ID-Liste ab VA `0x08E3C4`.

Die bevorzugten ersten IDs lauten:

```text
0xC02C
0xC030
0x009F
0xC0AD
0xC09F
0xC024
0xC028
0x006B
0xC00A
0xC014
0x0039
0xC0AF
0xC0A3
0xC087
0xC08B
0xC07D
0xC073
0xC077
0x00C4
0x0088
0xC02B
0xC02F
0x009E
...
```

Für das Labor ist daher kein spezieller Cipher-Patch nötig. Ein TLS-1.2-Broker mit einem üblichen RSA-Zertifikat und normaler OpenSSL-Cipherauswahl sollte einen gemeinsamen Cipher finden. Falls der Broker seine Cipherliste stark einschränkt, sollte sie zunächst breit gelassen werden.

---

## 13. Minimaler lokaler Broker – was er akzeptieren muss

TLS-Ebene:

```text
TLS version: TLS 1.2
SNI/Hostname: <productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com
Serverzertifikat: SAN enthält exakt diesen Hostnamen
Serverzertifikat: von der im Prozess verwendeten Lab-CA signiert
Client certificate: nicht erforderlich
```

MQTT-Ebene:

```text
Protocol: MQTT 3.1.1
ClientID:
<productKey>.<deviceName>|securemode=2,timestamp=2524608000000,signmethod=hmacsha1,gw=0,ext=0|

Username:
<deviceName>&<productKey>

Password:
hex(HMAC-SHA1(
    key = deviceSecret,
    data = "clientId<productKey>.<deviceName>deviceName<deviceName>productKey<productKey>timestamp2524608000000"
))

Keepalive: 300 s
CleanSession: 0
Will: none
```

Ein reiner Laborbroker kann Username/Password entweder genau gegen diese Formel prüfen oder – für einen ersten Transporttest – beliebige MQTT-Credentials akzeptieren. TLS-Zertifikatsprüfung im Originalclient sollte dabei trotzdem aktiv bleiben.

---

## 14. Konsequenz für den geplanten isolierten Test

Der kleinste saubere Laboraufbau bleibt:

```text
1. Originalen MQTT-Hostname beibehalten.
2. Nur innerhalb des isolierten VM-Netzes DNS auf den lokalen Broker zeigen lassen.
3. Brokerzertifikat mit SAN = originaler MQTT-Hostname erzeugen.
4. Zertifikat mit eigener Lab-CA signieren.
5. Im Originalprozess ausschließlich den `iotx_ca_crt`-Pointer auf die Lab-CA umstellen.
6. Broker auf TLS 1.2 konfigurieren.
7. MQTT 3.1.1 CONNECT mit CleanSession=0 akzeptieren.
```

Damit bleiben alle relevanten Sicherheitsprüfungen des Originalprogramms aktiv; nur der Trust Anchor wird gezielt auf die isolierte Labor-PKI umgestellt.
