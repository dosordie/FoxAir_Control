# PHNIX `phnixIot4G` – TLS-/MQTT-Vertrauenspfad

Stand: 2026-08-22

Ziel dieser Analyse ist ausschließlich ein **vollständig netzisoliertes Labor**: Das unveränderte Originalprogramm soll mit einem lokalen TLS-MQTT-Testserver sprechen können, ohne Verbindung zur echten Cloud. Grundlage ist statische Analyse des bereitgestellten, ungestrippten ARM-ELF `phnixIot4G`.

## Kurzfazit

- Der MQTT-TLS-Pfad läuft über das statisch in `phnixIot4G` eingebettete mbedTLS.
- Der Trust Anchor ist ein statisch eingebettetes GlobalSign-Root-CA-PEM.
- Produktionspfad: CA != NULL -> TLS -> `MBEDTLS_SSL_VERIFY_REQUIRED`.
- `mbedtls_ssl_set_hostname()` wird mit dem MQTT-Host aufgerufen; damit werden SNI und Hostname-Verifikation aktiviert.
- Nach dem Handshake wird zusätzlich `mbedtls_ssl_get_verify_result()` ausgewertet und durch `_real_confirm()` geprüft.
- Kein TLS-Clientzertifikat wird im MQTT-Pfad verwendet.
- Der SDK besitzt zwar einen Plain-TCP-Pfad bei `pub_key == NULL`, aber PHNIX exponiert dafür keinen normalen Konfigurationsschalter.
- Der kleinste saubere Laboreingriff ist **keine Verify-Bypass-Patcherei**, sondern nur den CA-Pointer/CA-Inhalt auf eine lokale Test-CA umzulenken und den originalen Hostnamen lokal auf den Testbroker aufzulösen.
- `-0x0052` ist in diesem Build eindeutig `MBEDTLS_ERR_NET_UNKNOWN_HOST`.

---

## 1. Vollständiger Aufrufpfad

### PHNIX-/Aliyun-Ebene

```text
ali_mqtt_init()                         0x1F034
  -> IOT_SetupConnInfo(...)
     -> iotx_guider_authenticate()
        -> iotx_ca_get()                0x24438
        -> iotx_conn_info füllen
  -> mqtt_params @ 0x989F4 füllen
  -> IOT_MQTT_Construct(&mqtt_params)   0x2CEC4
     -> iotx_mc_init()                  0x2A9A4
        -> iotx_net_init()              0x38DC8
     -> iotx_mc_connect()               0x2B80C
        -> network->connect()
           -> iotx_net_connect()        0x38D10
              -> connect_ssl()          0x389F0
                 -> HAL_SSL_Establish() 0x4A1C8
                    -> _TLSConnectNetwork() 0x49644
```

### mbedTLS-Ebene

```text
_TLSConnectNetwork()
  -> _ssl_client_init()                 0x49124
     -> mbedtls_x509_crt_parse()
     -> mbedtls_ssl_config_defaults()
     -> mbedtls_ssl_conf_authmode()
     -> mbedtls_ssl_conf_ca_chain()
     -> optional mbedtls_ssl_conf_own_cert()
  -> mbedtls_net_connect_timeout()
  -> mbedtls_ssl_setup()
  -> mbedtls_ssl_set_hostname()
  -> mbedtls_ssl_set_bio()
  -> mbedtls_ssl_handshake()
  -> mbedtls_ssl_get_verify_result()
  -> _real_confirm()                    0x48FD4
```

Damit ist der komplette MQTT-Vertrauenspfad vom PHNIX-Wrapper bis zur Zertifikatsprüfung geschlossen.

---

## 2. Strukturen und Feldbelegung

### `iotx_conn_info`

`iotx_guider_authenticate()` füllt die Connection-Info. Die für MQTT relevanten Offsets sind:

| Offset | Inhalt |
|---:|---|
| `+0x000` | Port (`uint16_t`) |
| `+0x002` | Hostname-String |
| `+0x083` | Client-ID |
| `+0x184` | Username |
| `+0x385` | Password/Signatur |
| `+0x488` | `pub_key`/CA-Zeiger |

Produktiv wird Port **1883** gesetzt.

### `mqtt_params @ 0x989F4`

`ali_mqtt_init()` überträgt aus `iotx_conn_info`:

