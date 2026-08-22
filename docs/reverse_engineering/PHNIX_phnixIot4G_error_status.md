# PHNIX `phnixIot4G` – ErrorStatus-Bitfeld

Stand: 2026-08-22

Diese Datei dokumentiert das globale Fehlerbitfeld `ErrorStatue` des LTE-DTU. Grundlage ist statische Analyse des ungestrippten ARM-ELF `phnixIot4G`.

## 1. Grundaufbau

Global:

```text
ErrorStatue @ 0x93124
```

Es handelt sich um ein 32-Bit-Bitfeld.

```c
set_Error_Flag(bit):   ErrorStatue |=  (1u << bit)
Clear_Error_Flag(bit): ErrorStatue &= ~(1u << bit)
Get_ErrorStatue():     return ErrorStatue
```

Damit ist die Bitnummer direkt der Funktionsparameter von `set_Error_Flag()` / `Clear_Error_Flag()`.

## 2. Bisher sicher zugeordnete Bits

| Bit | Maske | Beobachteter Kontext | Bedeutung / Beweisgrad |
|---:|---:|---|---|
| 1 | `0x00000002` | `aliMqtt_handle_thread()`: gesetzt solange Device-/Produktidentität noch nicht verfügbar ist; gelöscht sobald der entsprechende globale Puffer befüllt ist | **Geräte-/Cloud-Identitätsinitialisierung unvollständig** – hoch wahrscheinlich |
| 2 | `0x00000004` | `AT_ATE0`, `AT_CPIN`, `AT_ATE1`, `AT_APN1`, `AT_APN6`; zusätzlich `UimAPI_thread_handle()` setzt es bei SIM-Status != 1 und löscht es bei Status 1 | **SIM/AT-Kommunikation bzw. SIM nicht betriebsbereit** – bewiesen als gemeinsames AT/UIM-Fehlerbit |
| 3 | `0x00000008` | `aliMqtt_handle_thread()`: vor der Schleife auf `NasAPI_get_registration_state()==1` gesetzt und danach gelöscht | **Mobilfunk nicht registriert** – bewiesen |
| 4 | `0x00000010` | `led_thread_handle()`: abhängig von einem Messwert, gültig nur bei Bereich 1..31 | **Signalqualitätsfehler / CSQ ungültig** – sehr wahrscheinlich |
| 5 | `0x00000020` | `TimerHandler()`: gesetzt wenn Statistik-/Watchdogzähler `+0x18` > 420; `getDevParameter()` löscht es bei erkanntem UART-Ereignis | **RS485/Mainboard-RX Timeout** – sehr wahrscheinlich |
| 6 | `0x00000040` | `TimerHandler()`: gesetzt bei Zähler `+0x24` >= 420; `getDevParameter()` löscht es bei weiterem gültigen Kommunikationsereignis | **RS485/Mainboard-Kommunikationswatchdog** – sehr wahrscheinlich; genaue Teilsemantik noch offen |
| 8 | `0x00000100` | `uart485_thread_handle()`: direkt nach `uart485_init()` gesetzt; erst gelöscht sobald `aliMqtt_get_productKey()[0] != 0` | **ProductKey/Mainboard-Provisioning fehlt** – bewiesen |
| 9 | `0x00000200` | `aliMqtt_handle_thread()`: gesetzt während auf `deviceSecret`/Credential-Puffer gewartet wird; danach gelöscht | **Cloud-Credentials fehlen** – hoch wahrscheinlich |
| 10 | `0x00000400` | `aliMqtt_handle_thread()`: vor `ali_mqtt_init()` gesetzt und nach erfolgreichem Init gelöscht; zusätzlich in `event_handle()` und `TimerHandler()` als Kommunikationsfehler verwendet | **MQTT/Cloud-Kommunikation gestört** – bewiesen für MQTT-Init, sehr wahrscheinlich allgemeines Cloud-Link-Fehlerbit |
| 12 | `0x00001000` | `TimerHandler()`: abhängig von einem eigenen 420-Tick-Zähler `+0x2C` gesetzt/gelöscht | **weiterer Kommunikations-/Watchdogfehler** – Funktion noch nicht sicher zugeordnet |

Bits 0, 7, 11 sowie 13..31 haben im analysierten Applikationscode bisher keinen direkten `set_Error_Flag()`-/`Clear_Error_Flag()`-Aufrufer.

