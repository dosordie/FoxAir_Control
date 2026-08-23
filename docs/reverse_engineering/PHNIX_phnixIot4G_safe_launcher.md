# PHNIX `phnixIot4G` – Safe-Launcher: Supervisor, DOG, OTA_INFO, Terminalstatus und Hook-Grenzen

Stand: 2026-08-23

Grundlage: statische Analyse des bereitgestellten ungestrippten ARM-ELF `phnixIot4G` (Build-ID `af4dcae12639bedce833ee5efa5da009777b6319`), Abgleich mit den dokumentierten Offline-VM-Ergebnissen und der Mainboard-Firmware V3.3. Es wurde keine Cloudkommunikation und keine reale OTA-Übertragung an die Wärmepumpe ausgeführt.

Diese Datei fokussiert nur die für einen kontrollierten lokalen Mainboard-OTA-Launcher noch relevanten Randbedingungen. Die allgemeine OTA-State-Machine wird nicht erneut beschrieben.

---

## 1. Externer Supervisor von `phnixIot4G`

### Sicher aus dem ELF belegt

Der DTU-Self-Updatepfad ersetzt das laufende Binary und beendet anschließend den Prozess hart:

```sh
chmod a+x /data/phnixIot4G_OTA
mv /data/phnixIot4G_OTA /data/phnixIot4G
killall -9 phnixIot4G
```

Im ELF ist kein eigener `fork()`-/`vfork()`-/`daemon()`-/`exec*()`-Restartpfad importiert. Damit kann sich `phnixIot4G` nach `SIGKILL` nicht selbst neu starten.

**Folgerung:** Ein externer Init-/Supervisorprozess muss den Dienst starten und nach seinem Ende erneut hochbringen, sofern der Updatepfad im Feld funktionieren soll.

### Noch nicht aus dem ELF bestimmbar

Der konkrete Supervisorname bzw. das Init-Skript ist nicht Bestandteil dieses ELF. Aus dem Binary allein ist daher nicht seriös ableitbar, ob der Prozess über BusyBox `init`, `/etc/inittab`, `/etc/init.d`, einen vendor-spezifischen Daemon oder einen anderen Watcher gestartet wird.

### Read-only Prüfung auf dem realen LTE-Modem

```sh
PID=$(pidof phnixIot4G)
echo "PID=$PID"
cat /proc/$PID/status | grep -E '^(Name|Pid|PPid):'
tr '\0' ' ' < /proc/$PID/cmdline; echo
readlink /proc/$PID/exe

PPID=$(awk '/^PPid:/{print $2}' /proc/$PID/status)
echo "PPID=$PPID"
cat /proc/$PPID/status | grep -E '^(Name|Pid|PPid):'
tr '\0' ' ' < /proc/$PPID/cmdline; echo

tr '\0' ' ' < /proc/1/cmdline; echo
```

Zusätzlich nur lesend:

```sh
grep -R "phnixIot4G" /etc/inittab /etc/init.d /etc/rc* /etc/init 2>/dev/null
ps -ef | grep '[p]hnixIot4G'
```

Vor einem echten OTA sollte damit geklärt sein, ob der Prozess nach Crash automatisch wiederkommt, wie lange dies dauert und ob ein Debugger-Stop vom Supervisor als Fehler interpretiert wird.

**Bewertung:** externe Restart-Abhängigkeit bestätigt; konkrete Supervisor-Identität bleibt bis zum PPID/RootFS-Readout offen.

---

## 2. GPIO 50 / `Reset_All_DOG()`

Funktion:

```text
Reset_All_DOG() @ 0x0000B400
```

Pseudocode:

```c
void Reset_All_DOG(void)
{
    EAT_WriteGpio(50, 1);
    sleep(2);
    EAT_WriteGpio(50, 0);
}
```

`initHardware()` initialisiert GPIO 50 zuvor über:

```text
EAT_InitGpio(50, 0, 0)
```

Im analysierten Build existieren 28 direkte Aufrufer. Sie liegen ausschließlich in den älteren `AT_*`-Transaktionsfunktionen, u. a. `AT_ATE0`, `AT_CPIN`, `AT_APN1`, `AT_APN6`, `AT_GetCSQ`, `AT_GetCGREG`, `AT_GetCREG`, `AT_GetCGSN`, `AT_GetCGMM`, `AT_GetCCID`, `AT_CGATT`, mehreren HTTP-AT-Funktionen und den alten MQTT-AT-Funktionen.

