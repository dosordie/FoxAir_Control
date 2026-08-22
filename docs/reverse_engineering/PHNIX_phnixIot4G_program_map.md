# PHNIX `phnixIot4G` – Programm-/Thread-Map

Stand: 2026-08-22

Dieser Bericht ergänzt `PHNIX_phnixIot4G_RE.md` um die statische Gesamtzerlegung außerhalb des engen OTA-Pfads. Grundlage ist das ungestrippte ARM-ELF `phnixIot4G` mit Symbolen/DWARF. Keine realen Gerätekennungen oder Secrets werden dokumentiert.

## 1. `main()` bei `0x0000B42C`

Der Startpfad ist statisch eindeutig:

```text
main()
 ├─ init_uart_debug()
 ├─ diverse globale Defaults setzen
 │   ├─ OTA/Status-Flag @ app+0x13 = 1
 │   ├─ Board-OTA Payload-Länge @ app+0x64 = 168
 │   └─ 16-Bit Feld @ app+0x0A = 0
 ├─ static_read_data(1)
 ├─ Boot-/Startzähler in globaler Statistik erhöhen
 ├─ initHardware()
 ├─ AT_GetCGMM()
 ├─ AT_CPIN()
 ├─ AT_GetCCID(UimAPI_get_iccid())
 ├─ AT_APN1()
 ├─ AT_APN6()
 ├─ led_init()
 ├─ pthread_create(..., led_thread_handle)
 ├─ DmsAPI_init()
 ├─ NasAPI_init()
 ├─ pthread_create(..., NasAPI_thread_handle)
 ├─ UimAPI_init()
 ├─ pthread_create(..., UimAPI_thread_handle)
 ├─ pthread_create(..., uart485_thread_handle)
 ├─ pthread_create(..., aliMqtt_handle_thread)
 ├─ pthread_create(..., fota_board_thread_handle)
 └─ danach nur noch Dauerschleife / Sleep
```

Wichtiger Punkt: Die AT-Sequenz `CGMM -> CPIN -> CCID -> APN1 -> APN6` läuft **synchron vor dem Start der Worker-Threads**. Damit erklären die VM-Traces exakt den statischen Programmablauf.

## 2. Worker-Threads

| Thread | Adresse | Aufgabe |
|---|---:|---|
| `led_thread_handle` | `0x17F8C` | LED-/Fehleranzeige |
| `NasAPI_thread_handle` | `0x1E23C` | Mobilfunkregistrierung / NAS-Netzstatus |
| `UimAPI_thread_handle` | `0x1E7B0` | SIM-Status, ICCID, IMSI |
| `uart485_thread_handle` | `0x14918` | `/dev/ttyHSL2`, Board-ProductKey/Device-ID, anschließend permanenter RS485-Empfang |
| `aliMqtt_handle_thread` | `0x1FC28` | Registrierungs-/Credential-/MQTT-State-Machine |
| `fota_board_thread_handle` | `0x1DD4C` | Board-OTA-State-Machine / Upload von Boardinformationen |

## 3. `dtu_run_step`

Accessor:

- `set_dtu_run_step()` `0x1D2F8`
- `get_dtu_run_step()` `0x1D328`

Im gesamten ELF existieren nur vier direkte Setzer mit konstantem Wert:

| Wert | Setzer | Bedeutung |
|---:|---|---|
| `4` | `uart485_init()` `0x141AC` | UART-/Boardkommunikation initialisieren; wird nur gesetzt, wenn das zugehörige Init-Flag noch 0 ist |
| `5` | `uart485_get_productKey()` `0x147AC` | Board-ProductKey/Identitätsabfrage gestartet bzw. Übergang nach initialem UART-Request |
| `7` | `aliMqtt_handle_thread()` `0x1FD5C` | Cloud-Geräte-/Credential-Abfragephase |
| `11` | `aliMqtt_handle_thread()` `0x1FDE8` | MQTT vollständig initialisiert / regulärer Laufzustand |

