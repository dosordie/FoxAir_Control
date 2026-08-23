# PHNIX `phnixIot4G` – OTA-/Firmware-Update-Pfad

Stand: 2026-08-23

Grundlage ist die statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`. Diese Datei konzentriert sich auf die Firmware-Update-Logik für **DTU/LTE-Modul** und **Mainboard**.

## Kurzfazit

`phnixIot4G` besitzt zwei getrennte OTA-Pfade:

```text
DTU-Self-Update
MQTT OTA_GET -> JSON Code 0032 -> URL/MD5/Size übernehmen
 -> HTTP/curl Download nach /data/phnixIot4G_OTA
 -> MD5 über das erwartete fileSize-Fenster prüfen
 -> chmod +x
 -> mv auf /data/phnixIot4G
 -> killall -9 phnixIot4G
```

und:

```text
Mainboard-Update
MQTT OTA_GET -> JSON Code 0033 -> URL/MD5/Size/SSID übernehmen
 -> HTTP/curl Download nach /cache/phnixIot_device_OTA
 -> MD5 über das erwartete fileSize-Fenster prüfen
 -> Metadaten persistent speichern
 -> Mainboard-OTA-State-Machine
 -> RS485 OTA-Register C350/C357/C36C/C36E/C371/C378/C5A8/C544
```

Die beiden Pfade teilen MQTT/JSON-Dispatcher und Download-/Progress-Infrastruktur, sind danach aber klar getrennt.

Wichtige Korrektur gegenüber älteren Fassungen dieser Datei: `fileSize` wird in den lokalen MD5-Prüffunktionen **nicht als tatsächliche Dateilänge validiert**. Die Funktionen lesen höchstens `fileSize` Bytes in einen vorher genullten Puffer und hashen anschließend immer exakt `fileSize` Bytes. `fileSize` ist damit praktisch das MD5-Prüffenster.

---

## 1. Exakte OTA_GET-Code-Dispatch-Tabelle

`ota_code_handle()` (`0x19958`) parst das JSON-Feld `code`, wandelt es numerisch um und durchsucht eine feste Tabelle bei `0x91C20`.

Die Tabelle ist im ELF vollständig statisch enthalten:

| Code dezimal | MQTT-String | Handler | Bedeutung |
|---:|---:|---|---|
| 12 | `0012` | `ota_dtu_set_ota_info()` | DTU-OTA-Metadaten / Cloud-Version setzen |
| 32 | `0032` | `down_dtu_ota_url_handle()` | DTU-OTA Download/Install starten |
| 33 | `0033` | `down_board_ota_url_handle()` | Mainboard-OTA Downloaddaten übernehmen |
| 62 | `0062` | `down_check_dtu_ver_handle()` | erneutes DTU-Version-Reporting anfordern |
| 63 | `0063` | `down_check_board_ver_handle()` | erneutes Mainboard-Version-Reporting anfordern |
| 73 | `0073` | `down_board_cancel_ota_handle()` | Mainboard-OTA abbrechen |
| 58 | `0058` | `down_dtu_cancel_ota_handle()` | DTU-OTA abbrechen |
| 103 | `0103` | `down_board_ver_bcakroll_handle()` | Mainboard-Rollback anfordern |
| 114 | `0114` | `device_reset_handle()` | DTU Reset/Reboot-Command |

Damit ist die eingehende OTA-Kommandoliste dieses Builds vollständig statisch belegt.

---

## 2. DTU-Self-Update: Metadaten

`ota_dtu_set_ota_info()` liest aus dem OTA-JSON mindestens:

```text
softwareCodeCloud
softwareVerCloud
fileMD5
fileSize
```

Die zugehörigen Strings sind im ELF sichtbar. Die Daten landen in der globalen `otaDtuInfo`-Struktur um `0x9313C`.

`ota_dtu_set_ota_file_download_info()` liest später zusätzlich:

```text
otaFileDownloadAddr
```

Damit besteht der DTU-Downloaddatensatz mindestens aus:

```text
Soll-Softwarecode
Soll-Version
Soll-MD5
Soll-Dateigröße / MD5-Prüffenster
Download-URL
```

---

## 3. DTU-Self-Update: Download

`down_dtu_ota_url_handle()` (`0x19580`) führt nach Übernahme der URL diesen Pfad aus:

```text
ota_dtu_set_ota_file_download_info(json)
  ↓
OTA erlaubt?
  ↓ ja
ota_download_dtu_otaFile()
  ↓
ota_check_dtu_otaFile_md5()
  ↓ Erfolg
