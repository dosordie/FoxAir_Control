# PHNIX `phnixIot4G` – Architektur und interessante Nicht-OTA-Funktionen

Stand: 2026-08-23

Grundlage: statische Analyse des ungestrippten ARM-ELF `phnixIot4G` (Build-ID `af4dcae12639bedce833ee5efa5da009777b6319`). Schwerpunkt dieser Datei sind bewusst **nicht** der Mainboard-OTA-Pfad, sondern Prozessarchitektur, Mobilfunk/QMI, Cloud/Provisionierung, RS485-Bridging, Diagnose, Statistik, LEDs, Debugschnittstellen und auffällige Alt-/Testpfade.

## Kurzfazit

`phnixIot4G` ist wesentlich mehr als ein Modbus-zu-MQTT-Gateway. Der Prozess vereint:

```text
SIMCom/Qualcomm-Modemzugriff (QMI + Alt-AT-Pfade)
PHNIX-/linked-go-Provisionierung per HTTP
Aliyun-IoT-MQTT
RS485-Serviceprotokoll zum Mainboard
Fehler-/LED-State-Machine
Statistik-/Persistenz
Debugausgabe
Hardware-/GPIO-/Power-Management
```

Viele alte AT-/Demo-Komponenten sind noch vollständig einkompiliert, obwohl der aktive Produktpfad weitgehend QMI + Linux + Aliyun-SDK nutzt.

---

## 1. Plattform: SIMCom / Qualcomm MDM9607

Debug- und Symbolnamen zeigen klar einen SIMCom-/Qualcomm-Unterbau, u. a.:

```text
simcom-sdk
mdm9607-perf
DMSControl.c
NASControl.c
UIMControl.c
```

Der Dienst verwendet QMI-nahe APIs für DMS/NAS/UIM.

### NAS / Netzstatus

Relevante Funktionen:

```text
NasAPI_init()                    @ 0x1E038
NasAPI_thread_handle()           @ 0x1E23C
NasAPI_show_NetworkType()        @ 0x1E05C
NasAPI_get_registration_state()  @ 0x1E168
NasAPI_get_cs_attach_state()     @ 0x1E18C
NasAPI_get_ps_attach_state()     @ 0x1E1B0
NasAPI_get_selected_network()    @ 0x1E1D4
NasAPI_get_radio_if_len()        @ 0x1E1F8
NasAPI_get_radio_if()            @ 0x1E21C
NasAPI_get_SignalStrength()      @ 0x1E2B0
NasAPI_get_MCC()                 @ 0x1E2FC
NasAPI_get_MNC()                 @ 0x1E328
NasAPI_get_LAC()                 @ 0x1E354
NasAPI_get_CELL_ID()             @ 0x1E380
```

Damit besitzt der Prozess intern mindestens:

```text
Registration State
CS/PS Attach State
Network Type / RAT
Signal Strength
MCC / MNC
LAC
Cell-ID
Selected Network
Radio Interface
```

### UIM / SIM

```text
UimAPI_init()             @ 0x1E584
UimAPI_thread_handle()    @ 0x1E7B0
UimAPI_show_sim_status()  @ 0x1E630
UimAPI_get_card_status()  @ 0x1E6E0
UimAPI_get_app_type()     @ 0x1E704
UimAPI_get_app_state()    @ 0x1E728
UimAPI_get_pin_state()    @ 0x1E74C
UimAPI_get_iccid()        @ 0x1E770
UUimAPI_get_imsi()        @ 0x1E790
```

Globale Identitätsbuffer beinhalten u. a. ICCID, IMSI und IMEI.

**Praktischer Nutzen:** Auf dem Modem selbst stehen deutlich mehr LTE-Diagnosedaten zur Verfügung als die wenigen Warmlink-Felder, die nach außen sichtbar sind.

---

## 2. Zwei Mobilfunk-/Kommunikationsgenerationen im selben Binary

Das ELF enthält sowohl einen älteren AT-basierten Stack als auch neuere direkte Linux/QMI-/SDK-Pfade.

### Alter AT-Pfad über `/dev/smd8`

