# PHNIX `phnixIot4G` – QMI/DSI Datenpfad-Analyse

Stand: 2026-08-22

Diese Ergänzung untersucht gezielt, ob `phnixIot4G` den mobilen IP-Datenpfad selbst über Qualcomm DSI/WDS aufbaut oder nur NAS/UIM/DMS für Status/Identität nutzt.

## Kurzfazit

Der entscheidende Befund ist negativ, aber wichtig:

**`phnixIot4G` ruft die DSI-Datenpfad-API nicht direkt auf.**

Obwohl `libdsi_netctrl.so.0`, `libqdi.so.0`, `libqmi.so.1`, `libdsutils.so.1` und weitere Qualcomm-Bibliotheken als `DT_NEEDED` im ELF stehen, besitzt das Executable keine undefinierten/importierten `dsi_*`, `qdi_*`, `netmgr_*` oder WDS-Funktionen.

Direkt importierte QMI-CCI-Funktionen des Programms sind nur:

```text
qmi_client_init_instance
qmi_client_send_msg_sync
qmi_client_message_decode
qmi_client_release
```

sowie die Service-Objekt-Getter für DMS/UIM/NAS.

Damit trennt dieser Build klar zwischen:

```text
Control plane im Prozess:
  DMS -> IMEI
  UIM -> SIM/Card/ICCID/IMSI
  NAS -> Registrierung/RAT/Signal

Data plane:
  nicht durch direkten dsi_start_data_call()/WDS-Aufruf aus phnixIot4G aufgebaut
```

## 1. `libdsi_netctrl` ist vorhanden, aber vom Executable nicht referenziert

Das ELF listet direkt unter anderem:

```text
libdsi_netctrl.so.0
libdsutils.so.1
libqmiservices.so.1
libqmi_cci.so.1
libqmi_common_so.so.1
libqmi.so.1
libqdi.so.0
```

Die Symboltabelle von `phnixIot4G` enthält jedoch keine undefinierten Symbole wie:

```text
dsi_init
dsi_get_data_srvc_hndl
dsi_set_data_call_param
dsi_start_data_call
dsi_stop_data_call
dsi_get_device_name
qdi_wds_start_nw_if
netmgr_client_register
```

Das ist statisch eindeutig: ein normaler direkter Aufruf dieser APIs aus dem Executable findet nicht statt.

## 2. Was `libdsi_netctrl` selbst könnte

Das aus dem Original-Runtimepaket stammende `libdsi_netctrl.so.0` exportiert die erwartete Qualcomm-Datenpfad-API, darunter:

```text
dsi_init
dsi_get_data_srvc_hndl
dsi_set_data_call_param
dsi_start_data_call
dsi_stop_data_call
dsi_get_device_name
dsi_get_ip_addr
```

Intern hängt die Bibliothek an QDI/WDS/Netmgr, zum Beispiel:

```text
qdi_wds_start_nw_if
qdi_wds_stop_nw_if
qdi_get_qmi_wds_handle
netmgr_client_register
netmgr_client_send_user_cmd
qmi_client_wds_init_instance
```

Die Runtime besitzt damit den vollständigen Qualcomm-Datenstack. Nur `phnixIot4G` benutzt dessen öffentliche DSI-API in diesem Build nicht direkt.

## 3. APN-Konfiguration erfolgt per AT

Vor dem Start der QMI-Threads ruft `main()` nacheinander auf:

```text
AT_GetCGMM()
AT_CPIN()
AT_GetCCID()
AT_APN1()
AT_APN6()
```

`AT_APN1()` und `AT_APN6()` konfigurieren PDP-Kontexte per `AT+CGDCONT` auf dem AT-Port `/dev/smd8`.

Im Binary sind mehrere APN-Profile enthalten. Für den beobachteten SIM-Modus wird unter anderem verwendet:

```text
AT+CGDCONT=1,"IPV4V6","orange.m2m.spec"
AT+CGDCONT=6,"IPV4V6","orange.m2m.spec"
```

Daneben existieren Profile wie `acell.90164`, `cuiot` sowie ein leerer APN. Die Auswahl hängt von einem internen SIMMODE-Wert und teilweise dem ICCID-Präfix ab.

Wichtig: `AT_CGATT()`, `AT_GetCGREG()` und `AT_GetCREG()` existieren zwar als Funktionen im Binary, es wurde im untersuchten Executable aber kein produktiver Aufrufer gefunden. Sie wirken wie ältere/alternative SDK-Demofunktionen.

## 4. Keine eigene Data-Call-State-Machine in `main()`

