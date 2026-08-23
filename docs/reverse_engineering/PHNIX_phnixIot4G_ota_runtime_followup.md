# PHNIX `phnixIot4G` – OTA Runtime-Follow-up: Timer, Stalls, Persistenz und UART-TX

Stand: 2026-08-23

Grundlage: statische Analyse des ungestrippten ARM-ELF `phnixIot4G` (Build-ID `af4dcae12639bedce833ee5efa5da009777b6319`) sowie Abgleich mit den bereits dokumentierten Offline-VM-Ergebnissen. Keine Cloudkommunikation und keine reale Übertragung an ein Mainboard wurden ausgeführt.

Diese Datei ergänzt `PHNIX_phnixIot4G_ota_full_path.md` gezielt um Laufzeitaspekte, die für einen kontrollierten realen Mainboard-Updateversuch relevant sind.

## 1. OTA-Timer laufen in echten Sekunden

`TimerHandler()` liegt bei:

```text
0x0000AB0C
```

Nach der Initialisierung läuft die Funktion in einer Dauerschleife. Am Schleifenanfang:

```asm
0xAC34  mov r0,#1
0xAC38  bl  sleep
```

und am Ende:

```asm
0xB264  b 0xAC34
```

Damit werden die relevanten OTA-Zähler einmal pro Sekunde bearbeitet.

Bestätigte Timerfelder in `app @ 0x988FC`:

| Offset | Verwendung | Einheit |
|---:|---|---|
| `+0x38` | C350 Retry-Timer | Sekunden |
| `+0x40` | C357 Retry-Timer | Sekunden |
| `+0x48` | C5A8 Retry-/Send-Timer | Sekunden |
| `+0x50` | Rollback C375 Timer | Sekunden |
| `+0x54` | Cancel C36A Timer | Sekunden |
| `+0x6C` | Cancel-Deferral-Timer | Sekunden |

Die Felder `+0x3C`, `+0x44`, `+0x4C`, `+0x58` sind dagegen Retrybudgets und werden nicht als Sekundentimer heruntergezählt.

Wenn `app+0x6C` auf 0 fällt, löscht `TimerHandler()` auch das zugehörige Deferral-Flag `app+0x68`.

**Bewertung:** bestätigt.

---

## 2. C350 – exakte Retrylogik

Sender-Gate:

```text
dtu_set_devver_by_485() @ 0x1C740
```

Pseudocode:

```c
if (app.timer_c350 == 0 && app.retry_c350 != 0) {
    app.retry_c350--;
    set_sev_code_and_ver(...);   // C350
    app.timer_c350 = 3;
}
```

Zuordnung:

```text
app+0x38 = Timer
app+0x3C = Retrybudget
```

`0033` initialisiert `app+0x3C = 3`.

Damit werden maximal drei C350-Sendeversuche mit ungefähr 3 Sekunden Abstand ausgeführt.

Der normale Modbus-Schreib-ACK für C350 landet in:

```text
board_set_ser_ver_handle() @ 0x1B480
```

und macht ausschließlich:

```c
app.retry_c350 = 0;
```

Wichtig: Dieser FC10-/Write-ACK ist **nicht** der semantische OTA-Status C36E.

### Stallfall

Wenn der C350-Write bestätigt wird, aber danach kein C36E Status 0/1 folgt:

```text
C350 ACK
 -> retry_c350 = 0
 -> kein weiterer C350-Versand
 -> kein gefundener terminaler Timeout
```

Auch wenn gar kein C350-ACK kommt, endet nach drei Sendungen nur das Retrybudget. Im Sender-Gate selbst existiert kein Übergang auf `board_ota_step=10`.

**Konsequenz:** Der Originaldienst kann in dieser Phase ohne zusätzliche externe Zeitüberwachung dauerhaft stehen bleiben.

**Bewertung:** bestätigt aus dem statischen Kontrollfluss.

---

## 3. C357 – exakte Retrylogik

Sender-Gate:

```text
set_ota_bin_info_by_485() @ 0x1D214
```

Pseudocode:

```c
if (app.timer_c357 == 0 && app.retry_c357 != 0) {
    app.retry_c357--;
    app.timer_c357 = 3;
    set_ota_bin_info(fileSize, md5);   // C357
}
```

Zuordnung:

```text
app+0x40 = Timer
app+0x44 = Retrybudget
```

Der normale C357-FC10-ACK wird in:

```text
board_set_bin_info_handle() @ 0x1B4B4
```

verarbeitet und setzt:

```c
app.retry_c357 = 0;
```

Auch hier ist der normale Modbus-ACK vom späteren semantischen Boardstatus C36E Status 2 zu unterscheiden.

### Stallfall

Fehlt nach C357/C357-ACK der Status 2, wurde kein terminaler Zeitfehlerpfad gefunden. Nach Verbrauch bzw. Löschen des Retrybudgets sendet das Gate nicht weiter, ohne automatisch in `step 10` zu wechseln.

**Bewertung:** bestätigt.

---

## 4. C5A8 – Retrygate und Resume-Sonderverzögerung

Sender-Gate:

```text
set_update_board_bin_by_485() @ 0x1CE14
```

Pseudocode:

```c
int rc = -1;

if (app.timer_c5a8 == 0 && app.retry_c5a8 != 0) {
    app.retry_c5a8--;
    rc = set_board_update_bin();
    app.timer_c5a8 = 5;
}

return rc;
```

Zuordnung:

```text
app+0x48 = Timer
app+0x4C = Retrybudget
```

Damit besitzt ein aktiver Block zunächst bis zu drei Sendemöglichkeiten, jeweils durch einen 5-Sekunden-Timer getrennt.

Der einfache C5A8-Modbus-Write-ACK wird in:

```text
board_set_updata_bin_handle() @ 0x1B4E8
```

verarbeitet und setzt:

```c
app.retry_c5a8 = 0;
```

Der eigentliche blockbezogene Fortschritt wird dagegen über C371 verarbeitet.

### Resume-Sonderfall

In `board_is_allow_upg_handle()` bei Status 2 und aktivem Resume-Marker `app+1 == 1`:

```text
0x1BC50  board_ota_step = 6
0x1BC60  app+0x4C = 3
0x1BC70  app+0x48 = 30
0x1BC80  ota_info+0x16 = 1
0x1BC90  app+1 = 0
```

Der Resume-Pfad besitzt damit statisch eindeutig einen **30-Sekunden C5A8-Timer** vor dem nächsten durch dieses Gate möglichen Sendetermin. Beim frischen Downloadpfad wird `+0x4C=3` gesetzt, aber kein neuer 30-Sekundenwert nachgewiesen; bei `+0x48==0` kann der erste Block dort unmittelbar gesendet werden.

Ob PHNIX die 30 Sekunden absichtlich als Board-Recovery-/Rebootfenster nutzt, ist aus dem Binary allein nicht beweisbar. Die Verzögerung selbst ist jedoch bestätigt.

---

## 5. C371 – bestätigter Offset und Progress-Takt

Handler:

```text
board_updata_bin_handle() @ 0x1B72C
```

Bei gültigem C371 mit `ackB == 1` und erwarteter Blocknummer:

```text
persisted_offset += blockSize
sys_set_board_file_offset(persisted_offset)
```

Zusätzlich wird anhand von:

```text
persisted_offset / blockSize
```

jede 30. bestätigte Blockposition erkannt. Dann setzt der Handler:

```c
app[0] = 4;
```

`dtu_upgrade_pro()` erkennt diesen Zustand, löscht das Flag und ruft:

```text
board_dowmload_rep() @ 0x1D434
 -> ota_device_send_ota_progress()
 -> OTA-Code 0043
```

auf.

Bei Default-Blockgröße 168 Byte entsteht ein Transfer-Progresspunkt alle:

```text
30 * 168 = 5040 Byte
```

Das ist wesentlich häufiger als der libcurl-Downloadfortschritt 25/50/75/100.

### Korrektur: Transfer-0043 ist nicht dauerhaft blockierend

Der Kontrollfluss lautet:

```c
if (app[0] == 4) {
    app[0] = 0;
    if (board_dowmload_rep() != 0)
        return;              // nur dieser dtu_upgrade_pro()-Durchlauf
}
```

Da `app[0]` **vor dem Publish gelöscht** wird und `fota_board_thread_handle()` unmittelbar erneut `dtu_upgrade_pro()` aufruft, wird ein fehlgeschlagenes Transfer-`0043` nicht erneut als Pending-Progress behandelt und hält die State-Machine nicht dauerhaft an.

Damit gilt für einen minimalen Offline-Publish-Stub:

```text
0043 Downloadprogress       nicht blockierend
0043 Transferprogress       ebenfalls nicht dauerhaft blockierend
```

Die frühere Einstufung von Transfer-`0043` als zwingend zu bestätigender Blocker ist zu korrigieren.

**Bewertung:** bestätigt.

---

## 6. Cloud-Publishes: neue minimale Blockermenge

Aus dem aktuellen Kontrollfluss ergibt sich für den normalen Mainboard-OTA-Pfad:

| Code | Bedeutung | Bei Publishfehler dauerhaft blockierend? |
|---:|---|---|
| `0023` | Upgrade-/Allow-Report | **ja** |
| `0043` | HTTP-Downloadprogress | nein |
| `0043` | C5A8-Transferprogress | nein, nur aktueller Schleifendurchlauf endet |
| `0053` | Upgrade erfolgreich | **ja**, Step 5 bleibt aktiv |
| `0083` | Upgrade fehlgeschlagen | **ja**, Step 10 bleibt aktiv |
| `0093` | FirmwareDownloadFailed | nein, Return wird im Downloadpfad nicht als Zustandsblocker benutzt |
| `0113` | Rollback-/Initialisierungsergebnis | **ja**, wenn Rollbackpfad benutzt wird |
| `0003` | Board-Versionsreport | bedingt, nur wenn entsprechendes Refresh-/Preamble-Flag aktiv ist |

Für einen kontrollierten normalen Offline-Updateablauf ohne Rollback ist die wirklich notwendige Stubmenge damit im Kern:

```text
0023
0053
0083
```

`0043` muss nicht künstlich erfolgreich bestätigt werden, sofern keine externe Auswertung des Fortschritts erforderlich ist.

---

## 7. `fota_board_thread_handle()` ist eine Busy-Loop

Thread:

```text
fota_board_thread_handle() @ 0x1DD4C
```

Nach Setup und `sys_read_para()`:

```asm
0x1DDD8  set_board_ota_step(12)
0x1DDE0  bl dtu_upgrade_pro
0x1DDE4  b  0x1DDE0
```

Zwischen den Aufrufen befindet sich **kein `sleep()`**.

Folge:

- Ein hart blockierender Cloud-Publish in Step 1/5/10 kann extrem häufig erneut versucht werden.
- Timerabhängige RS485-Gates sind trotzdem begrenzt, weil ihre Sekundentimer separat in `TimerHandler()` laufen.
- Bei einem lokalen Offline-Lauf sollte ein notwendiger Publish daher nicht absichtlich fehlschlagen gelassen werden; der gezielte Stub auf Return `0` verhindert eine unnötige CPU-/Log-/Publish-Schleife.

**Bewertung:** bestätigt.

---

## 8. Persistenzfehler stoppen den Transfer nicht zuverlässig

Nach erfolgreichem HTTP-Download + MD5 ruft `dtu_upgrade_pro()` auf:

```text
0x1D874  sys_set_board_file_offset(0)
0x1D87C  sys_set_board_file_md5(...)
0x1D890  sys_set_board_file_len(...)
0x1D8E0  sys_set_dev_otavercode(...)
```

Die Rückgaben der ersten drei Setter werden nicht als Gate ausgewertet.

`sys_set_dev_otavercode()` wird zwar geprüft, aber bei Fehler nur geloggt; anschließend folgt trotzdem:

```text
0x1D900  set_board_ota_step(6)
```

Auch im C371-Pfad wird der Return von:

```text
sys_set_board_file_offset()
```