| Offset | Inhalt |
|---:|---|
| `+0x00` | Port |
| `+0x04` | Host |
| `+0x08` | Client-ID |
| `+0x0C` | Username |
| `+0x10` | Password |
| `+0x14` | `pub_key`/CA |
| `+0x18` | Session-/Flagbyte, im PHNIX-Pfad 0 |
| `+0x1C` | Request-Timeout = 2000 ms |
| `+0x20` | Keepalive = 300000 ms = 300 s |
| `+0x24` | Sendepuffer |
| `+0x28` | Sendepuffergröße = 4096 |
| `+0x2C` | Empfangspuffer |
| `+0x30` | Empfangspuffergröße = 4096 |
| `+0x34` | Eventcallback `event_handle()` = `0x1EB24` |
| `+0x38` | Callback-Kontext = 0 |

### `iotx_net_init()` / Network-Struktur

Die Network-Struktur ist 36 Byte groß:

| Offset | Inhalt |
|---:|---|
| `+0x00` | Host-Zeiger |
| `+0x04` | Port (`uint16_t`) |
| `+0x06` | Länge `pub_key` (`uint16_t`) |
| `+0x08` | `pub_key`/CA-Zeiger |
| `+0x0C` | sekundärer TLS-/PSK-Zeiger; im PHNIX-Pfad 0 |
| `+0x10` | SSL-Handle |
| `+0x14` | Read-Funktion |
| `+0x18` | Write-Funktion |
| `+0x1C` | Disconnect-Funktion |
| `+0x20` | Connect-Funktion |

`iotx_net_init()` setzt `+0x06 = strlen(pub_key)`, falls `pub_key != NULL`.

### `HAL_SSL_Establish()` -> `_TLSConnectNetwork()`

`HAL_SSL_Establish()` übergibt:

```text
host
port-as-decimal-string
CA/pub_key pointer
CA/pub_key length
client certificate = NULL
client certificate length = 0
client private key = NULL
client private key length = 0
private-key password = NULL
password length = 0
```

Damit verwendet dieser MQTT-Pfad **nur Serverauthentisierung**, kein TLS-Clientzertifikat.

---

## 3. Herkunft des CA-/`pub_key`-Zeigers

### Globaler Pointer

Symbol:

```text
iotx_ca_crt @ 0x91CD0
size = 4
```

In `.data` steht dort little-endian:

```text
C0 6B 08 00
```

also:

```text
*(void **)0x91CD0 = 0x086BC0
```

`iotx_ca_get()` bei `0x24438` gibt ausschließlich diesen Pointer zurück.

`iotx_guider_authenticate()` liest ihn und schreibt ihn in:

```text
iotx_conn_info + 0x488
```

### PEM-Blob

- ELF-VA: **`0x086BC0`**
- Dateioffset: **`0x07EBC0`**
- Länge ohne NUL: **1280 Byte**
- Länge inkl. NUL: **1281 Byte**
- Format: PEM
- statisch eingebettet: **ja**

Inhalt: **GlobalSign Root CA**.