Die AT-Schnittstelle wird über `/dev/smd8` verwendet. Das Programm läuft also auf dem Linux/AP-Teil des Modems und spricht den Modem-Subsystemteil über diese interne SMD-Schnittstelle an.

### Negativbefund für Mainboard-OTA

Im Mainboard-OTA-Pfad

```text
HTTP/libcurl -> C350 -> C357 -> C5A8/C371 -> C36E/C37B
```

existiert kein direkter Aufruf von `Reset_All_DOG()`.

Damit wird GPIO 50 während eines rund zwölfminütigen C5A8-Transfers nicht durch die OTA-State-Machine periodisch gepulst.

Ein unmittelbarer Reset des gesamten Linux-LTE-Modems ist sehr unwahrscheinlich: `Reset_All_DOG()` wird vor vielen normalen AT-Transaktionen aufgerufen; ein Reset des Linux/AP-Prozessors würde den aufrufenden Prozess selbst zerstören.

Sicher ist damit:

```text
kein Self-Reboot des Linux-Prozesses
kein klassischer /dev/watchdog-Feed innerhalb des OTA-Threads
```

Offen bleibt die elektrische Bedeutung von GPIO 50. Die Funktionsbezeichnung `Reset_All_DOG` ist ein Indiz, aber kein Schaltplanbeweis. Vor dem realen OTA sollte deshalb geprüft werden, ob GPIO 50 im normalen Dauerbetrieb auch durch andere Prozesse/Kernelpfade getoggelt wird.

---

## 3. `/data/phnixIot_device_OTA_INFO` – exaktes Validierungsformat

Globale Struktur:

```text
sys_para @ 0x00098820
Größe    = 0xDC = 220 Byte
Datei    = /data/phnixIot_device_OTA_INFO
```

### CRC-Feld und Datenbereich

`sys_flash_erase_write() @ 0x1A6D8` berechnet:

```c
crc = GetCrc16(((uint8_t *)&sys_para) + 4, 216);
sys_para.crc_field = crc;
fwrite(&sys_para, 220, 1, fp);
fsync(fileno(fp));
```

Damit gilt exakt:

```text
0x00..0x03  32-Bit little-endian CRC-Feld
             gültiger CRC16 in den unteren 16 Bit
             obere 16 Bit beim Originalwriter 0

CRC-Bereich  0x04..0xDB inklusive
Länge        216 Byte
```

`sys_read_para() @ 0x1A7D0` liest 220 Byte und vergleicht den gespeicherten 32-Bit-Wert mit `GetCrc16(file + 4, 216)`.

### CRC-Algorithmus

`GetCrc16() @ 0x1A618` verwendet:

```text
Initialwert : 0xFFFF
reflektierte Tabelle
Polynom     : 0x8408
Update      : crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
Final XOR   : 0xFFFF
```

Die ersten Tabellenwerte im ELF sind:

```text
0000 1189 2312 329B 4624 57AD 6536 74BF ...
```

Das ist CRC-16/X-25 / CRC-16/IBM-SDLC (`poly=0x1021`, reflected `0x8408`, `init=0xFFFF`, `refin/refout=true`, `xorout=0xFFFF`).

### OTA-relevante Felder

| Offset | Länge | Bedeutung | Encoding |
|---:|---:|---|---|
| `0x00` | 4 | CRC-Feld | LE `uint32`, CRC16 im low word |
| `0x1C` | 6 | gespeicherter DTU-Versionsstring (`sys_get_ver()`) | ASCII |
| `0xA5` | 33 | Board-Firmware-MD5 | 32 ASCII-Hex + NUL |
| `0xC6` | 9 | Board OTA SoftwareCode | max. 8 Zeichen + NUL |
| `0xCF` | 5 | Board OTA SoftwareVersion | max. 4 Zeichen + NUL |
| `0xD4` | 4 | bestätigter Firmware-Dateioffset | LE `uint32` |
| `0xD8` | 4 | Board-Firmware-Dateilänge | LE `uint32` |

Alle übrigen Bytes gehören zur allgemeinen `sys_para`-Struktur und müssen unverändert in die CRC einbezogen werden.

### Launcher-Validator