Nach `AT_APN1()`/`AT_APN6()` startet `main()`:

```text
DmsAPI_init()
NasAPI_init()
NasAPI_thread_handle()
UimAPI_init()
UimAPI_thread_handle()
uart485_thread_handle()
aliMqtt_handle_thread()
fota_board_thread_handle()
```

Es folgt kein `dsi_init()` und kein `dsi_start_data_call()`.

Der MQTT-Thread wartet auf NAS-Registrierung und beginnt danach Credential-/MQTT-Initialisierung. Die eigentliche TCP-Verbindung wird anschließend durch den eingebetteten Aliyun-Netzwerkstack über Standard-Linux-Sockets hergestellt (`getaddrinfo`, `socket`, `connect`). libcurl benutzt ebenso den normalen Kernel-Netzwerkstack.

Daraus folgt:

```text
phnixIot4G erwartet beim MQTT/HTTP-Start bereits einen funktionierenden Kernel-IP-Pfad.
```

## 5. Wahrscheinliche Plattformarchitektur

Die statischen Befunde passen zu folgender Architektur des SIM7600-Linuxsystems:

```text
phnixIot4G
  |
  +-- AT /dev/smd8
  |     -> SIM/PDP-Kontext konfigurieren
  |
  +-- QMI CCI
  |     -> DMS/UIM/NAS Control Plane
  |
  +-- Linux sockets
        -> MQTT/HTTP
        -> vorhandenes rmnet-/Kernel-IP-Interface

Qualcomm Plattformdienste / Daemons / Libraries
  -> QMUX/QMI/WDS
  -> DSI/QDI/Netmgr
  -> rmnet Interface und Routing
```

Der letzte Block ist Plattforminfrastruktur und wird nicht durch eine eigene DSI-State-Machine im Applikationscode gesteuert.

## 6. Erklärung der VM-Beobachtung

Im Offline-QEMU-Lauf erscheint nach erfolgreicher AT-Sequenz unter anderem:

```text
/dev/diag
/data/qmux_client_socket ...
QMUX-/QMI-Verbindungsversuche
```

Das passt zu DMS/UIM/NAS bzw. deren Qualcomm-Abhängigkeiten. Es beweist nicht, dass `phnixIot4G` selbst einen DSI-Datacall startet.

Für eine vollständige Emulation des Originalprogramms sind deshalb zwei Ebenen zu unterscheiden:

1. **QMI Control Plane emulieren oder umgehen**, damit DMS/UIM/NAS erfolgreich werden und NAS Registration State 1 erreicht.
2. **Einen normalen Linux-IP-Pfad bereitstellen**, auf dem Aliyun MQTT/libcurl arbeiten können.

Eine Emulation der kompletten DSI/QDI/WDS-Data-Call-API ist für das Executable selbst nach aktuellem Stand nicht erforderlich.

## 7. Relevanz für Work

Für die parallele Analyse gelten damit folgende belastbare Aussagen:

```text
- DMS/UIM/NAS sind direkt von phnixIot4G verwendete QMI-Dienste.
- NAS Registration ist ein hartes Startup-Gate.
- DSI/WDS wird vom Executable nicht direkt aufgerufen.
- APN Context 1 und 6 werden per AT+CGDCONT gesetzt.
- MQTT/HTTP nutzen anschließend normale Linux-Sockets.
- rmnet/Data-Call-Aufbau liegt sehr wahrscheinlich in der SIMCom/Qualcomm-Plattformebene, nicht in der PHNIX-Applikationslogik.
```

## 8. Beweisgrad

### Bewiesen

- keine `dsi_*`/`qdi_*`/`netmgr_*`-Imports im Executable;
- DSI-Bibliothek selbst enthält vollständige Start/Stop-Data-Call-Funktionen;
- `main()` ruft AT-APN1/APN6 und danach DMS/NAS/UIM auf, aber keine DSI-Funktion;
- MQTT-Netzwerkstack verwendet Standard-Socketpfad;
- `AT_CGATT`, `AT_GetCGREG`, `AT_GetCREG` haben im untersuchten Build keinen gefundenen produktiven Aufrufer.

### Sehr wahrscheinlich

- rmnet/Data-Call wird von der Plattform/Daemons außerhalb von `phnixIot4G` bereitgestellt bzw. automatisch verwaltet;
- `libdsi_netctrl` ist durch Build-/Linkabhängigkeiten oder Plattform-SDK-Abhängigkeiten im NEEDED-Set verblieben, obwohl der Applikationscode seine API nicht direkt nutzt.
