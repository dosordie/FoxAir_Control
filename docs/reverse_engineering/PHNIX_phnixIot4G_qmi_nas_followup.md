# PHNIX `phnixIot4G` – QMI/NAS Follow-up und RS485-Watchdogs

Stand: 2026-08-22

Diese Datei ergänzt `PHNIX_phnixIot4G_qmi_nas.md` und `PHNIX_phnixIot4G_error_status.md` um die weitere statische Zerlegung. Grundlage ist ausschließlich Offline-Analyse des bereitgestellten ELF.

## 1. Produktiver NAS-Zustand kommt aus Polling, nicht aus dem Callback

`NasAPI_thread_handle()` bei `0x1E23C` läuft dauerhaft:

```text
loop:
    get_NetworkType(&global_NetworkType)
    nas_get_serving_system(&global_serving_system)
    sleep(5)
```

`get_NetworkType()` bei `0x21A94` sendet synchron NAS Message-ID `0x24`, Requestgröße 1, Responsegröße `0x5E4` (1508 Byte), Timeout 10000 ms. Bei Erfolg werden 1040 Byte in den produktiven Cache bei `0x981B4` übernommen.

Die Getter lesen daraus:

```text
+0x00 registration_state
+0x04 cs_attach_state
+0x08 ps_attach_state
+0x0C selected_network
+0x10 radio_if_len
+0x14... radio_if[]
```

`aliMqtt_handle_thread()` wartet auf `NasAPI_get_registration_state()==1`, also konkret auf `*(uint32_t *)0x981B4 == 1`.

### Konsequenz

Der für den DTU-Startup maßgebliche Registration-State wird alle fünf Sekunden synchron gepollt. Er hängt nicht davon ab, dass eine NAS-Indication empfangen wurde.

## 2. `process_simcom_ind_message()` ist in diesem Build nur ein Debug-Stub

`process_simcom_ind_message()` bei `0xA3CC` loggt die Eventnummer und kehrt zurück. Es schreibt keinen der produktiven NAS-Caches und treibt keine Zustandsmaschine weiter.

Damit ist der asynchrone Pfad

```text
nas_ind_cb()
 -> network_info_type
 -> process_simcom_ind_message(SIMCOM_EVENT_NETWORK_IND, ...)
```

für den Applikationszustand dieses Builds praktisch Diagnose/Logging.

## 3. Präzisere Bewertung der NAS-Indications

| msg_id | Struktur | Ergebnis im untersuchten Build |
|---:|---|---|
| `0x24` | `nas_serving_system_ind_msg_v01` | Registration/Attach/RAT wird dekodiert und an Debug-Eventpfad gegeben; kein produktiver Cache-Write gefunden |
| `0x4E` | `nas_sys_info_ind_msg_v01` | LTE/HDR/CDMA/WCDMA/GSM/TDSCDMA Service-Domain/Status wird ausgewertet; überwiegend Diagnose |
| `0x51` | `nas_sig_info_ind_msg_v01` | Signalinfo dekodiert/geloggt; produktiver Signallevel wird zusätzlich über Sync-Query geholt |
| `0x66` | `nas_rf_band_info_ind_msg_v01` | Nachricht erkannt/geloggt; keine relevante DTU-Zustandsänderung |

## 4. Error-Bit 6: kein Traffic von Slave `0x63`

Der zugehörige Timer liegt im Statistikbereich bei Offset `+0x24`.

`getDevParameter()` setzt diesen Timer bereits zurück, sobald ein empfangener Frame mit Slaveadresse `0x63` beginnt – noch vor erfolgreicher CRC-Auswertung.

Nach ungefähr 420 Sekunden ohne solches Ereignis setzt `TimerHandler()` Error-Bit 6.

Daraus folgt:

```text
Error-Bit 6 = seit >420 s kein sichtbarer RS485-Verkehr von Mainboard-Slave 0x63
```

## 5. Error-Bit 12: kein CRC-gültiges Mainboardtelegramm

Der Timer liegt bei Offset `+0x2C`.