Beispiele:

```text
AT_ATE0
AT_CPIN
AT_APN1
AT_APN6
AT_GetCSQ
AT_GetCGREG
AT_GetCREG
AT_GetCGSN
AT_GetCGMM
AT_GetCCID
AT_CGATT
```

Zusätzlich existieren ältere AT-basierte HTTP- und MQTT-Funktionen.

### Neuerer Produktpfad

```text
QMI / NAS / UIM / DMS
libcurl
Aliyun IoT SDK
TLS
MQTT direkt aus Linux
```

**Bewertung:** Das Binary ist historisch gewachsen. Das Vorhandensein einer Funktion oder eines Strings beweist daher nicht automatisch, dass der Pfad im aktuellen Produktbetrieb benutzt wird.

---

## 3. PHNIX-/linked-go-HTTP zusätzlich zu Aliyun

Im ELF stehen direkte PHNIX-/Linked-Go-Endpunkte, u. a. mit Basis:

```text
http://cloud.linked-go.com:84
```

Beispiele:

```text
/cloudservice/api/phnixiot/queryiotdevice.json
/cloudservice/api/communicationDevice/createDeviceBySign
/cloudservice/api/communicationDevice/queryiotdevice.json
/cloudservice/api/communicationDevice/create_communicationDeviceLog.json
```

Daraus ergibt sich mindestens diese Architektur:

```text
PHNIX / linked-go HTTP
    -> Gerätezuordnung / Provisionierung / Logs
    -> Credentials / Mapping

Aliyun IoT MQTT
    -> normaler Warmlink-Datenverkehr
    -> OTA
```

Damit erklärt sich, warum im Binary sowohl PHNIX-spezifische HTTP-Logik als auch der große Aliyun-IoT-Stack vorhanden sind.

---

## 4. Geräteidentität und Provisionierung

Im ELF finden sich u. a.:

```text
deviceCode      global @ 0x92008
deviceID        mehrere Buffer
ProductKey
DeviceName
DeviceSecret
ProductSecret
IMEI
ICCID
IMSI
```

Provisionierungs-JSON enthält Felder wie:

```json
{
  "productKey":"...",
  "deviceID":"...",
  "deviceCode":"...",
  "sign":"..."
}
```

Zusätzlich enthält der Aliyun-SDK-Pfad Dynamic Registration für `DeviceSecret`.

Damit existieren mehrere Identitätsebenen:

```text
deviceCode
PHNIX deviceID
IMEI/Modemidentität
Aliyun DeviceName
ProductKey
DeviceSecret
```

Die exakte Herkunft und Priorität dieser Werte wird separat weiter analysiert.

---

## 5. Normaler MQTT-Kanal

Die Topics werden dynamisch aus ProductKey und DeviceName aufgebaut. Sichtbar sind mindestens:

```text
/<productKey>/<deviceName>/user/get
/<productKey>/<deviceName>/user/update
/<productKey>/<deviceName>/user/update/error

/<productKey>/<deviceName>/user/OTA_GET
/<productKey>/<deviceName>/user/OTA_UPDATE
```

Vereinfachte Richtung:

```text
Cloud -> Modem   /user/get
Modem -> Cloud   /user/update
Fehler           /user/update/error
OTA separat      /user/OTA_*
```

Für eine eigene Warmlink-Bridge sind insbesondere `/user/get` und `/user/update` interessant.

---

## 6. Fehler-/Diagnosekanal

Relevante Funktion:

```text
aliMqtt_push_error_topic_to_phnix() @ 0x20100
```

Globale Zustände:

```text
ErrorStatue @ 0x93124
ErrorTag    @ 0x9312B
set_Error_Flag() @ 0x17864
Get_ErrorStatue() @ 0x1793C
```

Im Binary vorhandene Fehlertexte umfassen u. a.:

```text
485 connected error
Address error
Cloud connected error
WF_double_error
Crc error
```

Damit besitzt das LTE-Modul einen eigenen Fehlerzustandsautomaten und meldet Fehler separat zum normalen Telemetriekanal.

---

## 7. LED-State-Machine

