# PHNIX `phnixIot4G` – UART-Provisioning und Startup-Reads

Stand: 2026-08-22

Diese Notiz ergänzt die allgemeine `phnixIot4G`-Analyse um die lokal vom DTU erzeugten Mainboard-Abfragen und die Provisionierungsdaten, die vor bzw. während des MQTT-Starts aus `/dev/ttyHSL2` gelesen werden.

## Kurzfazit

Im Binary liegen drei vollständige Modbus-RTU-Requests fest eingebaut:

```text
63 03 00 06 00 01 6C 49
63 03 00 04 00 01 CD 89
63 03 07 D1 00 5A 9C FE
```

Die Analyse der Aufrufer zeigt:

- `0x07D1 / 90 Register` ist Teil der frühen Geräteidentifikation; die 180-Byte-Read-Antwort wird ausgewertet und daraus werden 12 Byte Device-ID übernommen.
- `0x0004 / 1 Register` wird von `uart485_get_device_info()` gesendet. Dieser Request wird nach erfolgreicher MQTT-Initialisierung einmal von `ali_mqtt_init()` ausgelöst.
- `0x0006 / 1 Register` wird im UART-/ProductKey-Startup bzw. von `Check485Statue()` gesendet und dient sehr wahrscheinlich einem lokalen 485-/Status-Handshake. Die exakte Registersemantik ist im LTE-Binary nicht weiter decodiert.

Zusätzlich wird ProductKey nicht über einen dieser FC03-Reads übernommen, sondern aus einem Mainboard-FC10-Frame auf Register `0x00C8` mit 32 Nutzdatenbytes.

---

## 1. Feste Requestframes

### Request A – Register `0x0006`

```text
63 03 00 06 00 01 6C 49
```

Interpretation:

```text
Slave       0x63
Function    0x03
Start       0x0006
Count       0x0001
CRC         6C 49
```

Verwendungen:

- innerhalb `uart485_get_productKey()` (`0x14354`) im allgemeinen Startup-/Retrypfad;
- innerhalb `Check485Statue()` (`0x156B4`), sofern das zugehörige interne Flag noch 0 ist.

Damit ist **bewiesen**, dass Register `0x0006` vom DTU aktiv als lokaler Status-/Handshake-Read verwendet wird. Die konkrete inhaltliche Bedeutung des einzelnen Registers ist im LTE-Programm nicht weiter benannt.

---

## 2. Request B – Register `0x0004`

```text
63 03 00 04 00 01 CD 89
```

Dieser Frame wird ausschließlich von

```text
uart485_get_device_info() 0x15698
```

über `uart485_send_data_to_board(..., 8)` gequeued.

Ein direkter Aufrufer befindet sich in `ali_mqtt_init()` bei `0x1F66C`. Der Call liegt im Erfolgszweig nach MQTT-/Cloudinitialisierung zusammen mit Kommunikationslogging und `aliMqtt_push_error_topic_to_phnix()`.

Damit ist **bewiesen**:

```text
MQTT-Initialisierung erfolgreich
    -> Cloud-/Kommunikationsstatus melden
    -> uart485_get_device_info()
    -> 63 03 00 04 00 01 CD 89
```