Es gibt in diesem Build **keine direkten `set_dtu_run_step(6/8/9/10)`-Aufrufe**. Die Zahlenfolge ist also keine lückenlos implementierte State-Machine, sondern verwendet nur ausgewählte historische/semantische Statuswerte.

### Übergang 4 -> 5

`uart485_init()`:

```text
wenn UART-Init-Flag == 0:
    set_dtu_run_step(4)
open("/dev/ttyHSL2", O_RDWR|O_NOCTTY)
set_opt(fd, 9600, 8, 'N', 1)
```

`uart485_get_productKey()` prüft später `get_dtu_run_step()==4`. Dann wird ein acht Byte langer Request auf `/dev/ttyHSL2` geschrieben und anschließend `set_dtu_run_step(5)` gesetzt.

### Übergang 5 -> 7

Der UART-Thread wartet so lange, bis `aliMqtt_get_productKey()` nicht mehr leer ist. Parallel wartet `aliMqtt_handle_thread()` auf Netzregistrierung, IMEI sowie ProductKey-/Credential-Puffer. Solange `deviceSecret` leer ist, setzt er `dtu_run_step=7` und ruft wiederholt:

```text
httpAPI_communicationDevice_queryiotdevice()
```

auf.

### Übergang 7 -> 11

Sobald das DeviceSecret vorhanden ist:

```text
ali_mqtt_init()
while return == -1:
    sleep(3)
    ali_mqtt_init()

set_dtu_run_step(11)
set_dtu_sta(4)
led_communication_on()
ota_dtu_send_version_to_phnix()
```

Anschließend bleibt `aliMqtt_handle_thread()` permanent in einer MQTT-Yield-Schleife:

```text
while true:
    if MQTT handle/state vorhanden:
        IOT_MQTT_Yield(handle, 200)
        bei Fehler: usleep(5000)
    else:
        sleep(5)
```

Damit ist `dtu_run_step == 11` tatsächlich der stabile betriebsbereite Cloudzustand und nicht nur ein kurzer Übergang.

## 4. `aliMqtt_handle_thread()` `0x1FC28`

Rekonstruierter Ablauf:

```text
set_dtu_sta(1)
set_Error_Flag(3)

# Netzregistrierung
while NasAPI_get_registration_state() != 1:
    debug registration state
    sleep(5)
Clear_Error_Flag(3)
set_dtu_sta(2)

# IMEI / DeviceName
set_Error_Flag(1)
while deviceName leer:
    DmsAPI_get_imei(imei_buf)
    sleep(1)
Clear_Error_Flag(1)

# Board ProductKey
while productKey leer:
    falls globales Triggerfeld leer: auf 1 setzen
    debug "warte auf Mainboard productKey"
    sleep(5)

# DeviceSecret / Cloud Device Lookup
set_Error_Flag(9)
while deviceSecret leer:
    set_dtu_run_step(7)
    httpAPI_communicationDevice_queryiotdevice()
    sleep(5)

set_dtu_sta(3)
Clear_Error_Flag(9)

# MQTT
set_Error_Flag(10)
ret = ali_mqtt_init()
while ret == -1:
    ret = ali_mqtt_init()
    sleep(3)
Clear_Error_Flag(10)
set_dtu_run_step(11)
set_dtu_sta(4)
led_communication_on()
ota_dtu_send_version_to_phnix()

# permanent
while true:
    IOT_MQTT_Yield(...)
```

### Beobachtung zu `deviceName`

Der Thread verwendet vor der Credential-Abfrage zunächst den Puffer bei `0x94EDC`. Ist er leer, wird `DmsAPI_get_imei()` auf genau diesen Bereich angewendet. Später kann die HTTP-Geräteabfrage `aliMqtt_set_deviceName()` auf denselben MQTT-DeviceName-Puffer schreiben. Damit ist die IMEI offenbar Fallback/Initialidentität für den Querypfad; der eigentliche MQTT-DeviceName kann danach aus der LinkedGo-Antwort stammen.