```pem
-----BEGIN CERTIFICATE-----
MIIDdTCCAl2gAwIBAgILBAAAAAABFUtaw5QwDQYJKoZIhvcNAQEFBQAwVzELMAkG
A1UEBhMCQkUxGTAXBgNVBAoTEEdsb2JhbFNpZ24gbnYtc2ExEDAOBgNVBAsTB1Jv
b3QgQ0ExGzAZBgNVBAMTEkdsb2JhbFNpZ24gUm9vdCBDQTAeFw05ODA5MDExMjAw
MDBaFw0yODAxMjgxMjAwMDBaMFcxCzAJBgNVBAYTAkJFMRkwFwYDVQQKExBHbG9i
YWxTaWduIG52LXNhMRAwDgYDVQQLEwdSb290IENBMRswGQYDVQQDExJHbG9iYWxT
aWduIFJvb3QgQ0EwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDaDuaZ
jc6j40+Kfvvxi4Mla+pIH/EqsLmVEQS98GPR4mdmzxzdzxtIK+6NiY6arymAZavp
xy0Sy6scTHAHoT0KMM0VjU/43dSMUBUc71DuxC73/OlS8pF94G3VNTCOXkNz8kHp
1Wrjsok6Vjk4bwY8iGlbKk3Fp1S4bInMm/k8yuX9ifUSPJJ4ltbcdG6TRGHRjcdG
snUOhugZitVtbNV4FpWi6cgKOOvyJBNPc1STE4U6G7weNLWLBYy5d4ux2x8gkasJ
U26Qzns3dLlwR5EiUWMWea6xrkEmCMgZK9FGqkjWZCrXgzT/LCrBbBlDSgeF59N8
9iFo7+ryUp9/k5DPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNVHRMBAf8E
BTADAQH/MB0GA1UdDgQWBBRge2YaRQ2XyolQL30EzTSo//z9SzANBgkqhkiG9w0B
AQUFAAOCAQEA1nPnfE920I2/7LqivjTFKDK1fPxsnCwrvQmeU79rXqoRSLblCKOz
yj1hTdNGCbM+w6DjY1Ub8rrvrTnhQ7k4o+YviiY776BQVvnGCv04zcQLcFGUl5gE
38NflNUVyRRBnMRddWQVDf9VMOyGj/8N7yy5Y0b2qvzfvGn9LhJIZJrglfCm7ymP
AbEVtQwdpf5pLGkkeB6zpxxxYu7KyJesF12KwvhHhm4qxFYxldBniYUr+WymXUad
DKqC5JlR3XC321Y9YeRq4VzW9v493kHMB65jUr9TU/Qr6cf9tveCX4XSQRjbgbME
HMUfpIBvFSDJ3gyICh3WZlXi/EjJKSZp4A==
-----END CERTIFICATE-----
```

Zertifikatsdaten:

- Subject/Issuer: `C=BE, O=GlobalSign nv-sa, OU=Root CA, CN=GlobalSign Root CA`
- Serial: `040000000001154B5AC394`
- Gültigkeit: 1998-09-01 bis 2028-01-28
- SHA-256 Fingerprint: `EB:D4:10:40:E4:BB:3E:C7:42:C9:E3:81:D3:1E:F2:A4:1A:48:B6:68:5C:96:E7:CE:F3:C1:DF:6C:D4:33:1C:99`
- RSA 2048
- Signaturalgorithmus: SHA1-RSA

Der Pointer selbst liegt in **beschreibbarer `.data`**. Das ist für ein Labor wichtig: Man kann den Trust Anchor zur Laufzeit umlenken, ohne den Kontrollfluss der TLS-Prüfung zu verändern.

---

## 4. Prüfung der Serverzertifikatskette

`_ssl_client_init()` parst die CA mit:

```text
mbedtls_x509_crt_parse(ca_chain, ca_ptr, ca_len)
```

In `_TLSConnectNetwork()` gilt:

```text
CA != NULL
  -> mbedtls_ssl_conf_authmode(conf, MBEDTLS_SSL_VERIFY_REQUIRED)

CA == NULL
  -> mbedtls_ssl_conf_authmode(conf, MBEDTLS_SSL_VERIFY_NONE)
```

Beim Produktionspfad ist CA immer ungleich NULL.

Danach:

```text
mbedtls_ssl_conf_ca_chain(conf, &ca_chain, NULL)
```

Nach dem Handshake:

```text
flags = mbedtls_ssl_get_verify_result(ssl)
_real_confirm(flags)
```

`_real_confirm()` wertet Zertifikatsfehler explizit als Fehler. Damit findet nicht nur die mbedTLS-Verify-Required-Prüfung statt, sondern zusätzlich noch eine explizite Nachkontrolle der Verify-Flags.

**Ergebnis:** Die Zertifikatskette wird tatsächlich geprüft.

---

## 5. Hostnameprüfung und SNI

Nach `mbedtls_ssl_setup()` ruft `_TLSConnectNetwork()` explizit auf:

```text
mbedtls_ssl_set_hostname(ssl, host)
```

Callsite liegt im Bereich `0x49A74..0x49A80`.

Damit wird derselbe MQTT-Hostname in den mbedTLS-Kontext übernommen. Bei dieser mbedTLS-Generation dient das sowohl als TLS-SNI-Servername als auch als Referenzname für die X.509-CN/SAN-Prüfung.

Für den Labortest sollte deshalb **nicht** einfach auf `localhost` umgestellt werden. Besser:

1. originalen MQTT-Hostnamen beibehalten,
2. diesen ausschließlich im isolierten Lab-DNS bzw. `/etc/hosts` auf den lokalen Broker zeigen lassen,
3. lokales Serverzertifikat mit genau diesem Hostnamen in SAN/CN erzeugen,
4. Zertifikat mit der lokalen Test-CA signieren.

