# PHNIX `phnixIot4G` – minimale QMI-Responses für Startup/VM-Lab

Stand: 2026-08-22

Grundlage: statische Analyse des ungestrippten ARM-ELF `phnixIot4G` inklusive DWARF-Typinformationen. Ziel ist zu dokumentieren, welche QMI-Responsefelder die Applikation **tatsächlich auswertet**. Es wurden keine Live-QMI-Kommandos gesendet.

## Kurzfazit

Für den PHNIX-Startup sind die QMI-Dienste funktional sehr schmal:

- **DMS** muss eine gültige IMEI liefern.
- **UIM** muss einen präsent/benutzbar wirkenden SIM-Status liefern; ICCID/IMSI werden zusätzlich gelesen und gecacht.
- **NAS** muss im gepollten Serving-System `registration_state = 1` (`NAS_REGISTERED_V01`) liefern. Genau dieses Feld ist die harte Schranke vor Cloud/MQTT.

Viele weitere Felder der großen Qualcomm-Strukturen werden von `phnixIot4G` nicht benötigt.

---

## 1. NAS – `get_NetworkType()` ist die entscheidende Startup-Abfrage

Funktion: `get_NetworkType()` bei `0x21A94`.

QMI-Aufruf:

```text
service: NAS
msg_id: 0x24 (36) = Get Serving System
request size: 1 Byte (placeholder/leer)
response size: 0x5E4 = 1508 Byte
timeout: 10000 ms
```

Nach erfolgreichem `qmi_client_send_msg_sync()` prüft die Funktion:

```text
response.resp.result == 0
```

und kopiert anschließend **exakt 1040 Byte** ab Response-Offset `+8` in den Zielcache.

DWARF bestätigt: diese 1040 Byte sind `nas_serving_system_type_v01`.

### Relevantes Layout `nas_serving_system_type_v01`

| Offset | Feld | Typ / Bedeutung |
|---:|---|---|
| `+0x00` | `registration_state` | `nas_registration_state_enum_v01` |
| `+0x04` | `cs_attach_state` | CS attach |
| `+0x08` | `ps_attach_state` | PS attach |
| `+0x0C` | `selected_network` | 3GPP/3GPP2 |
| `+0x10` | `radio_if_len` | Länge Radio-IF-Liste |
| `+0x14` | `radio_if[]` | RAT-Liste |

Enumwerte für `registration_state`:

```text
0 = NAS_NOT_REGISTERED_V01
1 = NAS_REGISTERED_V01
2 = NAS_NOT_REGISTERED_SEARCHING_V01
3 = NAS_REGISTRATION_DENIED_V01
4 = NAS_REGISTRATION_UNKNOWN_V01
```

### Harte Startup-Bedingung

`aliMqtt_handle_thread()` benutzt anschließend nur:

```text
NasAPI_get_registration_state()
```

und wartet bis der Wert **exakt 1** ist.

Damit ist für eine minimale Lab-NAS-Response bewiesen:

```text
QMI result = SUCCESS
nas_serving_system_type.registration_state = 1
```

reicht aus, um die Registrierungsschranke der Applikation zu passieren.

`cs_attach_state`, `ps_attach_state`, `selected_network` und `radio_if[]` werden zwar gecacht und über Getter angeboten, sind aber für diese Startup-Schleife nicht erforderlich.

---

## 2. DMS – minimale IMEI-Response

Funktion: `get_imei()` bei `0x20440`.

QMI-Aufruf:

```text
service: DMS
msg_id: 0x25 (37) = Get Device Serial Numbers
request size: 1 Byte
response size: 368 Byte
timeout: 10000 ms
```

DWARF-Typ:

```text
dms_get_device_serial_numbers_resp_msg_v01
```

Relevante Strukturfelder:

| Offset | Feld |
|---:|---|
| `+0x00` | `resp` (`qmi_response_type_v01`) |
| `+0x2A` | `imei_valid` |
| `+0x2B` | `imei[33]` |

Die Funktion prüft in dieser Reihenfolge:

```text
qmi_client_send_msg_sync() == 0
resp.result == 0
imei_valid != 0
```

Erst dann wird `imei` mit `strcpy()` in den Applikationscache kopiert.

### Minimale DMS-Semantik

Für die Applikation müssen daher nur folgende Inhalte sinnvoll sein:

```text
resp.result = QMI_RESULT_SUCCESS
imei_valid = 1
imei = NUL-terminierter ASCII-IMEI-String
```