## 5. `uart485_thread_handle()` `0x14918`

Rekonstruierter Ablauf:

```text
uart485_init()
set_Error_Flag(8)

do:
    ret = uart485_get_productKey()
    debug ret
    sleep(2)
while aliMqtt_get_productKey()[0] == 0

Clear_Error_Flag(8)

# Device-ID / persistente Statistik angleichen
vergleiche statisch gespeicherte Device-ID mit aktuell gelesener Device-ID
bei Änderung:
    Statistikzähler erhöhen
    persistente Struktur aktualisieren
    static_write_data()

init_line(...)

while true:
    getDevParameter()
```

Damit ist bestätigt: **Nach erfolgreicher ProductKey-/Identitätsphase verlässt der UART-Thread die Initialisierung vollständig und wird zu einem permanent blockierenden/lesenden RS485-Empfangsthread.**

## 6. `uart485_init()`

Statisch eindeutig:

```text
open("/dev/ttyHSL2", O_RDWR | O_NOCTTY)
set_opt(fd, 9600, 8, 'N', 1)
```

Fehler beim Öffnen oder Konfigurieren werden geloggt; der File Descriptor liegt global.

## 7. `uart485_get_productKey()` – Identitätsprotokoll

Die Funktion ist größer als der OTA-Parser und verarbeitet mehrere Antworttypen.

Nachgewiesene Muster:

### Device-ID-Antwort

Es wird unter anderem auf Headerbytes geprüft:

```text
0x63 0x10 0x07 0xD1 ...
```

Danach werden 12 Bytes in `aliMqtt_get_deviceID_buf()` kopiert.

### ProductKey-Antwort

Ein weiterer Pfad prüft:

```text
0x63 0x10 0x00 0xC8 ...
```

mit gültiger Modbus-CRC-Prüfung. Anschließend werden 32 Bytes ab Payload-Offset 7 in den ProductKey-Puffer kopiert.

### Test-/Debugantwort

Die vier ASCII-Bytes

```text
'T' 'E' 'S' 'T'
```

werden separat erkannt und setzen ein internes Testflag.

### Aktiver Request in Step 4

Wenn `get_dtu_run_step()==4`, schreibt die Funktion einen statischen acht Byte langen Request auf den UART und setzt danach Step 5.

Damit ist der Board-ProductKey **nicht** fest im LTE-Binary hinterlegt, sondern wird aktiv vom Mainboard angefordert.

## 8. `UimAPI_thread_handle()` `0x1E7B0`

Der SIM-Thread läuft alle fünf Sekunden:

```text
while true:
    getSimCardStatus(...)

    if status != 1:
        set_Error_Flag(2)
        led_communication_off()
    else:
        Clear_Error_Flag(2)

    if ICCID-Puffer leer:
        get_iccid(...)

    if IMSI-Puffer leer:
        get_imsi(...)

    sleep(5)
```

Damit sind drei getrennte UIM-Daten nachweisbar:

- Kartenstatus
- ICCID
- IMSI

ICCID/IMSI werden nach erfolgreichem Lesen gecacht und danach nicht ständig erneut abgefragt.

## 9. NAS-/Mobilfunkregistrierung

`aliMqtt_handle_thread()` blockiert explizit so lange auf:

```text
NasAPI_get_registration_state() == 1
```

und pollt im Abstand von fünf Sekunden. Solange Registrierung fehlt, bleibt Error Flag 3 gesetzt und die Credential-/MQTT-Sequenz startet nicht.

Der NAS-Bereich besitzt Getter für mindestens:

- Registration State
- LAC (`NasAPI_get_LAC`)
- CELL_ID (`NasAPI_get_CELL_ID`)

Damit ist der NAS-Thread eindeutig für den Mobilfunk-Netzstatus zuständig, nicht für MQTT selbst.