So bleibt der gesamte originale Vertrauenspfad einschließlich Hostnameprüfung erhalten.

---

## 6. mbedTLS: statisch oder dynamisch?

mbedTLS ist **statisch in `phnixIot4G` eingebettet**.

Relevante interne/ globale Symbole:

```text
_TLSConnectNetwork              0x49644
_ssl_client_init                0x49124
_real_confirm                   0x48FD4
HAL_SSL_Establish               0x4A1C8
mbedtls_ssl_set_hostname        0x5AFBC
mbedtls_ssl_handshake           0x5B6E8
mbedtls_ssl_get_verify_result   0x5B26C
mbedtls_x509_crt_parse          0x5E31C
mbedtls_ssl_conf_authmode       0x5A774
mbedtls_ssl_conf_ca_chain       0x5ABE8
mbedtls_ssl_conf_own_cert       0x5ABA8
```

Das ELF enthält unter anderem die Compilereinheit/Dateibezeichnung:

```text
HAL_TLS_mbedtls.c
```

Es gibt **keine** `DT_NEEDED`-Abhängigkeit auf `libmbedtls`, `libmbedx509` oder `libmbedcrypto`.

Dynamisch vorhanden sind hingegen beispielsweise:

```text
libssl.so.1.0.0
libcrypto.so.1.0.0
libcurl.so.5
libmosquitto.so.1
```

Diese OpenSSL-Bibliotheken gehören anderen Pfaden. Der Aliyun-MQTT-TLS-Pfad verwendet das statisch eingelinkte mbedTLS.

### Konsequenz für Interposing

Ein normales `LD_PRELOAD` kann **nicht einfach `mbedtls_ssl_get_verify_result()` oder `mbedtls_ssl_set_hostname()` ersetzen**, weil diese Funktionen im Executable selbst definiert und per direkten `BL`-Calls aufgerufen werden. Es gibt dafür keinen dynamischen PLT/GOT-Aufruf.

Daher ist ein Verify-Interposer hier **nicht** der zweitbeste Weg; eine reine Datenumlenkung des CA-Pointers ist wesentlich sauberer.

---

## 7. Vorhandene Konfigurationspfade

### MQTT ohne TLS

Der Aliyun-Netzwerk-Layer besitzt einen eingebauten Plain-TCP-Zweig:

```text
iotx_net_connect():

pub_key == NULL && secondary_tls_ptr == NULL
  -> connect_tcp()

pub_key != NULL && secondary_tls_ptr == NULL
  -> connect_ssl()
```

Der PHNIX-Produktionspfad liefert jedoch über `iotx_ca_get()` immer einen nicht-NULL-CA-Pointer. Ein normaler PHNIX-Konfigurationsschalter auf Plain MQTT wurde nicht gefunden.

### Zertifikatsprüfung deaktivieren

Innerhalb `_TLSConnectNetwork()` existiert technisch:

```text
CA == NULL -> MBEDTLS_SSL_VERIFY_NONE
```

Im normalen Netzwerk-Layer würde derselbe NULL-`pub_key` aber bereits dazu führen, dass statt TLS `connect_tcp()` gewählt wird. Es gibt im PHNIX-Code keinen sichtbaren Konfigurationspfad „TLS an, Verify aus“.

### Alternative CA

Kein Dateipfad wie `/etc/...ca.pem` oder vergleichbarer Loader wurde gefunden. Die CA kommt aus dem statischen Pointer `iotx_ca_crt @ 0x91CD0`.

Technisch kann der Pointer aber zur Laufzeit geändert werden, weil er in `.data` liegt.

### Benutzerdefinierter MQTT-Host/Port

Kein normaler Konfigurationsdateipfad gefunden.

Der Host wird durch den Aliyun-Guider erzeugt:

```text
<productKey>.<region-domain>
```

Region 4 entspricht in diesem Build:

```text
iot-as-mqtt.eu-central-1.aliyuncs.com
```

also typischerweise:

```text
<productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com
```

Der Port wird vom Guider auf **1883** gesetzt. Wichtig: In diesem SDK bedeutet Port 1883 nicht automatisch Plaintext; weil `pub_key != NULL`, läuft der Transport über TLS auf diesem Port.

