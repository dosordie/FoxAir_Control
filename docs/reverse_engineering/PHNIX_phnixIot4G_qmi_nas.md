# PHNIX `phnixIot4G` – QMI/NAS/DMS/UIM statische Analyse

Stand: 2026-08-22

Grundlage: statische Analyse des bereitgestellten, ungestrippten ARM-ELF `phnixIot4G` inklusive Symboltabelle und partieller DWARF-Debugdaten. Keine Live-QMI-Kommandos wurden gesendet.

## Kurzfazit

`phnixIot4G` verwendet drei Qualcomm-QMI-Dienste direkt:

- DMS (Device Management Service) für IMEI,
- UIM (User Identity Module) für SIM-Status, ICCID und IMSI,
- NAS (Network Access Service) für Registrierung, Serving-System, RAT/Radio-Interface und Signalwerte.

Die drei öffentlichen Wrapper `DmsAPI_init()`, `NasAPI_init()` und `UimAPI_init()` sind dünn. Die eigentliche QMI-Logik liegt in `dms_init()`, `uim_init()`, `nas_init()` und den jeweiligen Query-/Callbackfunktionen.

Der NAS-Pfad ist für die DTU-Zustandsmaschine besonders wichtig: `aliMqtt_handle_thread()` wartet auf `NasAPI_get_registration_state()==1`, bevor die Cloud-/Credential-/MQTT-Initialisierung fortgesetzt wird.

---

## 1. Importierte QMI-CCI-Funktionen

Über PLT/GOT eindeutig aufgelöst:

| PLT | Import |
|---:|---|
| `0x9D68` | `qmi_client_release` |
| `0x9D74` | `dms_get_service_object_internal_v01` |
| `0x9D80` | `qmi_client_init_instance` |
| `0x9D8C` | `qmi_client_send_msg_sync` |
| `0x9DA4` | `uim_get_service_object_internal_v01` |
| `0x9DB0` | `qmi_client_message_decode` |
| `0x9DBC` | `nas_get_service_object_internal_v01` |

Die Firmware nutzt damit die Qualcomm QMI Client CCI API direkt und nicht etwa AT-Kommandos für die eigentliche Netzregistrierung/Serving-System-Auswertung.

---

## 2. `DmsAPI_init()` / DMS

### Wrapper `DmsAPI_init()` – `0x1E8B8`

Ablauf:

```text
DmsAPI_init()
  -> dms_init()
  -> memset(IMSI/IMEI cache, 0, 32)
  -> get_imei(cache)
```

Der 32-Byte-IMEI-Cache liegt bei `0x93688`.

`DmsAPI_get_imei_cache()` liefert direkt `0x93688` zurück.

### `dms_init()` – `0x20340`

Wenn bereits ein DMS-Client existiert, Rückgabe 0.

Andernfalls:

```text
dms_get_service_object_internal_v01(1, 57, 6)
  -> service object

qmi_client_init_instance(
    service_object,
    0xFFFF,          // instance ANY
    NULL,            // kein DMS indication callback
    NULL,
    &dms_os_params,
    4,
    &dms_svc_client
)
```

Bei Fehler wird mehrfach mit Sleep/Retry versucht; bei endgültigem Fehler `-1`.

### `get_imei()` – `0x20440`

`get_imei()` verwendet `qmi_client_send_msg_sync()` mit:

- Message-ID `0x25` (dezimal 37),
- Requestgröße 1 Byte / leerer Request,
- Responsepuffer 368 Byte,
- Timeout `10000` ms.

Die DWARF-Daten und die enthaltenen Typnamen zeigen, dass der Response `dms_get_device_serial_numbers_resp_msg_v01` ist. Aus dem Response wird das Feld `imei_valid` geprüft und bei Erfolg die IMEI kopiert.

**Bewiesen:** DMS wird in diesem Programm praktisch nur als IMEI-Quelle benutzt. Es existieren zwar `dms_set_operating_mode()` und `dms_get_operating_mode()`, aber der normale Startup-Wrapper ruft sie nicht auf.

---

## 3. `UimAPI_init()` / UIM

### Wrapper `UimAPI_init()` – `0x1E584`

Ablauf:

```text
UimAPI_init()
  -> uim_init()
  -> ICCID cache leeren (22 Byte)
  -> get_iccid()
  -> IMSI cache leeren (17 Byte)
  -> get_imsi()
```

Caches:

- ICCID: `0x9365C`, 22 Byte
- IMSI: `0x93674`, 17 Byte
- SIM-Statusstruktur: `0x98AB0`

### `uim_init()` – `0x20A78`

Analog zu DMS:

```text
uim_get_service_object_internal_v01(1, 54, 6)

qmi_client_init_instance(
    service_object,
    0xFFFF,
    NULL,
    NULL,
    &uim_os_params,
    4,
    &uim_svc_client
)
```

Kein UIM-Indication-Callback wird registriert; der Status wird gepollt.

### `UimAPI_thread_handle()` – `0x1E7B0`

Endlosschleife mit 5 s Pause:

```text
getSimCardStatus(&UimAPIStatus)

if card_status != 1:
    set_Error_Flag(2)
    Kommunikations-LED aus
else:
    Clear_Error_Flag(2)

wenn ICCID-Cache leer:
    get_iccid()

wenn IMSI-Cache leer:
    get_imsi()

sleep(5)
```

Damit ist **Error-Bit 2 eindeutig SIM/UIM-Status**: es wird gesetzt, solange `card_status != 1` ist.

### `getSimCardStatus()` – `0x20B9C`

QMI-Sync-Request:

- Message-ID `0x2F` (dezimal 47),
- Responsegröße 9088 Byte,
- Timeout 10000 ms.

Die Funktion extrahiert aus der großen UIM-Card-Statusantwort mindestens:

- Card state,
- Application type,
- Application state,
- PIN state,
- weitere Statusfelder.

Diese Werte landen in der globalen `UimAPIStatus`-Struktur bei `0x98AB0`.

### `get_iccid()` – `0x20D1C`

QMI-Sync-Request:

- Message-ID `0x47` (dezimal 71),
- Responsegröße 156 Byte,
- Timeout 10000 ms.

Die Funktion wandelt die ICCID aus dem QMI-Response in die ASCII-Darstellung des 22-Byte-Caches um.

### `get_imsi()` – `0x20EA4`

Hier ist die Semantik besonders klar: die Funktion baut einen UIM-Read-Transparent-Request auf und verwendet File-ID `0x6F07` (EF_IMSI).

QMI-Sync-Request:

- Message-ID `0x20` (dezimal 32),
- Requestgröße 76 Byte,
- Responsegröße `0x142C`,
- Timeout 10000 ms.

Die zurückgelieferten IMSI-BCD-Daten werden in ASCII umgesetzt und im 17-Byte-Cache abgelegt.

---

## 4. `NasAPI_init()` / NAS

### Wrapper `NasAPI_init()` – `0x1E038`

```text
NasAPI_init()
  -> nas_init()
  -> nur DebugTrace des Rückgabewerts
```

### `nas_init()` – `0x21720`

NAS unterscheidet sich wesentlich von DMS/UIM, weil hier ein Indication-Callback registriert wird.

Serviceobject:

```text
nas_get_service_object_internal_v01(1, 158, 6)
```

Danach:

```text
qmi_client_init_instance(
    nas_service_object,
    0xFFFF,          // ANY instance
    nas_ind_cb,      // Callback 0x210B0
    NULL,
    &nas_os_params,
    4,
    &nas_svc_client
)
```

Nach erfolgreichem Client-Init wird `nas_ind_register()` aufgerufen.

### `nas_ind_register()` – `0x2166C`

Die Funktion erzeugt eine 69-Byte-`nas_indication_register_req_msg_v01`-Struktur, setzt zwei Enable-Bytes auf 1 und sendet synchron:

```text
qmi_client_send_msg_sync(
    nas_client,
    0x0003,
    &nas_ind_req_msg,
    69,
    &nas_ind_resp_msg,
    8,
    10000
)
```

Message-ID `3` ist damit der NAS-Indication-Register-Request dieses Builds.

---

## 5. NAS-Indication-Callback `nas_ind_cb()` – `0x210B0`

Dank DWARF sind die lokalen Strukturen im Callback namentlich bekannt:

```text
nas_sys_info_ind_msg_v01       sys_info_ind
nas_rf_band_info_ind_msg_v01   band_info_ind
nas_serving_system_ind_msg_v01 serving_sys_info_ind
nas_sig_info_ind_msg_v01       sig_info_ind
```

Zusätzlich existieren lokale Variablen für:

- `registration_state`
- `ps_attach_state`
- Service-Domain/Service-Status für LTE, HDR, CDMA, WCDMA, GSM, TDSCDMA
- Roamingstatus
- `network_info_type`

Der Dispatcher akzeptiert exakt vier NAS-Indication-Message-IDs:

| msg_id | dekodierte Struktur | Verhalten |
|---:|---|---|
| `0x24` | `nas_serving_system_ind_msg_v01` | Serving-System/Registrierung/PS-Attach auswerten und SIMCom-Network-Event erzeugen |
| `0x4E` | `nas_sys_info_ind_msg_v01` | technologiespezifische Service-Domain/Service-Status auswerten |
| `0x51` | `nas_sig_info_ind_msg_v01` | Signalinfo dekodieren |
| `0x66` | `nas_rf_band_info_ind_msg_v01` | RF-Band-Indication wird erkannt/logged; in diesem Callback praktisch keine weitere DTU-Logik |