Die genaue Bedeutung des einzelnen Registers ist im LTE-Binary nicht weiter
aufgelöst. Ein einmaliger Live-Read auf dem Warmlink-Bus zeigte jedoch die
praktische Wirkung: Das Mainboard sendete danach die acht bekannten
90-Register-Blöcke ab `0x03E9`, `0x0443`, `0x049D`, `0x04F7`, `0x0551`,
`0x05AB`, `0x07D1` und `0x082B`; rund 49 Sekunden später folgte C544 mit der
Boardversion. Damit ist `0x0004` als Trigger eines vollständigen
Device-Info-/Paketzyklus dynamisch belegt. Nach C544 blieben weitere 120
Sekunden ohne OTA-Frames. Details stehen in
[`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md).

---

## 3. Request C – Register `0x07D1`, 90 Register

```text
63 03 07 D1 00 5A 9C FE
```

Interpretation:

```text
Slave       0x63
Function    0x03
Start       0x07D1
Count       0x005A = 90 Register
Response    180 Datenbytes
```

### Auslöser

In `uart485_get_productKey()` wird dieser Request gesendet, wenn

```text
get_dtu_run_step() == 4
```

Direkt danach setzt die Firmware

```text
dtu_run_step = 5
```

Damit gehört der Read eindeutig zur frühen DTU-/Geräteinitialisierung.

### Verarbeitung der Antwort

`uart485_get_productKey()` erkennt eine FC03-Read-Antwort anhand:

```text
byte 0 = 0x63
byte 1 = 0x03
byte 2 = 0xB4 = 180 Datenbytes
```

Wenn Daten vorhanden sind, wird `aliMqtt_get_deviceID_buf()` geholt und **12 Byte ab Antwortoffset +3** dorthin kopiert.

Sinngemäß:

```c
if (rx[0] == 0x63 && rx[1] == 0x03 && rx[2] == 180 && rx[3] != 0) {
    memcpy(deviceID, rx + 3, 12);
}
```

Damit ist **bewiesen**, dass der 90-Register-Read bei `0x07D1` mindestens die Device-ID liefert und dass die ersten 12 Datenbytes vom LTE-Programm als Device-ID interpretiert werden.

Die restlichen 168 Datenbytes dieser Antwort werden in diesem Zweig nicht semantisch decodiert.

---

## 4. Zweiter Device-ID-Pfad über FC10 `0x07D1`

Die gleiche Funktion erkennt zusätzlich einen Frame mit:

```text
byte 0 = 0x63
byte 1 = 0x10
byte 2 = 0x07
byte 3 = 0xD1
```

Wenn das Datenfeld ab Offset +7 nicht leer ist, werden ebenfalls 12 Byte in `deviceID` kopiert.

Damit akzeptiert die Firmware Device-ID offenbar in zwei Formen:

1. als Antwort auf den eigenen FC03-Read `0x07D1/0x005A`,
2. als FC10-Datenframe auf Register `0x07D1`.

Das spricht dafür, dass `0x07D1` ein PHNIX-spezifischer Geräteidentifikations-/Infobereich ist und nicht bloß ein gewöhnliches Betriebsregister.

---

## 5. ProductKey: Register `0x00C8`

Der ProductKey-Pfad ist separat.

`uart485_get_productKey()` erkennt:

```text
63 10 00 C8 ...
```

Nach erfolgreicher CRC-Prüfung holt es den ProductKey-Puffer über `aliMqtt_get_product_buf()` und kopiert:

```text
32 Byte ab rx + 7
```

in diesen Puffer.

Der gleiche Sonderfall ist später nochmals in `getDevParameter()` enthalten: Ist `aliMqtt_get_product_buf()[0] == 0`, werden bei Register `0x00C8` ebenfalls 32 Datenbytes übernommen; existiert bereits ein ProductKey, wird die Meldung nur geloggt und nicht überschrieben.

Damit ist das lokale Provisionierungsformat eindeutig:

```text
Slave       0x63
Function    0x10
Register    0x00C8
Data        ProductKey, 32 Byte ab Frameoffset 7
```

Dieser Frame wird lokal konsumiert und nicht als normale Heizungs-/Statusmeldung zur Cloud gereicht.

---

## 6. Weitere Startup-Erkennung

`uart485_get_productKey()` besitzt außerdem einen ASCII-Testpfad:

```text
'T' 'E' 'S' 'T'
```

Werden diese vier Bytes am Anfang des empfangenen Puffers erkannt, setzt die Funktion ein internes Flag (`0x930E8 = 1`). Dieses Flag wird später von `getDevParameter()` verwendet, um einen lokalen Diagnose-/DTU-Informationsstring mit DTU-Hardware-/Softwareversion, IMEI und ICCID über den UART auszugeben.

Dieser Pfad ist ein lokaler Fertigungs-/Hardwaretest und gehört nicht zum normalen MQTT-Protokoll.

---

## 7. Zusammenhang mit `dtu_run_step`

Der `0x07D1`-Read liefert eine direkte Verbindung zwischen UART- und MQTT-State-Machine:

```text
dtu_run_step == 4
    -> sende 63 03 07 D1 00 5A 9C FE
    -> set_dtu_run_step(5)
    -> Antwort liefert Device-ID
```

Andere Pfade in derselben Funktion senden `0x0006` wiederholt, bis die für den weiteren Start benötigten lokalen Zustände verfügbar sind.

Damit ist `uart485_get_productKey()` trotz seines Namens funktional breiter: Es sammelt **ProductKey, Device-ID und Board-/485-Startupstatus**.

---

## 8. Relevanz für Work

Für die Mainboard-Analyse sind folgende Register jetzt als DTU-spezifische Servicebereiche identifiziert:

| Register | Zugriff | LTE-Bedeutung |
|---:|---|---|
| `0x0004` | FC03 Read 1 | `uart485_get_device_info()` nach MQTT-Init; live als Trigger des Geräteinfo-/Paketzyklus bis C544 bestätigt |
| `0x0006` | FC03 Read 1 | UART-/485-Status/Handshake, genaue Semantik offen |
| `0x00C8` | FC10 Daten | ProductKey, 32 Byte |
| `0x01F4` | FC03 Read | lokaler DTU-Info-/Errorstatus-Request |
| `0x07D1` | FC03 Read 90 / FC10 Daten | Device-ID-/Geräteinfobereich; erste 12 Datenbytes = Device-ID |

Diese Register sollten bei der Mainboard-Firmware gezielt auf Schreib-/Lesehandler und Datenquellen zurückverfolgt werden. Besonders `0x07D1` ist interessant, weil der LTE-Code nur 12 der angeforderten 180 Datenbytes nutzt – die übrigen Daten könnten weitere bislang unbekannte Geräteinformationen enthalten.

## 9. Beweisgrad

### Bewiesen

- exakte drei eingebettete FC03-Requests und CRCs;
- `0x0004` wird von `uart485_get_device_info()` gesendet und nach erfolgreicher MQTT-Initialisierung ausgelöst;
- ein einzelner Live-Read `0x0004` löste acht Geräteinfoblöcke und später C544 aus, aber während 120 Sekunden Nachbeobachtung keinen OTA-Start;
- `0x07D1/90` wird bei `dtu_run_step==4` gesendet und setzt danach Step 5;
- FC03-Antwort mit 180 Datenbytes liefert die ersten 12 Bytes als Device-ID;
- FC10 `0x07D1` kann ebenfalls 12 Byte Device-ID liefern;
- FC10 `0x00C8` liefert 32 Byte ProductKey;
- `TEST` aktiviert einen lokalen Diagnosepfad.

### Offen

- Bedeutung des einzelnen Registerwerts `0x0004` und exakte Semantik von `0x0006` auf Mainboardseite;
- Bedeutung der verbleibenden 168 Datenbytes des `0x07D1`-Readblocks;
- ob `0x07D1` im Mainboard eine zusammenhängende Infostruktur oder mehrere logisch unabhängige Register enthält.