```python
def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
            crc &= 0xFFFF
    return crc ^ 0xFFFF

raw = open('/data/phnixIot_device_OTA_INFO', 'rb').read()
assert len(raw) == 220
stored = int.from_bytes(raw[0:4], 'little')
calc = crc16_x25(raw[4:220])
assert stored == calc

md5_ascii = raw[0xA5:0xC6].split(b'\0',1)[0].decode()
software_code = raw[0xC6:0xCF].split(b'\0',1)[0].decode()
software_ver  = raw[0xCF:0xD4].split(b'\0',1)[0].decode()
offset = int.from_bytes(raw[0xD4:0xD8], 'little')
length = int.from_bytes(raw[0xD8:0xDC], 'little')
```

Validieren sollte der Launcher mindestens nach Download+Metadatenpersistenz vor dem ersten C5A8, nach jeder C371-bedingten Offsetänderung und vor einem bewusst ausgelösten Resume/Restart-Test.

Stopbedingungen:

```text
CRC ungültig
MD5/SoftwareCode/Version/Length unerwartet
Offset > Length
Offset sinkt unerwartet
C371 ackB=2, aber Offset != Length
```

---

## 4. Terminale Boardantworten und Phasen-Watchdog

### C371 – Blockfortschritt, noch kein finales Updateergebnis

Handler:

```text
board_updata_bin_handle() @ 0x1B72C
```

Nach Session-/Blockprüfung werden zwei relevante `ackB`-Werte verarbeitet:

```text
ackB = 1
  normaler bestätigter Datenblock
  -> Offset += blockSize
  -> sys_set_board_file_offset(new_offset)

ackB = 2
  letzter Block bestätigt
  -> Offset = file_len
  -> sys_set_board_file_offset(file_len)
```

`ackB=2` bedeutet nur: LTE->Board-Datentransfer vollständig angenommen. Es beweist noch nicht erfolgreiche MD5-Prüfung, Promotion oder Start der neuen Firmware.

### C36E Statusmatrix

Handler:

```text
board_is_allow_upg_handle() @ 0x1BA04
```

| C36E | Bedeutung | LTE-Reaktion | Launcher |
|---:|---|---|---|
| `0` | kein Upgrade / abgelehnt / identischer oder inkompatibler Kandidat | neutraler Vorhandshake | kein Update gestartet |
| `1` | C350 akzeptiert | C357-Retrybudget aktiv | C350-Phase erfolgreich |
| `2` | C357/Metadaten akzeptiert | frischer/Resume-Übergang Richtung Transfer | C357-Phase erfolgreich |
| `3` | Staging-/MD5-Prüfung erfolgreich | `C37B status 3` | Datenphase erfolgreich, Promotion noch nicht final |
| `4` | Daten-/MD5-/Stagingfehler | `C37B status 4`, Offset zurück, Recovery/Cancel | Fehler |
| `5` | OTA/Promotion erfolgreich | `C37B status 5`, Offset/Length löschen, Step 12->5 | **finaler Erfolg** |
| `6` | Upgrade-/Promotionfehler | `C37B status 6`, Offset zurück, Recovery/Cancel | **finaler Fehler** |

C37B ist für Status 3..6 das LTE->Board-ACK. Die Mainboard-Firmware besitzt für ausbleibendes C37B einen eigenen Retrymechanismus.

### Sicherer Cancel

Handler:

```text
board_recv_cancel_upgrade_handle() @ 0x1B51C
```

Erfolgreiche Boardbestätigung:

```text
C36C status = 1
```

Bei aktivem Cancel-Pending löscht der LTE-Dienst dann u. a.:

```text
app+0x02 cancel_pending = 0
app+0x58 cancel_retry_budget = 0
```

Launcher-Kriterium für bestätigten Cancel:

```text
C36A tatsächlich gesendet
AND C36C status 1 empfangen
AND LTE cancel_pending gelöscht
```

Ein bloßes Ausbleiben weiterer C5A8-Frames ist kein ausreichender Cancelbeweis.

### Externe Phasen-Watchdogs

```text
P1: nach C350 -> C36E 1 erwartet
P2: nach C357 -> C36E 2 erwartet
P3: während C5A8 -> CRC-validierter persistenter Offset muss fortschreiten
P4: nach C371 ackB=2 -> C36E 3 oder 4 erwartet
P5: nach C36E3/C37B3 -> C36E 5 oder 6 erwartet
P6: nach Cancel C36A -> C36C status 1 erwartet
```