Andere Message-IDs werden nur als unbekannt geloggt.

### 5.1 `0x24` – Serving-System-Indication

Der Callback dekodiert mit:

```text
qmi_client_message_decode(..., msg_id=0x24, ...)
```

Danach werden unter anderem `registration_state` und `ps_attach_state` entnommen. Der Debugstring lautet:

```text
SERVING_SYSTEM_IND: reg_state[%d], ps_satat[%d]
```

Aus den Daten wird eine `network_info_type`-Struktur aufgebaut und anschließend:

```text
process_simcom_ind_message(SIMCOM_EVENT_NETWORK_IND, &network_info)
```

aufgerufen.

Die DWARF-Enumdaten bestätigen:

```text
SIMCOM_EVENT_NETWORK_IND = 4
```

Damit ist der Pfad statisch geschlossen:

```text
QMI NAS serving-system indication
  -> nas_ind_cb()
  -> network_info_type
  -> process_simcom_ind_message(event 4)
  -> höherer SIMCom-/DTU-Eventpfad
```

### 5.2 `0x4E` – System-Info-Indication

Diese Nachricht enthält technologiespezifische Serviceinformationen. Der Callback prüft nacheinander Valid-Flags/Statusfelder für:

- LTE
- HDR
- CDMA
- WCDMA
- GSM
- TDSCDMA

und extrahiert jeweils `srv_domain` und `srv_status`.

Der Code bevorzugt gültige/in-service RAT-Informationen und bildet daraus den internen Netzstatus.

### 5.3 `0x51` – Signal-Info-Indication

Dekodierung in `nas_sig_info_ind_msg_v01` (DWARF-Strukturgröße 56 Byte).

Die Struktur enthält Valid-Flags und Messwerte für mehrere RATs, unter anderem:

- GSM signal info
- WCDMA signal info
- LTE signal info
- TDSCDMA signal info
- RSCP

Der Callback selbst nutzt diese Indication nicht als einzigen Signalstärke-Cache; die öffentlich verwendete Prozent-/Levelberechnung läuft zusätzlich über den synchronen Query `get_SignalStrength()`.

### 5.4 `0x66` – RF-Band-Info-Indication

Der Binary-String lautet ausdrücklich:

```text
Receive QMI_NAS_RF_BAND_INFO_IND_V01
```

Die Nachricht wird erkannt; im untersuchten Callback folgt danach keine relevante DTU-Zustandsänderung.

---

## 6. `NasAPI_thread_handle()` – Polling trotz Indications

NAS benutzt **beides**: Indications und periodische Sync-Queries.

Thread `0x1E23C`:

```text
loop forever:
    get_NetworkType(&global_NetworkType)
    nas_get_serving_system(&global_serving_system)
    sleep(5)
```

Globale Daten:

- NetworkType-Struktur ab `0x981B4`
- Serving-System-Puffer ab `0x97BD0`

Der Thread aktualisiert also alle 5 Sekunden den aktuellen Netzstatus unabhängig von den asynchronen NAS-Indications.

---

## 7. NAS-API-Cache und Getter

`NasAPI_show_NetworkType()` zeigt die Struktur bei `0x981B4` an. Aus den Gettern ist das Layout klar:

| Offset | Getter | Bedeutung |
|---:|---|---|
| `+0x00` | `NasAPI_get_registration_state()` | Registration state |
| `+0x04` | `NasAPI_get_cs_attach_state()` | CS attach state |
| `+0x08` | `NasAPI_get_ps_attach_state()` | PS attach state |
| `+0x0C` | `NasAPI_get_selected_network()` | selected network |
| `+0x10` | `NasAPI_get_radio_if_len()` | Anzahl Radio-Interfaces |
| danach | `NasAPI_get_radio_if()` | Radio-interface array, Basis `0x981C8` |

Wichtigster Verbraucher ist `aliMqtt_handle_thread()`:

```text
set_Error_Flag(3)
while NasAPI_get_registration_state() != 1:
    sleep(5)
Clear_Error_Flag(3)
```

**Error-Bit 3 ist damit eindeutig: Mobilfunk/NAS nicht registriert.**

---

## 8. Signalstärke: AT-CSQ und QMI-NAS sind getrennt

Das Programm besitzt zwei parallele Signalpfade.

### AT-Pfad