nicht als Transfer-Stop verwendet.

Damit kann das Update weiterlaufen, obwohl `/data/phnixIot_device_OTA_INFO` nicht sauber aktualisiert wurde.

### Risiko

Der unmittelbare Transfer kann funktionieren, aber ein Stromausfall/Prozessrestart kann danach:

- auf einen alten Offset zurückfallen;
- inkonsistente MD5/Länge/Version sehen;
- Resume verlieren;
- einen bereits bestätigten Block erneut senden.

### Empfehlung für einen kontrollierten Lauf

Vor dem ersten C5A8 sollte extern verifiziert werden:

```text
/data/phnixIot_device_OTA_INFO vorhanden
schreibbar
220-Byte-Struktur nach Metadata-Persistenz lesbar
CRC durch sys_read_para() akzeptiert
MD5/Length/SoftwareCode/Version entsprechen dem erwarteten Kandidaten
Offset == 0 bei frischem Update
```

Diese Prüfung kann außerhalb der Original-Updatefunktionen erfolgen; die Original-Persistenzlogik muss dafür nicht gepatcht werden.

**Bewertung:** Persistenzfehler-Toleranz statisch bestätigt; konkrete Dateisystemfehler wurden nicht erzeugt.

---

## 9. `0033` zerstört die alte Resume-Basis früh

In `ota_device_set_ota_file_download_info()` beginnt der zustandsändernde Teil um `0x19064`.

Nach erfolgreichem Parsing werden unter anderem:

```text
app+0x3C = 3
ota_info+0x16 = 2
SSID persistent in statistic_para geschrieben
```

und anschließend:

```sh
rm -f /cache/phnixIot_device_OTA
true > /data/phnixIot_device_OTA_INFO
```

aufgerufen.

Das bedeutet:

> Das Akzeptieren eines neuen `0033` verwirft die bisherige OTA_INFO-/Resume-Basis **vor** einem erfolgreichen neuen Firmwaredownload.

Ein Crash während des nachfolgenden HTTP-Downloads besitzt deshalb keinen sauberen Rückweg auf einen zuvor halbfertigen OTA-Transfer.

Für einen realen lokalen Updateversuch sollte `0033` daher erst dann injiziert werden, wenn URL/Datei, Stromversorgung, Speicherplatz und UART-Voraussetzungen bereits geprüft sind.

---

## 10. Fehlende semantische Antworten: externer Phase-Watchdog empfohlen

Die Originalsoftware besitzt Timer und Retrybudgets für das Senden, aber nicht in jeder Phase einen terminalen Timeoutzustand.

Besonders kritisch:

```text
C350 ohne ACK          -> max. 3 Sends, danach still
C350 ACK ohne C36E 1   -> kein weiterer C350, kein terminaler Timeout gefunden
C357 ohne ACK          -> max. 3 Sends, danach still
C357 ACK ohne C36E 2   -> kein terminaler Timeout gefunden
C5A8/C371-Ausfall      -> lokales Retrybudget vorhanden, aber kein allgemeiner terminaler Watchdog im Gate
```

Daher sollte ein externer Laufzeit-Supervisor nicht nur `board_ota_step`, sondern die **Protokollphase plus Wandzeit** überwachen.

Sinnvolle Abbruchbedingungen für einen kontrollierten Test sind beispielsweise:

```text
Phase C350:  kein erwarteter semantischer Boardstatus innerhalb eines definierten Fensters
Phase C357:  kein Status 2 innerhalb eines definierten Fensters
Phase C5A8:  persistierter Offset bewegt sich über mehrere Retryintervalle nicht
Finalisierung: kein Status 5/6 nach letztem Block
```

Die konkreten externen Grenzwerte sollten bewusst großzügiger als die internen 3-/5-Sekunden-Retrytimer gewählt und zunächst in einer VM/Labortopologie validiert werden.

---

## 11. Cancel und Rollback besitzen unterschiedliche Retrysemantik

### Cancel

Step 7 verwendet:

```text
app+0x54 = Cancel-Timer
app+0x58 = Retrybudget
```