Während P3 gilt nur der bestätigte `OTA_INFO`-Offset als Fortschritt, nicht ein gesendeter Blockzähler.

---

## 5. Minimaler Laufzeit-Hook für MQTT-Publishes

Zentrale Funktion:

```text
ali_mqtt_push_OTA_msg() @ 0x1F9B0
```

Ein globales `return 0` ist nicht empfohlen.

Nur während eines bewusst gestarteten lokalen Mainboard-OTA dürfen lokal als erfolgreich bestätigt werden:

```text
0023  Mainboard Upgrade-/Allow-Report
0053  Mainboard OTA Erfolg
0083  Mainboard OTA Fehler
0113  Rollback-/Initialization-Ergebnis – nur bei bewusst aktiviertem Rollback
```

Nicht erforderlich:

```text
0043  Downloadprogress
0043  Transferprogress
0093  FirmwareDownloadFailed
```

`0003` soll ebenfalls nicht pauschal gefaked werden.

### Zweistufiges Aktivierungsmodell

```text
launcher_armed
  lokaler OTA bewusst vorbereitet, 0033 aber noch nicht akzeptiert

local_ota_active
  0033 vom Originalparser akzeptiert und Original-Metadaten sichtbar
```

Hook für:

```text
set_dtu_run_step() @ 0x1D2F8
```

nur:

```c
if (launcher_armed && requested_step == 7)
    requested_step = 11;
```

Andere Werte, insbesondere 4 und 5, nie umbiegen.

Publish-Hook:

```c
if (!local_ota_active)
    return original_ali_mqtt_push_OTA_msg(...);

code = parse_code_from_original_json_payload();

if (code == "0023" || code == "0053" || code == "0083")
    return 0;

if (code == "0113" && launcher.rollback_requested)
    return 0;

return original_ali_mqtt_push_OTA_msg(...);
```

---

## 6. Exakte Hook-Abschaltung / terminale Step-12-Übergänge

Die terminalen Cloudreport-Zustände wechseln erst nach erfolgreichem Publish zurück auf Step 12.

```text
0x001D744  step 10 -> 12  nach erfolgreichem 0083  (Fehler/Cancel-Ende)
0x001DA38  step 5  -> 12  nach erfolgreichem 0053  (Erfolg)
0x001DC90  step 9  -> 12  nach erfolgreichem 0113  (Rollback)
```

Sicheres Abschaltkriterium:

```text
local_ota_active == true
AND einer der terminalen Übergänge 0x1D744 / 0x1DA38 / 0x1DC90 wurde ausgeführt
AND board_ota_step == 12
```

Danach:

```text
local_ota_active = false
launcher_armed = false
Publish-Hook deaktivieren
run_step-Override deaktivieren
```

### `dtu_run_step` danach aktiv auf 7 setzen?

**Nein.**

Direkte Originalsetter:

```text
4   UART-/ProductKey-Initialisierung
5   ProductKey vorhanden / nächster Startupschritt
7   Cloud-Credential-/DeviceSecret-Phase bzw. Cloud-Recovery
11  MQTT erfolgreich initialisiert / produktiver Betriebszustand
```

Nach lokalem OTA soll nur der Override entfernt werden. Ein künstliches Schreiben von 7 könnte bei wieder verfügbarer realer Cloud einen gültigen Step 11 zerstören. Bei weiterhin fehlender Cloud kann der originale `aliMqtt_handle_thread()` anschließend selbst wieder 7 setzen.

Regel:

```text
terminal Step 12 -> Hooks entfernen -> dtu_run_step selbst NICHT schreiben
```

---

## 7. Reale UART-Konkurrenz vor OTA passiv messen

Gemeinsamer TX-Slot:

```text
uart485_send_data_to_board() @ 0x1562C
uart485WriteBuf              @ 0x928DC
uart485SendFlag              @ 0x930DC
uart485SendLen               @ 0x930E0
```

Der Slot besitzt keine Queue und keinen Mutex.

### Statisch bereits entschärft

`Check485Statue()` sendet seinen 8-Byte-Probe-Frame nur, wenn:

```c
uart485SendFlag == 0
```