MEID, ESN und IMEISV werden von `DmsAPI_init()` nicht benötigt.

---

## 3. UIM – Card Status

Funktion: `getSimCardStatus()` bei `0x20B9C`.

QMI-Aufruf:

```text
service: UIM
msg_id: 0x2F (47) = Get Card Status
request size: 2 Byte
response size: 9088 Byte
timeout: 10000 ms
```

DWARF-Typ:

```text
uim_get_card_status_resp_msg_v01
```

Top-Level-Layout:

| Offset | Feld |
|---:|---|
| `+0x00` | `resp` |
| `+0x08` | `card_status_valid` |
| `+0x0C` | `card_status` (`uim_card_status_type_v01`) |

Die Funktion akzeptiert den Response nur bei:

```text
qmi call == 0
resp.result == 0
card_status_valid != 0
```

Danach sucht sie innerhalb von `card_status.card_info[]` eine geeignete Karten-/Applikationskombination. Explizit wird dabei nach einer App mit

```text
app_type == 2
```

gesucht. DWARF bestätigt:

```text
UIM_APP_TYPE_USIM_V01 = 2
```

Aus der ausgewählten Karte/App erzeugt `getSimCardStatus()` die kleine interne Applikationsstruktur `SimCard_Status_type`:

```c
struct SimCard_Status_type {
    uint32_t card_status;
    uint32_t app_type;
    uint32_t app_state;
    uim_pin_info_type_v01 pin;
};
```

Wichtige Enumwerte:

```text
UIM_CARD_STATE_ABSENT  = 0
UIM_CARD_STATE_PRESENT = 1
UIM_CARD_STATE_ERROR   = 2

UIM_APP_TYPE_SIM  = 1
UIM_APP_TYPE_USIM = 2

UIM_APP_STATE_READY = 7

UIM_PIN_STATE_ENABLED_VERIFIED = 2
UIM_PIN_STATE_DISABLED         = 3
```

### Was der PHNIX-Thread wirklich prüft

`UimAPI_thread_handle()` testet anschließend nur:

```text
UimAPIStatus.card_status == 1
```

Also:

```text
card_status = UIM_CARD_STATE_PRESENT
```

ist die harte Bedingung zum Löschen von Error-Bit 2.

Für eine realistische minimale Response empfiehlt sich zusätzlich:

```text
card_status_valid = 1
card_info_len >= 1
card_info[0].card_state = PRESENT
card_info[0].app_info_len >= 1
card_info[0].app_info[0].app_type = USIM (2)
card_info[0].app_info[0].app_state = READY (7)
pin1.pin_state = ENABLED_VERIFIED (2) oder DISABLED (3)
```

Die Applikation verlangt im UIM-Thread aber nur, dass der daraus extrahierte `card_status` gleich 1 wird.

---

## 4. UIM – ICCID kommt über `Get Slots Status`, nicht über Card Status

Funktion: `get_iccid()` bei `0x20D1C`.

QMI-Aufruf:

```text
service: UIM
msg_id: 0x47 (71) = Get Slots Status
request size: 1 Byte
response size: 156 Byte
timeout: 10000 ms
```

DWARF-Typ:

```text
uim_get_slots_status_resp_msg_v01
```

Layout:

| Offset | Feld |
|---:|---|
| `+0x00` | `resp` |
| `+0x08` | `physical_slot_status_valid` |
| `+0x0C` | `physical_slot_status_len` |
| `+0x10` | `physical_slot_status[0]` |

Erster Slot (`uim_physical_slot_status_type_v01`):

| Slot-Offset | Feld |
|---:|---|
| `+0x00` | `physical_card_status` |
| `+0x04` | `physical_slot_state` |
| `+0x08` | `logical_slot` |
| `+0x0C` | `iccid_len` |
| `+0x10` | `iccid[]` |

Die Funktion fordert explizit:

```text
resp.result == 0
physical_slot_status_valid != 0
physical_slot_status_len != 0
physical_slot_status[0].iccid_len != 0
```

Danach wird jedes ICCID-Byte nibbleweise in ASCII umgewandelt: Low-Nibble zuerst, dann High-Nibble.

### Minimale ICCID-Response

```text
resp.result = SUCCESS
physical_slot_status_valid = 1
physical_slot_status_len = 1
physical_slot_status[0].iccid_len > 0
physical_slot_status[0].iccid = gültige BCD-Bytes
```