Wenn `app+0x54 == 0` und `app+0x58 != 0`:

```c
app.retry_cancel--;
app.timer_cancel = 3;
reply_cancel_upgrade(1);   // C36A
```

Fehlerpfade Status 4/6 setzen typischerweise zunächst:

```text
retry = 5
timer = 5
```

Damit folgt nach initial etwa 5 Sekunden ein endlicher Satz von maximal fünf C36A-Versuchen im Abstand von ungefähr 3 Sekunden.

Cloud-Cancel setzt zusätzlich:

```text
app+0x68 = 1
app+0x6C = 60
```

`TimerHandler()` löscht `+0x68`, wenn der 60-Sekunden-Timer abgelaufen ist.

### Rollback

Step 8 prüft:

```text
app+0x03 == 1
app+0x50 == 0
```

setzt dann:

```text
app+0x50 = 3
```

und sendet:

```text
dtu_to_board(1)   // C375
```

Das Flag `app+0x03` bleibt bis zur C378-Antwort aktiv. Damit kann der Request nach erneutem Ablauf des 3-Sekunden-Timers wieder gesendet werden.

Im untersuchten Pfad wurde hierfür kein separates endliches Retrybudget wie beim Cancel gefunden.

**Bewertung:** Rollback-Request Status 1 wird statisch als potentiell unbegrenzt periodisch wiederholbar bewertet, solange keine C378-Antwort bzw. andere Zustandsänderung erfolgt.

---

## 12. UART-TX-Produzenten während eines Transfers

Alle relevanten Pfade landen letztlich im gemeinsamen Single-Slot:

```text
uart485_send_data_to_board() @ 0x1562C
```

### OTA-Produzenten

```text
C37B ACK              dtu_reply_recv_status
C36A Cancel           reply_cancel_upgrade
C375 Rollback         dtu_to_board
C350                  set_sev_code_and_ver
C357                  set_ota_bin_info
C5A8                  set_board_update_bin
```

### normale / servicebezogene Produzenten

```text
check_mcu_get_sta()
getDevParameter()       lokale RX-Antworten/ACKs
uart485_get_device_info()
Check485Statue()
aliMqtt_topic_get_msg_arrive()   normaler Cloud-Downlink -> UART
```

### `Check485Statue()` besitzt einen Sendeslot-Guard

Funktion:

```text
0x156B4
```

Pseudocode:

```c
if (uart485SendFlag == 0)
    uart485_send_data_to_board(static_8_byte_probe, 8);
```

Der periodische 485-Healthcheck kann damit einen **bereits wartenden** OTA-Frame nicht überschreiben.

### weiterhin kritisch

Nicht für alle anderen Produzenten wurde ein entsprechender Guard gefunden. Besonders der normale Cloud-Downlink über:

```text
aliMqtt_topic_get_msg_arrive() @ 0x1EED0
```

ist während eines echten cloudverbundenen OTA theoretisch ein Konkurrent zum gemeinsamen Puffer.

Bei einem bewusst offline gefahrenen lokalen OTA fällt dieser Produzent natürlicherweise weg.

### sichere Pausen-/Unterdrückungsstrategie

Nicht pausieren:

```text
uart485_thread_handle / getDevParameter
```

Dieser Thread wird für physisches TX-Drain sowie C36E/C371/FC10-ACK-RX zwingend benötigt.

Unkritisch bzw. sinnvoll unterdrückbar während eines lokalen Offline-OTA:

```text
normaler MQTT-Downlink -> UART
```

Startup-Producer wie `uart485_get_device_info()` sollten vor Aktivierung des lokalen OTA bereits abgeschlossen sein, nicht mitten im Startup suspendiert werden.

Ereignisgetriebene lokale RX-Antworten sollten nicht blind abgeschaltet werden, da sie Teil des normalen Boardprotokolls sein können.

---

## 13. Watchdog-/Restart-Beobachtung

Das ELF enthält:

```text
Reset_All_DOG() @ 0xB400
```

Die Funktion pulst GPIO 50:

```text
GPIO 50 = 1
usleep(2)
GPIO 50 = 0
```

