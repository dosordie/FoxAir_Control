# PHNIX `phnixIot4G` – Identity-/ProductKey-Pfad über RS485

Stand: 2026-08-23

Grundlage: statische Analyse von `uart485_get_productKey()` im ungestrippten ARM-ELF `phnixIot4G`.

## Kurzfazit

Die Cloudidentität des LTE-Dienstes kommt nicht ausschließlich vom Modem oder aus lokaler Persistenz. Das Mainboard liefert über die Hersteller-RS485-Services mindestens:

```text
12-Byte deviceID-artige Identität
32-Byte ProductKey
```

Diese Werte werden direkt in die globalen Aliyun-/Warmlink-Identity-Puffer übernommen und sind Voraussetzung für den weiteren Startup-/Credential-Pfad.

---

## 1. Zentrale Funktion

```text
uart485_get_productKey() @ 0x14354
```

Sie arbeitet direkt auf dem RS485-UART und parst mehrere unterschiedliche Hersteller-Serviceantworten.

Der UART-FD wird aus dem globalen UART-Kontext übernommen; die Funktion baut/selectiert zunächst einen Request und liest anschließend bis zu 200 Byte Antwortdaten.

---

## 2. 12-Byte `deviceID` aus Boardantwort

Ein erkannter Antworttyp beginnt mit:

```text
0x63 0x03 0xB4 ...
```

Bei gültiger Länge kopiert der Code:

```c
memcpy(aliMqtt_get_deviceID_buf(), rx + 3, 12);
```

Ein weiterer Service-Antworttyp beginnt mit:

```text
0x63 0x10 0x07 0xD1 ...
```

und kopiert ebenfalls 12 Byte, diesmal aus:

```c
memcpy(aliMqtt_get_deviceID_buf(), rx + 7, 12);
```

Damit kann derselbe globale `deviceID`-Puffer aus unterschiedlichen Mainboard-Serviceantworten gefüllt werden.

Der globale Aliyun-Puffer liegt im späteren MQTT-Kontext; `aliMqtt_set_deviceID()` verwaltet zusätzlich einen eigenen Buffer bei etwa `0x94F44`.

---

## 3. 32-Byte ProductKey direkt vom Mainboard

Ein weiterer erkannter Frame besitzt Headerbytes:

```text
0x63 0x10 0x00 0xC8 ...
```

Nach CRC-Prüfung über `Check_crc()` ruft der Code:

```text
aliMqtt_get_product_buf()
```

auf und kopiert anschließend:

```c
memcpy(productKeyBuffer, rx + 7, 32);
```

Der ProductKey ist damit eindeutig Mainboard-seitig bereitgestellt.

**Praktische Konsequenz:** Ein LTE-Modem ist nicht vollständig unabhängig austauschbar. Für den normalen Hersteller-Startup braucht es die passende Mainboardidentität/ProductKey-Antwort auf RS485.

---

## 4. Startup-State 4 -> 5 hängt an dieser RS485-Identity-Phase

Wenn `uart485_get_productKey()` noch keine gültige Antwort erhalten hat und:

```text
dtu_run_step == 4
```

sendet die Funktion erneut einen Boardrequest. Nach dem entsprechenden Identity-/ProductKey-Fortschritt setzt sie:

```c
set_dtu_run_step(5);
```

Damit liegt die Reihenfolge sinngemäß bei:

```text
LTE/Modemgrundinitialisierung
 -> dtu_run_step 4
 -> Mainboard ProductKey/deviceID per RS485
 -> dtu_run_step 5
 -> weitere Credential-/Cloudinitialisierung
```

Dies bestätigt, dass die Mainboardidentität bereits vor der Aliyun-Cloudinitialisierung in den LTE-Prozess einfließt.

---

## 5. Sonder-/Testpfad mit IMEI und ICCID

Die Funktion enthält zusätzlich einen Sonderpfad, der bei einem internen Test-/Fallbackflag Informationen aus:

```text
DmsAPI_get_imei_cache()
UimAPI_get_iccid()
```

verwendet und daraus einen Diagnose-/Identitätsstring aufbaut.

Das zeigt, dass IMEI/ICCID lokal verfügbar sind, sie ersetzen im normalen Produktpfad aber nicht einfach den vom Mainboard gelieferten ProductKey.

---

## 6. Bedeutung für eigene Warmlink-Tools

Für eine vollständige lokale Replikation oder ein Ersatz-LTE-Gateway sollte zwischen folgenden Identitäten unterschieden werden:

```text
Mainboard ProductKey        32 Byte, über RS485
Mainboard/Service deviceID  12 Byte, über RS485
Modem IMEI                  aus DMS/QMI
SIM ICCID                   aus UIM/QMI
Aliyun DeviceName           Cloud-/SDK-Kontext
Aliyun DeviceSecret         Provisionierungs-/Credentialpfad
PHNIX deviceCode            separater Hersteller-Identifier
```

Diese Werte sind nicht austauschbar und besitzen unterschiedliche Herkunft und Rollen.

---

## 7. Nächster sinnvoller Schritt

Noch zu klären sind:

- exakte Register-/Payloadbedeutung der Serviceantworten `0xB4xx`, `0x07D1` und `0x00C8`;
- welcher 12-Byte-Identifier im Feld tatsächlich in `deviceID` landet;
- wie `deviceCode`, `deviceID`, ProductKey und Aliyun DeviceName beim HTTP-Provisioning zusammengeführt werden;
- ob der ProductKey auf verschiedenen Mainboardmodellen unterschiedlich ist oder eine Produktfamilie bezeichnet.