Installationsschritte
```

Downloadziel:

```text
/data/phnixIot4G_OTA
```

Vor dem Download wird die alte Datei entfernt:

```sh
rm -f /data/phnixIot4G_OTA
```

Der Download verwendet `libcurl` dynamisch über:

```text
curl_easy_init
curl_easy_setopt
curl_easy_perform
curl_easy_getinfo
curl_easy_strerror
curl_easy_cleanup
curl_slist_append
curl_slist_free_all
```

Die URL aus `otaFileDownloadAddr` wird direkt an curl übergeben.

Der Progress-Callback ist `assetsManagerProgressFunc()`.

---

## 4. OTA-Download-Fortschritt

`assetsManagerProgressFunc()` berechnet:

```text
progress = downloaded / total * 100
```

Nur bei exakt folgenden Prozentwerten wird ein OTA-Progress-Report ausgelöst:

```text
25
50
75
100
```

Globaler OTA-Typ:

```text
1 -> DTU OTA -> ota_dtu_send_ota_progress()
2 -> Mainboard OTA -> ota_device_send_ota_progress()
```

Cloudcodes:

```text
DTU Progress       0042
Mainboard Progress 0043
```

---

## 5. DTU-Dateiprüfung – Korrektur zur Dateilänge

Nach erfolgreichem Download wird `ota_check_dtu_otaFile_md5()` (`0x1A0C8`) aufgerufen.

Die Funktion führt **keinen separaten Vergleich der tatsächlichen Dateigröße mit `otaDtuInfo.fileSize`** durch. Rekonstruiert ist vielmehr:

```c
expected = otaDtuInfo.fileSize;
buf = malloc(expected + 1);
memset(buf, 0, expected + 1);

fp = fopen("/data/phnixIot4G_OTA", "rb");
nread = fread(buf, 1, expected, fp);

MD5Init(&ctx);
MD5Update(&ctx, buf, expected);   // nicht nread
MD5Final(...);
```

`nread` wird zwar geloggt, aber nicht als Akzeptanzbedingung gegen `expected` geprüft.

Folgen:

```text
Datei kürzer als fileSize:
  fehlende Bytes bleiben im vorher genullten Puffer 0x00
  und gehen so in den MD5 ein.

Datei länger als fileSize:
  nur die ersten fileSize Bytes werden gehasht;
  angehängte Daten bleiben unberücksichtigt.
```

Damit ist `fileSize` lokal ein **MD5-Prüffenster**, keine echte Dateilängenvalidierung.

Die MD5-Implementierung liegt im Executable (`MD5Init`, `MD5Update`, `MD5Final`).

Es gibt in diesem PHNIX-DTU-Pfad **keine zusätzlich erkannte RSA-/Signaturprüfung des heruntergeladenen Binaries**. Die lokale Integritätsentscheidung beruht auf dem MD5-Vergleich über das erwartete Fenster.

Hinweis: Das Executable enthält zusätzlich generischen Aliyun-OTA-Code mit RSA-/MD5-Symbolen, dieser ist vom hier beschriebenen PHNIX-`CMD_OTA`-Pfad zu unterscheiden.

---

## 6. DTU-Self-Update: Installation

Wenn Download und MD5 erfolgreich sind, führt `down_dtu_ota_url_handle()` drei fest eingebettete Shellkommandos aus:

```sh
chmod a+x /data/phnixIot4G_OTA
mv /data/phnixIot4G_OTA /data/phnixIot4G
killall -9 phnixIot4G
```

Damit ist der Installationsmechanismus sehr einfach:

```text
neues ELF herunterladen
 -> MD5 prüfen
 -> executable setzen
 -> bestehende Programmdatei ersetzen
 -> laufenden Prozess hart beenden