## 10. Gesamtabhängigkeit bis Cloud-Ready

```text
Prozessstart
  |
  +-- AT-Modem-Basistests synchron
  |     CGMM -> CPIN -> CCID -> APN1 -> APN6
  |
  +-- NAS Thread ------------------------------+
  |     wartet/aktualisiert LTE Registration   |
  |                                            v
  +-- UART Thread -> /dev/ttyHSL2 -> Board ProductKey/Device-ID
  |                                            |
  +-- UIM Thread -> SIM Status/ICCID/IMSI      |
  |                                            |
  +-- DMS -> IMEI                              |
                                               v
                                      aliMqtt_handle_thread
                                               |
                                   Registration == 1
                                               |
                                        Device identity
                                               |
                                      Board ProductKey
                                               |
                               LinkedGo Credential Query
                                               |
                                      DeviceSecret da
                                               |
                                        ali_mqtt_init
                                               |
                                      dtu_run_step = 11
                                               |
                                       MQTT regulär aktiv
                                               |
                                      OTA/FOTA darf publishen
```

## 11. Verbindung zur OTA-Analyse

Diese Zerlegung erklärt mehrere bisher nur aus dem OTA-Pfad bekannte Bedingungen:

- `dtu_run_step == 11` bedeutet **nachweislich**: NAS registriert, Identität vorhanden, Cloud-Credentials vorhanden und `ali_mqtt_init()` erfolgreich.
- Der Board-ProductKey wird vor MQTT aktiv über `/dev/ttyHSL2` bezogen.
- `fota_board_thread_handle()` läuft parallel bereits früh, aber `dtu_upgrade_pro()` kann seinen Cloud-Publishpfad erst sinnvoll abschließen, wenn der MQTT-Thread Step 11 erreicht hat.
- `uart485_thread_handle()` verarbeitet nach der Identitätsphase dauerhaft normale sowie OTA-bezogene Boardtelegramme in `getDevParameter()`.

## 12. Neue gesicherte Erkenntnisse

**Bewiesen:**

1. `main()` startet sechs Worker-Threads.
2. AT-Basisinitialisierung läuft vollständig synchron vor diesen Threads.
3. `dtu_run_step` verwendet in diesem Build nur die gesetzten Werte 4, 5, 7 und 11.
4. Step 11 wird exakt nach erfolgreichem `ali_mqtt_init()` gesetzt und bleibt der Betriebszustand.
5. MQTT startet erst nach LTE-Registrierung, IMEI/DeviceName, Board-ProductKey und DeviceSecret.
6. Der ProductKey wird über `/dev/ttyHSL2` vom Mainboard angefordert; 32 Payloadbytes werden übernommen.
7. Eine 12-Byte Device-ID wird ebenfalls über den UART-Pfad empfangen und persistent abgeglichen.
8. Nach erfolgreicher Identitätsinitialisierung läuft `uart485_thread_handle()` permanent in `getDevParameter()`.
9. Der UIM-Thread pollt SIM-Status und liest ICCID/IMSI bei leerem Cache.
10. `aliMqtt_handle_thread()` ruft unmittelbar nach erfolgreichem MQTT-Aufbau `ota_dtu_send_version_to_phnix()` auf.

## 13. Nächste statische Zerlegung

Als nächste Blöcke sind sinnvoll:

- `getDevParameter()` + kompletter normaler RS485-Dispatcher außerhalb OTA
- `NasAPI_thread_handle()` inklusive QMI/NAS-Callbacks und Registration-State-Quelle
- normale MQTT `/user/get` Dispatcher und `/user/update` Telemetrie
- globale `app`-/`statistic_para`-/`sys_para`-Felder und ihre Cross-References
- Fehlerflags und `dtu_sta` Bedeutung
- vollständige Thread-/Callgraph-Tabelle mit allen periodischen Intervallen