Im ELF existieren dedizierte Funktionen für Kommunikations-, Fehler- und Signalstärkeanzeigen, u. a.:

```text
led_failure_on/off
led_communication_on/off
led_high_on/off
led_middle_on/off
led_weak_on/off
ChangeErrorLedStatue()
comm_and_exc_led()
comled_blink_start()
comled_blink_stop()
led_thread_handle()
```

Das spricht für lokale Zustände für:

```text
Fehler
Kommunikation
Signal hoch
Signal mittel
Signal schwach
Blink-/Intervallzustände
```

Die Signal-LEDs können direkt aus dem NAS/QMI-Signalwert versorgt werden; keine Cloudinformation ist dafür erforderlich.

---

## 8. Lokale Statistikpersistenz

Neben OTA_INFO existiert:

```text
/data/phnixIot_device_statisic
```

Globale Struktur:

```text
statistic_para @ 0x91B60
Größe ca. 128 Byte
```

Funktionen:

```text
static_read_data()  @ 0x10598
static_write_data() @ 0x106F0
add_static_data()   @ 0x1078C
```

Beim Prozessstart wird `static_read_data(1)` aufgerufen. Dabei werden nicht einfach alle Werte übernommen; einzelne Felder werden abhängig vom Modus zurückgesetzt oder weitergeführt.

**Bewertung:** Das ist eine persistente Betriebs-/Statistikstruktur, keine reine Logdatei. Eine vollständige Feldzuordnung ist sinnvoll.

---

## 9. HTTP-Diagnoselogs an PHNIX

Relevante Funktionen:

```text
Upload_bord_log() @ 0x10898
Check_upload_log()
http_ommunicationDeviceLog()
```

Zielpfad:

```text
/cloudservice/api/communicationDevice/create_communicationDeviceLog.json
```

Der Dienst sammelt dafür u. a. Geräteidentitäten und Fehlerstatus und kann Logtexte getrennt vom normalen MQTT-Telemetriepfad an PHNIX senden.

**Praktischer Nutzen:** Herstellerdiagnose läuft nicht ausschließlich über MQTT.

---

## 10. RS485 ist mehr als ein Modbus-Tunnel

Relevante Funktionen:

```text
uart485_get_productKey()  @ 0x14354
uart485_get_device_info() @ 0x15698
response_DTU_info_request()
check_mcu_get_sta()
```

Über dieselbe RS485-Schnittstelle laufen neben normalen Modbusdaten auch Serviceinformationen wie:

```text
ProductKey
SoftwareCode
SoftwareVersion
Geräteidentität
DTU-Status
OTA-Serviceframes
```

Das Mainboard-LTE-Protokoll ist damit ein erweitertes Hersteller-Serviceprotokoll; normaler Modbus ist nur ein Teil davon.

---

## 11. RS485-Healthcheck

```text
Check485Statue() @ 0x156B4
```

Das LTE-Modul führt einen eigenen aktiven RS485-Healthcheck durch und besitzt einen expliziten Fehlerzustand `485 connected error`.

Interessant für eigene Diagnose: Der Hersteller beurteilt Mainboard-Erreichbarkeit damit nicht ausschließlich anhand des Zeitpunkts des letzten normalen Modbus-Telegramms.

---

## 12. LTE-Diagnoseumfang

Intern verfügbar sind deutlich mehr Daten als in Warmlink typischerweise angezeigt werden:

```text
Registration State
CS/PS Attach
RAT / Network Type
Signal Strength
MCC/MNC
LAC
Cell-ID
Roaming-/Netzstatus
Radio Interface
```

Das ist ein guter Ansatz für eine spätere lokale LTE-Diagnoseseite.

---

## 13. SIM-Diagnose

Über UIM sind mindestens verfügbar:

```text
Card Status
Application Type
Application State
PIN State
ICCID
IMSI
```

Zusammen mit IMEI liegen damit alle üblichen Modem-/SIM-Identitäten lokal im Prozess vor.

---

## 14. Eingebetteter Aliyun-IoT-SDK-Stack