`led_thread_handle()` ruft `AT_GetCSQ()` auf. Ist der CSQ-Wert nicht im Bereich 1..31, wird Error-Bit 4 gesetzt.

Damit ist:

```text
Error-Bit 4 = ungültige/fehlende AT+CSQ-Signalstärke
```

Die drei Signal-LED-Stufen werden grob aus CSQ gebildet:

- >19: high
- >14: middle
- >0: weak

### QMI-NAS-Pfad

`NasAPI_get_SignalStrength()` ruft `get_SignalStrength()` auf.

Der Sync-Request verwendet:

- NAS Message-ID `0x20` (dezimal 32),
- Requestgröße 4,
- Responsegröße 324,
- Timeout 10000 ms.

Die Requestmaske wird auf `0x81` gesetzt.

Der Code skaliert die gelieferten dBm-/RSSI-Werte auf einen Prozent-/Levelwert 0..100 und speichert zusätzlich einen Modus/Validitätswert (`NasAPIMode`, `NasAPILevel`).

Damit ist wichtig: **die sichtbare Signal-LED basiert auf AT+CSQ, die NAS/QMI-API besitzt aber parallel eine detailliertere Signalabfrage.**

---

## 9. Rolle von DMS/UIM/NAS im Gesamtstartup

```text
main()
  -> AT-Basisinitialisierung
  -> DmsAPI_init()
       -> QMI DMS client
       -> IMEI
  -> NasAPI_init()
       -> QMI NAS client + nas_ind_cb
       -> indication registration
  -> start NasAPI_thread_handle()
  -> UimAPI_init()
       -> QMI UIM client
       -> ICCID + IMSI
  -> start UimAPI_thread_handle()
  -> UART/MQTT/FOTA worker
```

Der MQTT-Worker wartet anschließend explizit auf NAS-Registrierung:

```text
NasAPI_get_registration_state() == 1
```

Erst danach folgen Board-/Cloud-Identifier, Credentials und MQTT.

Damit ist die praktische Abhängigkeit:

```text
QMI NAS registriert
    ↓
Cloud-/MQTT-Startup erlaubt
```

---

## 10. Relevanz für die VM-Emulation

Die statische Analyse erklärt den bisherigen Lauf sehr gut:

Nach erfolgreicher AT-Sequenz initialisiert `phnixIot4G` DMS/NAS/UIM über Qualcomm QMI. Dafür erwartet die Originalplattform funktionierende QMI-CCI-/QMUX-Dienste und lokale Qualcomm-Sockets/Devices.

Ein reines AT-Modem-PTY reicht deshalb nicht aus, um den Originalprozess bis zum normalen MQTT-Betrieb zu bringen. Der fehlende QMI-Unterbau ist ein echter nächster Plattform-Layer und kein zufälliger Nebeneffekt.

Für eine sichere Laborreproduktion ist deshalb sinnvoller, die QMI-API kontrolliert zu stubben/emulieren, statt `/dev/diag` oder reale Qualcomm-Geräte blind durchzureichen.

---

## 11. Beweisgrad

### Bewiesen aus Binary/DWARF

- DMS/UIM/NAS Serviceobject-Aufrufe und Versionsargumente `(1,57,6)`, `(1,54,6)`, `(1,158,6)`;
- `qmi_client_init_instance()` für alle drei Dienste;
- DMS/UIM ohne Indication-Callback, NAS mit `nas_ind_cb`;
- NAS Indication Registration über Message-ID 3;
- NAS Callback Message-IDs `0x24`, `0x4E`, `0x51`, `0x66`;
- zugehörige DWARF-Strukturtypen;
- Serving-System-Indication erzeugt `SIMCOM_EVENT_NETWORK_IND`;
- NAS-Thread pollt NetworkType/ServingSystem alle 5 s;
- MQTT-Startup wartet auf `registration_state == 1`;
- DMS liefert IMEI;
- UIM liefert Card Status, ICCID und IMSI;
- IMSI wird über EF_IMSI `0x6F07` gelesen;
- Error-Bit 2 = SIM/UIM nicht bereit;
- Error-Bit 3 = NAS nicht registriert;
- Error-Bit 4 = AT+CSQ ungültig/außerhalb 1..31.

### Noch offen / nächste Zerlegung

- exakte Semantik aller `nas_sys_info_ind` RAT-Prioritätszweige in lesbarem Pseudocode;
- vollständige Zuordnung der QMI-Responsefelder in `getSimCardStatus()`;
- genaue Bedeutung der verbleibenden Error-Bits 5, 6 und 12;
- Rolle der festen Mainboard-Reads `0x0004` und `0x0006`;
- ob die NAS Signal-Info-Indication außerhalb des Callbacks noch in weitere Statistiken eingeht.