```

Der Neustart erfolgt damit offenbar über einen Plattform-/Supervisor-Mechanismus außerhalb dieses ELF, der `phnixIot4G` erneut startet. Welcher konkrete Supervisor dafür verantwortlich ist, ist aus diesem Binary allein noch nicht belegt.

Bei Downloadfehler wird Code `0092` gesendet (`FirmwareDownloadFailed`).

Bei Integritäts-/Upgradefehler wird Code `0082` gesendet (`upgradeFailed`).

Erfolgsreport DTU:

```text
0052 progress=100
```

---

## 7. DTU Reset-Command `0114`

`device_reset_handle()` erzeugt zuerst eine OTA-Antwort:

```json
{"cmd":"RESET","code":"0114","param":{"result":"1"}}
```

Nach erfolgreichem MQTT-Publish wird gewartet und anschließend der Resetpfad ausgeführt.

Im Executable sind sowohl `reboot()` als auch der String `reboot` vorhanden; der Reset-Handler führt nach dem Ack eine verzögerte Systemaktion aus.

---

## 8. Mainboard-OTA: eingehende Cloud-Daten

`down_board_ota_url_handle()` ruft bei erlaubtem Zustand:

```text
ota_device_set_ota_file_download_info(json)
```

auf.

Die Funktion extrahiert:

```text
softwareCode
softwareVer
ssid
fileMD5
fileSize
otaFileDownloadAddr
```

Wichtige globale Struktur:

```text
otaDeviceInfo @ ca. 0x933AC
```

Der SSID-Wert wird aus einem ASCII-Feld in einen 8-/16-Bit-internen Wert umgesetzt und auch persistent gespeichert.

Nach Übernahme der Daten werden OTA-Zustände und persistente Parameter aktualisiert.

---

## 9. Mainboard-Firmwaredownload und lokale Prüfung

Downloadziel:

```text
/cache/phnixIot_device_OTA
```

Vorher:

```sh
rm -f /cache/phnixIot_device_OTA
```

`board_ota_http_download()` ruft:

```text
ota_download_device_otaFile()
 -> ota_check_device_otaFile_md5()
```

auf.

`ota_check_device_otaFile_md5()` (`0x1A370`) verwendet dieselbe problematische Längenlogik wie die DTU-Prüfung:

```text
malloc(fileSize + 1)
memset(..., 0)
fread(..., fileSize)
MD5Update(..., fileSize)
```

Auch hier wird der tatsächliche `fread()`-Rückgabewert nicht gegen `fileSize` als Akzeptanzbedingung geprüft.

Daher gilt auch für das Mainboard-Payload:

```text
fileSize = MD5-Prüffenster
keine eigenständige echte Dateilängenvalidierung
```

Bei Downloadfehler:

```text
0093 FirmwareDownloadFailed
```

Bei Upgradefehler:

```text
0083 upgradeFailed
```

Progress:

```text
0043
```

Erfolg:

```text
0053 progress=100
```

---

## 10. Persistenz Mainboard-OTA

Relevante Persistenzfunktionen:

```text
sys_set_dev_otavercode
sys_set_board_file_md5
sys_get_board_file_md5
sys_set_board_file_len
sys_get_board_file_len
sys_set_board_file_offset
sys_get_board_file_offset
sys_get_board_ota_ssid
sys_set_board_ota_ssid
sys_get_ver
sys_set_ver
```

Zusätzliche Statusdatei:

```text
/data/phnixIot_device_OTA_INFO
```

Sie wird für Resume-/Offset-/OTA-Zustandsinformationen verwendet.

Damit kann der Mainboard-OTA-Vorgang einen unterbrochenen Transfer zumindest teilweise persistent fortsetzen.

`board_ota_step` selbst ist dagegen RAM-only; Resume basiert auf den persistenten Firmwaremetadaten und dem bestätigten Dateioffset plus erneutem Handshake.

---

## 11. Mainboard-OTA-State-Machine

Der permanente Thread:

```text
fota_board_thread_handle()
```

führt nach Initialisierung endlos aus:

```text
dtu_upgrade_pro()
```

`dtu_upgrade_pro()` läuft nur produktiv, wenn:

```text
dtu_run_step == 11
```

also nach vollständig erfolgreichem MQTT-Startup.

Die Board-State-Machine verwendet `board_ota_step`.

Bestätigte Zustände:

| Step | Bedeutung |
|---:|---|
| `1` | Upgrade-Erlaubnis / Cloud-Anfrage |
| `3` | Board-Firmware herunterladen und MD5 prüfen |
| `6` | Firmware via RS485 übertragen |
| `12` | Warte-/Abschlusszustand; Boardantworten treiben weiter |
| `5` | Erfolg an Cloud melden |
| `10` | Fehler an Cloud melden |
| `7` | Cancel-/Recovery-Pfad |
| `8` | Rollback-/Backroll-Steuerung |
| `9` | Rollback-Ergebnis an Cloud melden |

Der reguläre Pfad lautet damit vereinfacht:

```text
Step 1
 -> Step 3
 -> HTTP Download + MD5
 -> Persistenz
 -> Step 6
 -> RS485 Firmwaretransfer
 -> Step 12
 -> Board-Ergebnis
 -> Step 5 oder Step 10
