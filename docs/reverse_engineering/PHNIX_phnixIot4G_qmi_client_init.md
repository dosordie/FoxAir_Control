# PHNIX `phnixIot4G` – QMI Client-Init und NAS-Indication-Register

Stand: 2026-08-22

Grundlage: statische Analyse von `dms_init()`, `uim_init()`, `nas_init()` und `nas_ind_register()` im ungestrippten ARM-ELF.

## 1. Gemeinsames Init-Muster

DMS, UIM und NAS verwenden dasselbe Grundmuster:

```text
wenn Clienthandle bereits != NULL:
    return 0

service_object = *_get_service_object_internal_v01(...)
wenn NULL:
    return -1

qmi_client_init_instance(...)
bei erstem Fehler:
    sleep(1)
    ein zweiter Versuch
bei erneutem Fehler:
    return -1
```

Damit gibt es **maximal zwei `qmi_client_init_instance()`-Versuche** pro Init-Aufruf. Zwischen erstem und zweitem Versuch liegt eine Sekunde.

Die drei Wrapper selbst besitzen darüber hinaus je nach aufrufender Zustandsmaschine weitere Retrymöglichkeiten; hier beschrieben ist nur die jeweilige `*_init()`-Funktion.

---

## 2. DMS `dms_init()` – `0x20340`

Serviceobject:

```text
dms_get_service_object_internal_v01(1, 57, 6)
```

Clientinit:

```text
qmi_client_init_instance(
    service_object,
    0xFFFF,       // QMI_CLIENT_INSTANCE_ANY
    NULL,         // kein indication callback
    NULL,
    &os_params,
    4,
    &client_handle
)
```

DMS arbeitet im PHNIX-Code damit rein synchron. `DmsAPI_init()` liest anschließend per Message `0x25` die IMEI.

---

## 3. UIM `uim_init()` – `0x20A78`

Serviceobject:

```text
uim_get_service_object_internal_v01(1, 54, 6)
```

Clientinit ist strukturell identisch zu DMS:

```text
instance = 0xFFFF
indication callback = NULL
callback data = NULL
```

Auch UIM wird vollständig per synchronen Queries gepollt; es existiert im PHNIX-Code kein UIM-Indication-Callback.

---

## 4. NAS `nas_init()` – `0x21720`

Serviceobject:

```text
nas_get_service_object_internal_v01(1, 158, 6)
```

NAS registriert als einziger der drei Dienste einen Callback:

```text
qmi_client_init_instance(
    service_object,
    0xFFFF,
    nas_ind_cb,       // 0x210B0
    NULL,
    &os_params,
    4,
    &client_handle
)
```

Auch hier maximal zwei Initversuche, mit 1 s Pause vor dem zweiten.

Nach erfolgreichem Clientinit folgt zwingend:

```text
nas_ind_register()
```

Schlägt diese Registrierung fehl, wird der NAS-Client sofort per `qmi_client_release()` freigegeben und `nas_init()` liefert `-1`.

---

## 5. `nas_ind_register()` – `0x2166C`

QMI-Request:

```text
msg_id = 0x0003
request type = nas_indication_register_req_msg_v01
request size = 69
response size = 8
timeout = 10000 ms
```

Die 69-Byte-Requeststruktur wird vorher vollständig genullt. Danach setzt der PHNIX-Code **nur die ersten zwei Bytes**:

```text
offset +0 = 1
offset +1 = 1
```

DWARF löst diese Felder eindeutig auf:

```text
+0 reg_sys_sel_pref_valid = 1
+1 reg_sys_sel_pref       = 1
```

Alle anderen Enable-/Valid-Felder der umfangreichen `nas_indication_register_req_msg_v01` bleiben 0.

### Wichtige Konsequenz

Der PHNIX-Code fordert über `nas_ind_register()` explizit nur:

```text
System Selection Preference indications
```

an.

Er setzt hier **nicht** explizit die vielen anderen Registerflags für Serving-System-, RF-Band-, Signal- oder ähnliche Indications.

Dass `nas_ind_cb()` trotzdem Handler für `0x24`, `0x4E`, `0x51` und `0x66` enthält, bedeutet daher nicht, dass dieser Build all diese Indications aktiv über den Registerrequest anfordert. Einige können modemseitig standardmäßig/anderweitig geliefert werden oder der Callback stammt aus einer allgemeineren SIMCom/Qualcomm-Codebasis.

Das stärkt die frühere Erkenntnis, dass die produktive PHNIX-Netzlogik primär auf den synchronen 5-s-Polls (`get_NetworkType()`/`nas_get_serving_system()`) beruht.

---

## 6. Fehlerbehandlung

### Serviceobject fehlt

Ist `*_get_service_object_internal_v01()` NULL:

```text
return -1
```

### `qmi_client_init_instance()` schlägt fehl

```text
Versuch 1 -> Fehler
sleep(1)
Versuch 2 -> Fehler
return -1
```

### NAS Indication Register schlägt fehl

```text
qmi_client_release(nas_client)
nas_client = NULL
return -1
```

DMS/UIM besitzen diesen zusätzlichen Register-Schritt nicht.

---

## 7. Relevanz für VM/QMI-Emulation

Ein minimaler QMI-Unterbau muss für die drei Serviceobjects jeweils eine discoverbare `ANY`-Instanz anbieten, sodass `qmi_client_init_instance(..., 0xFFFF, ...)` erfolgreich wird.

Für NAS reicht nicht nur Service-Discovery: unmittelbar nach dem Client-Connect erwartet `phnixIot4G` zusätzlich einen erfolgreichen synchronen Response auf Message-ID `0x03` (`NAS Indication Register`).

Minimaler NAS-Startup aus Sicht der App:

```text
1. NAS Serviceobject/Instance discoverbar
2. qmi_client_init_instance erfolgreich
3. NAS msg 0x03 -> QMI success
4. später NAS msg 0x24 -> QMI success + registration_state=1
```

DMS:

```text
1. DMS discoverbar
2. Client init erfolgreich
3. msg 0x25 -> gültige IMEI
```

UIM:

```text
1. UIM discoverbar
2. Client init erfolgreich
3. msg 0x2F -> SIM present
4. msg 0x47 -> ICCID (für ruhigen Pollingbetrieb)
5. msg 0x20 -> IMSI (für ruhigen Pollingbetrieb)
```

---

## 8. Neue Beweisgrade

### Bewiesen

- DMS/UIM/NAS verwenden `QMI_CLIENT_INSTANCE_ANY` (`0xFFFF`).
- DMS und UIM registrieren keinen Indication-Callback.
- NAS Callback ist `nas_ind_cb()` bei `0x210B0`.
- Jede `*_init()`-Routine versucht `qmi_client_init_instance()` höchstens zweimal, mit einer Sekunde Pause vor Versuch 2.
- `nas_ind_register()` setzt ausschließlich `reg_sys_sel_pref_valid=1` und `reg_sys_sel_pref=1`.
- NAS-Init gilt erst nach erfolgreichem Message-`0x03`-Registerrequest als erfolgreich.

### Interpretation

Der umfangreiche NAS-Indication-Dispatcher ist allgemeiner als der tatsächlich registrierte PHNIX-Betrieb. Für die Rekonstruktion des realen Steuerpfades sind deshalb die synchronen Queries höher zu gewichten als die bloße Existenz von Callbackzweigen.