und überschreibt daher keinen bereits wartenden OTA-Frame.

### Noch dynamisch zu bewerten

```text
normale MQTT/Cloud-Downlinks -> UART
RX-getriggerte lokale Antworten in getDevParameter()
weitere ereignisgesteuerte Producer
```

### Bevorzugte passive Messung

Am sichersten ist ein externer paralleler RS485-Mitschnitt über den bereits verwendeten USB-RS485-Sniffer. Dabei wird der LTE-Prozess überhaupt nicht verändert.

Über längeren Normalbetrieb erfassen:

```text
Timestamp
vollständiges RTU-Frame
Register/Function
Abstand zum vorherigen Frame
Richtung soweit aus Master/Slave-Timing ableitbar
```

Zielstatistik:

```text
Welche LTE->Board-TX-Frames treten im Normalbetrieb auf?
Wie häufig?
Welche sind periodisch?
Welche erscheinen nur RX-getriggert?
Wie groß ist der maximale Burst?
```

Optional kann in einer reinen Vorab-Normalbetriebsanalyse bei verfügbarem Debugger am Eingang `uart485_send_data_to_board()` die Return-Address/LR protokolliert werden, um Producer exakt einer Callsite zuzuordnen. Ein GDB-Breakpoint stoppt den Prozess kurz und ist deshalb weniger passiv als externer RS485-Mitschnitt.

Beim vollständig offline gefahrenen OTA fällt der gefährlichste normale Producer bereits weg:

```text
kein MQTT-Cloud-Downlink
 -> keine normalen cloudgesteuerten UART-Write-Kommandos
```

UART-RX darf niemals pausiert werden, da derselbe Laufzeitpfad C36E, C371, C36C und FC10-ACKs empfängt und den TX-Slot physisch auf `/dev/ttyHSL2` schreibt.

---

## 8. Empfohlene Safe-Launcher-Phasen

### Preflight – noch kein `0033`

```text
Supervisor/PPID identifiziert
Restartverhalten bekannt
OTA_INFO-Validator lokal getestet
Firmwaredatei verfügbar, MD5 bekannt
freier Speicher ausreichend
RS485 passiver Mitschnitt unauffällig
keine alte OTA_INFO-Resume-Sitzung offen
```

### ARM

```text
launcher_armed = true
nur set_dtu_run_step(7 -> 11) temporär erlauben
```

### Nach akzeptiertem `0033`

```text
local_ota_active = true
nur 0023/0053/0083 lokal mit 0 bestätigen
0113 nur bei bewusstem Rollback
```

### Vor erstem C5A8

```text
Download abgeschlossen
Original-MD5 erfolgreich
OTA_INFO exakt 220 Byte
CRC-16/X25 gültig
MD5/Code/Version/Length korrekt
Offset == 0
```

### Transfer

```text
nur bestätigter OTA_INFO-Offset = Fortschritt
CRC nach jeder Offsetänderung prüfen
No-Progress-Watchdog
C371 ackB=2 -> Offset exakt Length
```

### Promotion

```text
C36E 3 -> C37B3
warte auf C36E 5 oder 6
C36E5 = finaler Boarderfolg
C36E6 = finaler Boardfehler
```

### Cancel

```text
C36A senden
C36C status 1 zwingend abwarten
kein C36C1 -> nicht als sicheren Cancel bewerten
```

### Cleanup

Nach terminalem Step-12-Übergang:

```text
local_ota_active = false
launcher_armed = false
Publish-Hook entfernen
run_step-Override entfernen
dtu_run_step NICHT aktiv schreiben
```

---

## 9. Noch offene Punkte mit höchstem Nutzwert

1. Supervisor auf dem realen Modem per PPID/RootFS-Readout identifizieren.
2. GPIO50 OS-/elektrisch passiv beobachten und klären, ob ein externer DOG während langer AT-freier Phasen anderweitig bedient wird.
3. UART-Normalverkehr mehrere Stunden passiv mitschneiden und reale konkurrierende TX-Produzenten quantifizieren.
4. Launcher vollständig gegen Offline-VM/RS485-Simulator testen, einschließlich fehlender C36E/C371/C36C-Antworten und beschädigter OTA_INFO-Datei.

Breite weitere Firmwareanalyse ist für den Launcher derzeit deutlich weniger wertvoll als diese vier Validierungen.