ICCID ist für den MQTT-Registrierungs-Gate nicht direkt kritisch; der UIM-Thread versucht sie aber alle 5 Sekunden erneut zu lesen, solange der ICCID-Cache leer bleibt.

---

## 5. UIM – IMSI über EF_IMSI (`0x6F07`)

Funktion: `get_imsi()` bei `0x20EA4`.

Request:

```text
service: UIM
msg_id: 0x20 (32) = Read Transparent
request size: 76 Byte
response size: 0x142C
timeout: 10000 ms
```

Im Request ist statisch gesetzt:

```text
file_id = 0x6F07   // EF_IMSI
```

Der Response wird nur akzeptiert, wenn:

```text
qmi call == 0
resp.result == 0
read_result_len > 0
```

Die zurückgelieferten Bytes werden BCD/nibbleweise in ASCII umgesetzt und in den IMSI-Cache kopiert.

Auch IMSI wird im UIM-Thread nur nachgeladen, solange der Cache leer ist; eine fehlende IMSI blockiert die harte NAS-Registrierungsschleife nicht direkt.

---

## 6. Startup-kritische Minimalmatrix

| Dienst | Request | Was `phnixIot4G` minimal braucht | Startup-Relevanz |
|---|---|---|---|
| DMS | `0x25` Serial Numbers | `result=0`, `imei_valid=1`, ASCII-IMEI | hoch: Geräte-/Cloudidentität |
| UIM | `0x2F` Card Status | `result=0`, `card_status_valid=1`, extrahierbare Karte mit `card_state=1` | hoch: Error-Bit 2 / SIM ready |
| UIM | `0x47` Slots Status | mindestens 1 Slot + ICCID | mittel; wird periodisch nachgeladen |
| UIM | `0x20` Read Transparent EF_IMSI | erfolgreicher IMSI-Inhalt | mittel; wird periodisch nachgeladen |
| NAS | `0x24` Serving System | `result=0`, `registration_state=1` | **kritisch: harte Schranke vor Cloud/MQTT** |

---

## 7. Konsequenz für das VM-Lab

Für ein minimalistisches Offline-Lab muss nicht das gesamte Qualcomm-Modemmodell nachgebaut werden. Aus Sicht von `phnixIot4G` reichen semantisch wenige Antworten:

```text
DMS:
  IMEI gültig

UIM:
  SIM present
  optional ICCID/IMSI, damit Polling zur Ruhe kommt

NAS:
  registration_state = REGISTERED
```

Danach kann die Applikation ihren eigenen Cloud-/MQTT-Code erreichen, sofern zusätzlich ein normales Linux-Netzinterface sowie die erwarteten PHNIX-Geräte-/Credentialdaten vorhanden sind.

Wichtig: Das beschreibt die **Applikationssemantik nach erfolgreichem QMI-Transport**. Ein Emulator muss zusätzlich die von Qualcomm QMI-CCI/QMUX erwartete Transport-/Service-Discovery-Schicht korrekt bedienen; rohe Strukturbytes an einem beliebigen Socket reichen nicht automatisch aus.

---

## 8. Neue Beweisgrade

### Bewiesen

- `get_NetworkType()` kopiert genau `nas_serving_system_type_v01` (1040 Byte) aus `nas_get_serving_system_resp_msg_v01` in den Applikationscache.
- `registration_state` liegt am Anfang dieser 1040-Byte-Struktur.
- `NAS_REGISTERED_V01` hat Enumwert `1`.
- `aliMqtt_handle_thread()` wartet exakt auf diesen Wert 1.
- DMS IMEI liegt bei Responseoffset `+0x2B`, mit `imei_valid` bei `+0x2A`.
- UIM Card Status sucht explizit nach `app_type == 2` = USIM.
- `UimAPI_thread_handle()` betrachtet `card_status == 1` = PRESENT als SIM ready.
- `get_iccid()` nutzt `uim_get_slots_status_resp_msg_v01` und liest ICCID aus dem ersten physischen Slot.
- `get_imsi()` liest EF_IMSI `0x6F07` per UIM Read Transparent.

### Noch offen

- welche minimale QMUX-/QMI-CCI-Service-Discovery-Emulation nötig ist, bevor diese semantischen Responses überhaupt beim Client ankommen;
- ob `DmsAPI_get_imei_cache()` bei fehlender IMEI später einen alternativen Cloudpfad zulässt (bisher kein belastbarer Hinweis);
- ob real auf dem SIM7600 eine spezielle UIM-Appauswahl nötig ist, wenn mehrere Apps/Slots gemeldet werden.