Er wird erst nach erfolgreicher `Check_crc()`-Prüfung zurückgesetzt. Nach mehr als ungefähr 420 Sekunden ohne CRC-gültigen Frame setzt `TimerHandler()` Error-Bit 12.

```text
Error-Bit 12 = seit >420 s kein CRC-gültiges Mainboardtelegramm
```

Das unterscheidet Bit 12 sauber von Bit 6: Bit 6 sieht bereits rohe `0x63`-Aktivität, Bit 12 verlangt ein gültiges Telegramm.

## 6. Error-Bit 5 und `Check485Statue()`

Der dritte Watchdogtimer liegt bei Offset `+0x18`.

Nach ungefähr 300 Sekunden Inaktivität ruft `TimerHandler()` periodisch `Check485Statue()` auf; ab ungefähr 420 Sekunden wird Error-Bit 5 gesetzt.

`Check485Statue()` bei `0x156B4` sendet exakt:

```text
63 03 00 06 00 01 6C 49
```

also Modbus-Read:

```text
slave    0x63
function 0x03
register 0x0006
quantity 1
```

Dieser Timer wird unter anderem bei höherwertigen lokal erkannten Mainboard-Ereignissen zurückgesetzt, zum Beispiel beim ProductKey-/Provisioningpfad `63 10 00 C8 ...` und bei lokal erfolgreich von `unpack_mcu_modbus()` behandelten Frames.

Deshalb ist Bit 5 kein einfacher physikalischer RX-Watchdog. Es beschreibt eher das Ausbleiben eines erwarteten Mainboard-Service-/Provisioning-/Heartbeat-Ereignisses; `0x0006` dient dabei als aktive Alive-Probe.

## 7. Fester Read `0x0004`

`uart485_get_device_info()` bei `0x15698` sendet:

```text
63 03 00 04 00 01 CD 89
```

also FC03 auf Register `0x0004`, ein Register.

Der Aufruf erfolgt nach erfolgreicher vollständiger MQTT-Initialisierung. Die Antwort auf `0x0004` besitzt keinen lokalen Spezialhandler und läuft bei gültiger CRC über den normalen Binärpfad:

```text
Mainboard response 0x0004
 -> getDevParameter()
 -> ali_mqtt_push_msg(raw_frame, len)
 -> /user/update
```

Damit ist `0x0004` ein cloud-relevanter Board-/Device-Info-Trigger.

Ein einmaliger Live-Read am realen Warmlink-Bus bestätigte am 23. August 2026
einen breiteren Ablauf als einen isolierten Ein-Register-Response: Das Mainboard
sendete anschließend die acht 90-Register-Blöcke `03E9`, `0443`, `049D`, `04F7`,
`0551`, `05AB`, `07D1`, `082B` und rund 49 Sekunden später ein vollständiges
C544. Das LTE-Modem bestätigte C544 mit C37B/status 7. Eine 120-sekündige
Nachbeobachtung zeigte keinen OTA-Start. Details und Frames:
[`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md).

## 8. Fester Read `0x0006`

`0x0006` wird ausschließlich von `Check485Statue()` als Watchdogprobe abgefragt. Eine gültige Antwort besitzt ebenfalls keinen eigenen Decoder und wird deshalb als Rohframe auf `/user/update` publiziert.

## 9. Kompakte Übergabe an parallele Mainboard-Analyse

```text
QMI/NAS:
- produktiver Registration-State = 5-s Sync-Poll NAS msg 0x24
- produktiver Cache = 0x981B4
- nas_ind_cb() ist in diesem Build überwiegend Diagnose
- process_simcom_ind_message() = Debug-Stub

RS485:
- 0x0004: Device-info-/Paketzyklus-Trigger nach erfolgreichem MQTT init; live folgten acht Paketblöcke und später C544
- 0x0006: Check485Statue-Watchdogprobe; Antwort roh zur Cloud

Error:
- Bit 6  = >420 s kein Frame mit Slave 0x63
- Bit 12 = >420 s kein CRC-gültiges Mainboardframe
- Bit 5  = >420 s kein erwartetes höherwertiges Mainboard-Serviceevent; aktive Probe 0x0006
```