## 3. Wichtige Aufrufer

### Bit 2 – gemeinsamer SIM/AT-Fehler

Mehrere AT-Routinen verwenden dasselbe Bit:

```text
AT_ATE0()
AT_CPIN()
AT_ATE1()
AT_APN1()
AT_APN6()
```

Bei erfolgreicher erwarteter Antwort wird `Clear_Error_Flag(2)` aufgerufen, bei Fehlschlag nach Retry `set_Error_Flag(2)`.

Auch `UimAPI_thread_handle()` benutzt Bit 2:

```text
UimAPI card_status != 1 -> set bit 2
UimAPI card_status == 1 -> clear bit 2
```

Damit ist Bit 2 kein einzelner „CPIN“-Fehler, sondern ein zusammengefasstes SIM-/AT-Betriebsbereitschaftsbit.

### Bit 3 – Netzregistrierung

`aliMqtt_handle_thread()`:

```text
set_Error_Flag(3)
while NasAPI_get_registration_state() != 1:
    sleep(5)
Clear_Error_Flag(3)
```

Semantik deshalb eindeutig: Mobilfunknetz noch nicht registriert.

### Bit 8 – ProductKey / Mainboard-Provisioning

`uart485_thread_handle()`:

```text
uart485_init()
set_Error_Flag(8)
repeat:
    uart485_get_productKey()
    sleep(2)
until aliMqtt_get_productKey()[0] != 0
Clear_Error_Flag(8)
```

Bit 8 bleibt also gesetzt, solange die DTU keinen ProductKey aus Mainboard/Persistenz erhalten hat.

### Bit 10 – MQTT / Cloud-Link

Im MQTT-Thread:

```text
set_Error_Flag(10)
retry ali_mqtt_init()
Clear_Error_Flag(10)
set_dtu_run_step(11)
```

Darüber hinaus setzt `event_handle()` Bit 10 bei MQTT-Verbindungs-/Eventfehlern und löscht es wieder bei erfolgreichem Kommunikationsereignis. Das spricht klar für ein allgemeines Cloud-/MQTT-Link-Bit.

## 4. Register 500 / `response_DTU_info_request()`

`getDevParameter()` erkennt einen lokalen Modbus-Read auf Register `0x01F4` (dezimal 500) und ruft:

```text
response_DTU_info_request(quantity)
```

Die Funktion liest `Get_ErrorStatue()` und baut daraus ein lokales Modbus-ähnliches Antworttelegramm.

Die ersten Datenbytes werden in dieser Reihenfolge aufgebaut:

```text
byte 0 : 0x63
byte 1 : 0x03
byte 2 : quantity * 2
byte 3 : ErrorStatue bits 15..8
byte 4 : ErrorStatue bits 7..0
byte 5 : ErrorStatue bits 31..24
byte 6 : ErrorStatue bits 23..16
...
CRC
```

Das 32-Bit-Fehlerwort wird also nicht als gewöhnliches little-endian DWORD übertragen, sondern als zwei 16-Bit-Wörter, jeweils big-endian, wobei zuerst das Low-Word und danach das High-Word kommt.

Für die aktuell genutzten Bits 0..12 ist praktisch vor allem das erste 16-Bit-Wort relevant.

## 5. Interpretation für Diagnose

Wenn Register 500 im Feld gelesen wird, können die beobachteten Werte unmittelbar auf die DTU-Subsysteme zurückgeführt werden. Beispiele:

```text
0x0004 -> Bit 2 -> SIM/AT nicht bereit
0x0008 -> Bit 3 -> Mobilfunk nicht registriert
0x0100 -> Bit 8 -> ProductKey/Provisioning fehlt
0x0400 -> Bit 10 -> MQTT/Cloud-Link gestört
```

Mehrere Bits können gleichzeitig gesetzt sein.

## 6. Offene Punkte

Noch genauer zu zerlegen sind:

- Bit 1: exakter Unterschied zu Bit 8/9 in der Credential-/Device-Initialisierung,
- Bit 4: Quelle des 1..31-Werts in `led_thread_handle()`, sehr wahrscheinlich CSQ,
- Bit 5/6/12: exakte Zuordnung der drei 420-Tick-Watchdogs,
- ob Register 500 regulär mehr als zwei Register angefordert wird und welche zusätzlichen Antwortbytes dann semantisch belegt sind.