Ein großer Teil des ELF stammt aus einem statisch eingebundenen Aliyun-IoT-C-SDK und enthält u. a.:

```text
MQTT
HTTP Client
TLS / mbedTLS
Dynamic Registration
KV Store
JSON
SHA1 / SHA256 / MD5
HMAC
RSA
X509
AES
Base64
```

Wichtig für Reverse Engineering:

> Das Vorhandensein von RSA/SHA/X509 im ELF bedeutet nicht automatisch, dass PHNIX diese Funktionen für Firmware- oder Nutzdaten-Signaturen verwendet. Ein erheblicher Teil gehört nur zum TLS-/Aliyun-SDK.

---

## 15. Eingebettete Root-CA

Das ELF enthält einen PEM-CA-Block und das Symbol:

```text
iotx_ca_crt
```

Damit verwendet der Aliyun-TLS-Pfad einen eingebetteten Trustanker.

Eine spätere Detailanalyse kann bestimmen, welche CA/Chain dieser Build konkret akzeptiert.

---

## 16. Aliyun-KV-Store

SDK-Funktionen:

```text
HAL_Kv_Set
HAL_Kv_Get
HAL_Kv_Del
kv_open / kv_get / kv_set / kv_del
```

sichtbarer Pfad:

```text
/tmp/kvfile.db
```

Strings zeigen u. a.:

```text
product_key
device_secret
product_secret
DyncRegDeviceSecret
```

Damit liegen nicht alle Credentials in PHNIX-eigenen `/data/phnix...`-Dateien; der Aliyun-SDK-Stack besitzt einen eigenen KV-Speicher.

---

## 17. Hardware-/Power-Management

Neben GPIO-Funktionen wie:

```text
EAT_InitGpio()
EAT_ReadGpio()
EAT_WriteGpio()
common_writeGpio()
```

existieren direkte Linux-Power-Management-Kommandos, z. B. sinngemäß:

```sh
echo off > /sys/power/autosleep
echo on > /sys/class/tty/ttyHSL1/device/power/control
```

Der Dienst greift also aktiv in Sleep-/UART-Power-Management ein.

---

## 18. Hersteller-/Demo-Altcode `helloworld`

Im ELF sind Kommandos wie:

```sh
cp /data/media/helloworld_bak /cache/helloworld_bak
chmod a+x /cache/helloworld_bak
cp /data/media/helloworld_bak /data/helloworld
chmod a+x /data/helloworld
```

enthalten.

Zusammen mit Pfaden/Namen aus `simcom-demo` spricht das dafür, dass die Anwendung historisch aus einem SIMCom-Demo-/Daemon-Projekt heraus entwickelt wurde und älterer Testcode im Produktbinary verblieben ist.

---

## 19. Debugsystem

Relevante Funktionen:

```text
init_uart_debug()          @ 0x13C88
Debugh()                   @ 0x13D70
DebugHex()                 @ 0x13DA8
DebugTrace()               @ 0x13E20
DebugTrace_no_file_info()  @ 0x13F34
```

Zusätzlich existieren Hinweise auf `/dev/ttyGS0` und separate UART-/Debugpfade.

**Praktischer Nutzen:** Falls diese Debugschnittstelle auf dem Feldgerät aktiv ist, könnten interne Zustände direkt lesbar sein, die weder über RS485 noch MQTT sichtbar sind.

---

# Nächste gezielte Analysen

Die größten praktischen Gewinne versprechen jetzt:

1. `init_uart_debug()` und alle Debugausgabepfade vollständig rekonstruieren;
2. Fehlercodes, `ErrorStatue`, `ErrorTag` und LED-State-Machine vollständig zuordnen;
3. `phnixIot_device_statisic` / `statistic_para` vollständig typisieren;
4. Provisionierungs-/Identity-Pfad `deviceCode` / `deviceID` / IMEI / ProductKey / DeviceName / DeviceSecret exakt auflösen.

Diese vier Punkte werden separat weiter analysiert, da sie für Diagnose und eine eigene lokale Warmlink-Integration mehr Nutzen versprechen als weitere breite OTA-Zerlegung.
