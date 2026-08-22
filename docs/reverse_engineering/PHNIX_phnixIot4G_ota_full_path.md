# PHNIX `phnixIot4G` – OTA-/Firmware-Update-Pfad

Stand: 2026-08-22

Grundlage ist die statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`. Diese Datei konzentriert sich auf die Firmware-Update-Logik für **DTU/LTE-Modul** und **Mainboard**.

## Kurzfazit

`phnixIot4G` besitzt zwei getrennte OTA-Pfade:

```text
DTU-Self-Update
MQTT OTA_GET -> JSON Code 0032 -> URL/MD5/Size übernehmen
 -> HTTP/curl Download nach /data/phnixIot4G_OTA
 -> Dateigröße + MD5 prüfen
 -> chmod +x
 -> mv auf /data/phnixIot4G
 -> killall -9 phnixIot4G
```

und:

```text
Mainboard-Update
MQTT OTA_GET -> JSON Code 0033 -> URL/MD5/Size/SSID übernehmen
 -> HTTP/curl Download nach /cache/phnixIot_device_OTA
 -> Dateigröße + MD5 prüfen
 -> Metadaten persistent speichern
 -> Mainboard-OTA-State-Machine
 -> RS485 OTA-Register C350/C357/C36C/C36E/C371/C378/C5A8/C544
```

Die beiden Pfade teilen MQTT/JSON-Dispatcher und Download-/Progress-Infrastruktur, sind danach aber klar getrennt.

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
Soll-Dateigröße
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
DTU Progress      0042
Mainboard Progress 0043
```

---

## 5. DTU-Dateiprüfung

Nach erfolgreichem Download wird `ota_check_dtu_otaFile_md5()` aufgerufen.

Die Funktion prüft zwei Dinge:

```text
1. tatsächliche Dateigröße gegen otaDtuInfo.fileSize
2. berechnetes MD5 gegen otaDtuInfo.fileMD5
```

Die MD5-Implementierung liegt im Executable (`MD5Init`, `MD5Update`, `MD5Final`).

Es gibt in diesem PHNIX-DTU-Pfad **keine zusätzlich erkannte RSA-/Signaturprüfung des heruntergeladenen Binaries**. Die Integritätsentscheidung beruht hier auf Größe + MD5.

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

Der Neustart erfolgt damit offenbar über den Plattform-/Supervisor-Mechanismus, der `phnixIot4G` erneut startet.

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

## 9. Mainboard-Firmwaredownload

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

Auch hier gelten:

```text
Dateigröße muss stimmen
MD5 muss stimmen
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

Die Board-State-Machine verwendet unter anderem `board_ota_step`.

Bekannte Schritte/Aktionen:

```text
Version des Mainboards melden
OTA-Erlaubnis vom Mainboard/Cloud abstimmen
Firmware per HTTP herunterladen
MD5 prüfen
OTA-Metadaten per RS485 senden
Firmwareblöcke übertragen
Fortschritt melden
Cancel behandeln
Rollback behandeln
Erfolg/Fehler melden
```

Cloud-Kommandos `0062` und `0063` setzen lediglich Flags für ein erneutes Versionsreporting; sie starten nicht direkt einen Download.

---

## 12. Mainboard-RS485-OTA-Register

Der bereits rekonstruierte `unpack_mcu_modbus()` behandelt exklusiv diese OTA-/Serviceadressen:

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

Damit sind Mainboard-OTA und normaler Modbusbetrieb logisch klar getrennt.

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
Download-Integrität: Dateigröße + MD5
separate Firmware-Signaturprüfung im PHNIX-DTU-Pfad: nicht gefunden
```

Das bedeutet nicht automatisch, dass der reale Cloudprozess unsicher ist; die Download-URL kann serverseitig geschützt/signiert sein. Im Client selbst ist für das heruntergeladene DTU-ELF jedoch keine zusätzliche kryptografische Signaturvalidierung sichtbar.

Beim Mainboard-Image ist ebenfalls Größe + MD5 die erkennbare lokale Downloadprüfung; weitere Validierungen können zusätzlich im Mainboard-Bootloader/Firmwarepfad stattfinden und sind nicht Bestandteil dieses ELF.

---

## 15. Nächste sinnvolle Zerlegung

Noch gezielt offen:

- exaktes `otaDtuInfo`- und `otaDeviceInfo`-Structlayout mit allen Offsets;
- vollständige `board_ota_step`-State-Tabelle aus `dtu_upgrade_pro()`;
- exakte RS485-Payloads für C350/C357/C36E/C371/C5A8;
- Resume-Logik über `/data/phnixIot_device_OTA_INFO` und `offset/down_cnt`;
- genaue Entscheidung, wann Mainboard-Blöcke erneut gesendet werden;
- DTU-Self-Update: exakter Verhalten nach `killall` und welcher externe Supervisor neu startet.