```

Cloud-Kommandos `0062` und `0063` setzen lediglich Flags für ein erneutes Versionsreporting; sie starten nicht direkt einen Download.

---

## 12. Mainboard-RS485-OTA-Register

Der rekonstruierte `unpack_mcu_modbus()` behandelt exklusiv diese OTA-/Serviceadressen:

| Register | Handler |
|---:|---|
| `0xC350` | `board_set_ser_ver_handle()` |
| `0xC357` | `board_set_bin_info_handle()` |
| `0xC36C` | `board_recv_cancel_upgrade_handle()` |
| `0xC36E` | `board_is_allow_upg_handle()` |
| `0xC371` | `board_updata_bin_handle()` |
| `0xC378` | `board_reply_verbackroll_handle()` |
| `0xC5A8` | `board_set_updata_bin_handle()` |
| `0xC544` | `board_softcode_ver_handle()` |

Damit sind Mainboard-OTA und normaler Modbusbetrieb auf Parser-/Handler-Ebene logisch getrennt. Auf der physischen UART-TX-Seite teilen sie sich dagegen dieselbe Sendeschiene; siehe Abschnitt 15.

---

## 13. Versionsreport / OTA-Handshake

Das LTE-Modul sendet aktiv:

```text
ota_dtu_send_version_to_phnix()
 -> code 0002

ota_device_send_version_to_phnix()
 -> code 0003
```

Mainboard-Version (`0003`) enthält:

```text
deviceCode
deviceSoftwareCode
deviceSoftwareVer
ssid
```

OTA-Erlaubnisantworten:

```text
0022 -> DTU
0023 -> Mainboard
```

Damit ist das Protokollmodell:

```text
Version melden
 -> Cloud entscheidet OTA-Ziel/Version
 -> Downloadinformationen kommen separat
 -> Client prüft Download
 -> Update wird lokal ausgeführt
```

---

## 14. Sicherheitsrelevante statische Beobachtung

Für den PHNIX-DTU-Self-Update-Pfad ist statisch erkennbar:

```text
Authentisierung des MQTT-Kanals: ja
TLS/Serverprüfung: ja
Download-Integrität: MD5 über erwartetes fileSize-Fenster
separate Firmware-Signaturprüfung im PHNIX-DTU-Pfad: nicht gefunden
```

Das bedeutet nicht automatisch, dass der reale Cloudprozess unsicher ist; die Download-URL kann serverseitig geschützt/signiert sein. Im Client selbst ist für das heruntergeladene DTU-ELF jedoch keine zusätzliche kryptografische Signaturvalidierung sichtbar.

Beim Mainboard-Image ist ebenfalls der MD5 über das erwartete `fileSize`-Fenster die erkennbare lokale Downloadprüfung; weitere Validierungen finden zusätzlich im Mainboard-OTA-/Bootpfad statt.

---

## 15. UART-/Warmlink-Abhängigkeit des OTA-Pfads

Die Detailanalyse des konkreten `phnixIot4G`-Builds zeigt, dass OTA und normaler Warmlink-Verkehr **dieselbe zentrale UART-Sendeschiene** verwenden.

### 15.1 `uart485_send_data_to_board()` ist kein direkter `write()`

Funktion:

```text
uart485_send_data_to_board() @ 0x1562C
```

Sie schreibt nicht direkt auf `/dev/ttyHSL2`, sondern kopiert das Telegramm in einen globalen Sendeslot:

```c
if (len <= 2048) {
    memcpy(uart485WriteBuf, data, len);
    uart485SendLen = len;
    uart485SendFlag = 1;
}
```

Bestätigte Globals:

```text
uart485WriteBuf   0x928DC   2048 Byte
uart485SendFlag   0x930DC
uart485SendLen    0x930E0
UART-FD           0x930E4
```

Damit gilt:

```text
OTA-Producer --------+
                     |
Normalbetrieb -------+--> uart485_send_data_to_board()
                     |       |
weitere UART-Sender -+       v
                         ein gemeinsamer
                         2048-Byte-Sendeslot
                              |
                              v
                         uart485SendFlag
                              |
                              v
                         UART-Thread
                              |
                              v
                         write(fd,...)
```

### 15.2 Keine Queue und kein Mutex im Sendeslot

In `uart485_send_data_to_board()` wurde keine Synchronisierung über

```text
pthread_mutex_lock/unlock
sem_wait/sem_post
```

oder eine erkennbare atomare Reservierung gefunden.

Der Sendemechanismus ist außerdem **keine Queue**, sondern nur ein einzelner globaler Puffer plus Länge und Flag.

Daraus ergibt sich statisch eine mögliche Race-/Overwrite-Situation:

```text
Thread A legt OTA-Frame ab
  -> flag = 1