Die Disassemblierung ruft `usleep@plt` mit dem Argument `2` auf. Es handelt
sich damit um ungefähr zwei Mikrosekunden und nicht um zwei Sekunden.

Ihre direkten Aufrufer liegen überwiegend in den AT-/Modem-Kommandofunktionen (`AT_CPIN`, `AT_APN1`, `AT_GetCSQ`, HTTP/MQTT-AT-Pfade usw.).

Im eigentlichen `dtu_upgrade_pro()`-/C5A8-Pfad wurde kein direkter Aufruf von `Reset_All_DOG()` gefunden.

Daraus lässt sich **nicht** sicher ableiten, ob GPIO 50 einen externen Watchdog füttert oder einen Modem-/Subsystemreset auslöst; der Name allein reicht dafür nicht. Wichtig für den lokalen OTA-Hook ist aber:

> Das bloße Festhalten von `dtu_run_step == 11` erzeugt im untersuchten Board-OTA-Pfad keinen zusätzlichen direkten `Reset_All_DOG()`-Aufruf.

Ein separater systemweiter Supervisor außerhalb dieses ELF bleibt weiterhin möglich.

---

## 14. Empfohlener Preflight für einen späteren realen lokalen Updateversuch

Aus den statischen Befunden ergibt sich vor Aktivierung eines lokalen `0033` mindestens:

1. UART-Initialisierung/ProductKey-Phase vollständig abgeschlossen; `dtu_run_step` nicht mehr 4/5.
2. Keine alte aktive OTA-State-Machine außer dem erwarteten Idle-/Step-12-Zustand.
3. `/cache` besitzt genügend freien Speicher für die Firmwaredatei.
4. `/data/phnixIot_device_OTA_INFO` und `/data/phnixIot_device_statisic` sind les- und schreibbar.
5. Alte OTA_INFO bei Bedarf extern sichern, da `0033` sie früh leert.
6. Firmware-MD5 und erwartetes `fileSize` vorab extern verifizieren.
7. Normalen MQTT-Downlink zum UART während des lokalen OTA nicht zulassen.
8. UART-RX/`getDevParameter()` ausdrücklich weiterlaufen lassen.
9. Eigenen Phase-Watchdog implementieren; nicht auf einen terminalen Timeout des Originaldienstes vertrauen.
10. Nach jedem C371 nur den **persistierten Offset** als bestätigten Fortschritt betrachten.
11. Vor einem absichtlichen Prozessrestart prüfen, dass OTA_INFO-CRC und Offset konsistent sind.
12. Lokalen Cloud-/Run-Step-Hook nach terminalem Erfolg, Fehler oder Cancel vollständig entfernen und Originalzustand wiederherstellen.

---

## 15. Wichtigste neuen Schlussfolgerungen

- Die OTA-Timer sind echte Sekundenwerte.
- C350: maximal 3 Sendungen, etwa alle 3 s.
- C357: maximal 3 Sendungen, etwa alle 3 s.
- C5A8: Retrygate mit 5-s-Timer; Resume setzt explizit 30 s.
- Plain Modbus-ACK und semantischer OTA-Status sind getrennte Ebenen.
- Nach ausgeschöpften Senderetries existiert nicht überall ein terminaler Timeout; Silent-Stall ist möglich.
- Transferprogress `0043` ist **nicht dauerhaft blockierend**; das Pending-Flag wird vor dem Publish gelöscht.
- Für den normalen Offlinepfad reduziert sich die zwingende Publish-Stubmenge im Kern auf `0023`, `0053`, `0083` (plus bedingte Sonderpfade).
- Persistenzschreibfehler stoppen den Transfer nicht zuverlässig und gefährden vor allem Resume/Recovery.
- `0033` verwirft die alte OTA_INFO schon vor erfolgreichem neuen Download.
- Cancel besitzt ein endliches Retrybudget; Rollback-C375 Status 1 kann dagegen periodisch weiterlaufen.
- `Check485Statue()` respektiert einen bereits belegten UART-Sendeslot.
- Der UART-RX-Thread darf während des Transfers nicht pausiert werden.