---

## 8. Kleinster sicherer Labor-Eingriff

### Bevorzugte Variante: nur Trust Anchor umleiten

Der sauberste Test erhält den gesamten originalen TLS-Kontrollfluss:

```text
Originalprogramm unverändert
Originaler MQTT-Hostname unverändert
Originale Hostname-/SNI-Prüfung unverändert
Originales VERIFY_REQUIRED unverändert
Originaler MQTT-Auth-String unverändert

Nur:
iotx_ca_crt pointer -> lokale Test-CA
```

Zusätzlich wird **nur innerhalb des isolierten Testnetzes** der originale generierte MQTT-Hostname auf den lokalen Broker aufgelöst.

Der Broker erhält ein Serverzertifikat:

```text
SAN = <productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com
Issuer = lokale Test-CA
```

und lauscht zweckmäßig auf Port 1883 mit TLS, damit weder Host noch Port im Programm geändert werden müssen.

### Variante A: Runtime-Datenpatch ohne Änderung des Executables

Weil das Binary `ET_EXEC`/non-PIE ist, ist die Adresse stabil:

```text
0x91CD0 = Pointervariable iotx_ca_crt
```

Ein kleiner ARM-`LD_PRELOAD`-Constructor kann **nur diesen Datenpointer** auf einen im Preload-Objekt enthaltenen Test-CA-PEM-String umsetzen. Das Original-ELF bleibt bitidentisch.

Das ist ein Trust-Anchor-Austausch, kein Verify-Bypass.

### Variante B: PEM in-place ersetzen

Alternativ kann eine Laborkopie des ELF das PEM ab Dateioffset `0x07EBC0` ersetzen, sofern das neue PEM inklusive NUL in die vorhandenen 1281 Byte passt. Der Pointer muss dann nicht verändert werden.

Diese Variante verändert allerdings die Binärdatei und ist deshalb weniger elegant als Runtime-Datenumlenkung.

### Interposition einer Prüffunktion

Für die statischen mbedTLS-Funktionen **nicht sinnvoll**: direkte interne Calls, kein PLT/GOT.

### Kontrollfluss-Patch

Erst als letzte Option wären denkbar:

- `_real_confirm()` umgehen,
- `mbedtls_ssl_conf_authmode()` auf VERIFY_NONE zwingen,
- Hostnameprüfung überspringen.

Für das Laborziel ist das unnötig und schlechter, weil damit gerade der zu untersuchende Vertrauenspfad deaktiviert würde.

---

## 9. `-0x0052`

`mbedtls_net_connect_timeout()` ruft `getaddrinfo()` auf.

Bei Fehler erzeugt die Funktion an `0x49450`:

```text
mvn r3, #81
```

Bitweise Negation von 81 ergibt:

```text
-82 decimal = -0x52
```

Im Binary ist dazu die mbedTLS-Fehlermeldung sinngemäß „Failed to get an IP address for the given hostname“ vorhanden.

Damit ist für diesen Build **bewiesen**:

```text
-0x0052 = MBEDTLS_ERR_NET_UNKNOWN_HOST
```

---

## 10. MQTT-Authentisierung und CONNECT

### Host

Format:

```text
%s.%s
```

also:

```text
<productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com
```

für die in diesem Build verwendete EU-Central-Region.

### Port

```text
1883
```

Transport bleibt wegen `pub_key != NULL` TLS.

### Username

Formatstring:

```text
%s&%s
```

Argumente:

```text
deviceName, productKey
```

also:

```text
<deviceName>&<productKey>
```

### HMAC-Password

`_calc_hmac_signature()` verwendet:

```text
HMAC-SHA1
key = deviceSecret
```

Signierstring ohne `ext`:

```text
clientId%sdeviceName%sproductKey%stimestamp%s
```

mit:

```text
clientId    = <productKey>.<deviceName>
deviceName  = <deviceName>
productKey  = <productKey>
timestamp   = <Guider timestamp>
```

Wenn `ext` aktiviert ist, lautet das Format:

```text
clientId%sdeviceName%sext%dproductKey%stimestamp%s
```

Der HMAC-SHA1 wird als textuelle Hexsignatur in `iotx_conn_info+0x385` abgelegt und als MQTT-Passwort verwendet.

### Client-ID

Format:

```text
%s|securemode=%d,timestamp=%s,signmethod=hmacsha1,gw=%d,ext=%d%s%s|
```

Der Basis-Client-ID-String ist:

```text
<productKey>.<deviceName>
```

`guider_get_secure_mode()` liefert in diesem Build:

```text
securemode = 2
```

Typische Ausgabe:

```text
<productKey>.<deviceName>|securemode=2,timestamp=<timestamp>,signmethod=hmacsha1,gw=0,ext=0|
```

Optional können noch Partner-/Modulfelder ergänzt werden.

### MQTT-Protokollparameter

Aus `iotx_mc_init()`:

```text
MQTTVersion = 4
```

also **MQTT 3.1.1**.

Keepalive:

```text
mqtt_params + 0x20 = 300000 ms
-> CONNECT keepalive = 300 s
```

Der PHNIX-Pfad setzt das Session-/Clean-Session-Flagbyte in `mqtt_params+0x18` auf 0.

Will-Daten werden im normalen Initpfad nicht gesetzt.

Send-/Receive-Puffer:

```text
4096 / 4096 Byte
```

### Minimaler lokaler Broker

Der lokale Broker muss die Aliyun-Signatur **nicht nachprüfen**, wenn im Labor anonyme/ungeprüfte MQTT-Authentisierung erlaubt wird. Das Originalprogramm sendet trotzdem seine unveränderten Client-ID-/Username-/Password-Felder.

Für maximale Protokolltreue kann später ein lokaler Auth-Plugin/Proxy die oben rekonstruierte HMAC-SHA1-Signatur prüfen; für den ersten TLS/MQTT-Handshake ist das nicht erforderlich.

---

## 11. Empfohlenes vollständig isoliertes Labordesign

```text
phnixIot4G
  |
  | TLS 1.2 / MQTT 3.1.1 / Port 1883
  v
lokaler Broker

Lab-DNS:
  <productKey>.iot-as-mqtt.eu-central-1.aliyuncs.com -> lokale Broker-IP

Serverzertifikat:
  SAN = originaler Aliyun-Hostname
  signiert von Lab-CA

phnixIot4G Trust Anchor:
  iotx_ca_crt -> Lab-CA
```

Netzwerknamespace/Firewall sollte ausschließlich den lokalen Broker erreichbar machen; kein Default-Route-Pfad zur echten Cloud.

Damit bleiben unverändert aktiv:

- DNS-Hostname aus dem Originalprogramm,
- TCP-Verbindungslogik,
- TLS 1.2,
- CA-Chain-Verifikation,
- SNI,
- Hostnameprüfung,
- MQTT 3.1.1,
- Aliyun-Client-ID,
- Username,
- HMAC-SHA1-Passwort,
- Keepalive.

Geändert wird ausschließlich **wem das Originalprogramm vertraut**, und selbst das kann durch Runtime-Datenumlenkung erfolgen, ohne das Original-ELF zu verändern.

---

## 12. Beweisgrad / offene Punkte

### Bewiesen

- vollständiger Call-Pfad bis `_TLSConnectNetwork()`;
- statisch eingebettetes mbedTLS;
- CA-Pointer `0x91CD0` -> PEM `0x086BC0`;
- PEM-Länge 1280 + NUL;
- GlobalSign Root CA;
- `VERIFY_REQUIRED` bei vorhandener CA;
- `mbedtls_ssl_set_hostname()` wird ausgeführt;
- `mbedtls_ssl_get_verify_result()` + `_real_confirm()`;
- kein MQTT-TLS-Clientzertifikat/-Private-Key;
- Plain-TCP-Zweig des SDK bei NULL-`pub_key`;
- `-0x0052 = MBEDTLS_ERR_NET_UNKNOWN_HOST`;
- Usernameformat `<deviceName>&<productKey>`;
- HMAC-SHA1 mit DeviceSecret;
- MQTT 3.1.1;
- Keepalive 300 s.

### Noch sinnvoll dynamisch im isolierten Labor zu bestätigen

- exakter zur Laufzeit erzeugter Client-ID-String inklusive optionaler `partner_id`/`module_id`-Felder;
- tatsächlicher Timestamp-Wert bzw. dessen Quelle im Guider;
- ob der lokale Broker Clean Session = 0 exakt so im CONNECT sieht;
- vollständige mbedTLS-Cipher-Suite-Liste des kompilierten Builds.