vor Verarbeitung schreibt Thread B einen anderen Frame
  -> gleicher Puffer wird überschrieben
  -> Länge wird ersetzt
  -> flag bleibt 1
```

Ob diese Situation im realen Betrieb tatsächlich auftritt, hängt von höherer Zustandslogik und zeitlicher Serialisierung der Produzenten ab. Der Sendeslot selbst schützt jedoch nicht davor.

### 15.3 Physisches Senden erfolgt im UART-Thread

`uart485_thread_handle()` läuft nach der Initialisierung dauerhaft über `getDevParameter()`.

Dort wird bei gesetztem Sendeflag schließlich ausgeführt:

```c
write(uart_fd, uart485WriteBuf, uart485SendLen);
```

Danach werden bei jedem Rückgabewert ungleich `-1`:

```text
uart485SendLen  = 0
uart485SendFlag = 0
```

gesetzt.

Damit ist der UART-Thread der zentrale physische Sender für die über `uart485_send_data_to_board()` eingelegten Frames.

### 15.4 Partial `write()` wird nicht behandelt

Der Code prüft nur:

```text
write_result != -1
```

nicht aber:

```text
write_result == uart485SendLen
```

Ein theoretischer partieller Write würde daher als Erfolg behandelt und der restliche Puffer anschließend verworfen.

Auf einer lokalen seriellen Linux-Schnittstelle und bei den hier verwendeten Framegrößen dürfte dies selten sein, ist im Code aber nicht robust abgefangen.

### 15.5 Normaler RS485-Empfang läuft während OTA weiter

Für Mainboard-OTA wird der permanente UART-Empfangsthread nicht beendet oder grundsätzlich suspendiert.

`getDevParameter()` verarbeitet weiterhin eingehende Mainboardtelegramme. OTA-Adressen werden intern an ihre speziellen Handler geleitet; anderer Verkehr kann weiterhin den normalen Modbus-/MQTT-Pfad erreichen.

Damit ist bestätigt:

> Ein Mainboard-OTA schaltet den normalen RS485-RX/Warmlink-Uplink nicht grundsätzlich ab.

Noch offen ist die vollständige Klassifizierung aller konkurrierenden TX-Produzenten während eines aktiven C5A8-Transfers. Gerade wegen des Single-Slot-Puffers ist dies für die weitere Analyse relevant.

### 15.6 Konsequenz für den OTA-Pfad

Der Mainboard-OTA besitzt keinen separat geöffneten UART und keinen exklusiven OTA-TX-Kanal:

```text
C350/C357/C5A8/C36A/C375/... 
        ↓
uart485_send_data_to_board()
        ↓
gemeinsamer Sendeslot
        ↓
UART-Thread
        ↓
/dev/ttyHSL2
```

Für einzelne Handshake-Telegramme wie C350 ist diese Architektur überschaubar. Während eines vollständigen Firmwaretransfers mit vielen C5A8-Blöcken ist die genaue TX-Serialisierung mit normalem Warmlink-Verkehr dagegen ein wichtiger noch zu prüfender Punkt.

---

## 16. Nächste sinnvolle Zerlegung

Bereits separat detailliert dokumentiert sind inzwischen unter anderem:

- vollständige `board_ota_step`-State-Machine;
- C350/C357/C5A8/C371-Transferpfad;
- Resume über `/data/phnixIot_device_OTA_INFO`;
- C544-Resume-Erkennung;
- Cancel und Rollback;
- Board-seitiger IAP-/Copy-/Jump-Pfad.

Noch gezielt offen bzw. als nächstes sinnvoll:

- alle Schreiber auf `uart485WriteBuf` / `uart485SendFlag` klassifizieren und mögliche reale TX-Kollisionen bewerten;
- die OTA-Timer-/Retryfelder in `app @ 0x988FC` vollständig benennen und ihre Tickquelle bestimmen;
- Timeoutverhalten C350 ohne C36E, C357 ohne Folgeantwort sowie C5A8 ohne C371 exakt rekonstruieren;
- normalen MQTT-Downlink während aktivem OTA-Transfer auf mögliche Konkurrenz zum UART-Sendeslot untersuchen;
- DTU-Self-Update: externen Supervisor bestimmen, der `phnixIot4G` nach `killall -9` erneut startet.
