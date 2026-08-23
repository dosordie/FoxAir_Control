# PHNIX/FoxAir LTE- und Mainboard-OTA – vollständige Workchat-Übergabe

Stand: 23. August 2026

Repository: `dosordie/FoxAir_Control`

Ausgangspunkt dieser Übergabe: Commit `43e7f264627b7f46af1fa577c9c62ce7484005ca`

## 1. Zweck dieser Datei

Diese Datei enthält den Arbeitsstand einer längeren Reverse-Engineering- und
Laboranalyse des PHNIX/FoxAir-LTE-/Warmlink-Systems. Ein neuer Workchat soll
damit auf einem anderen Computer ohne erneute Rekonstruktion weiterarbeiten
können.

Das langfristige Ziel ist:

> Eine noch nicht vorliegende, kompatible Mainboard-Firmware V3.4 kontrolliert
> auf die Wärmepumpe übertragen, ohne Cloudabhängigkeit und mit klaren
> Abbruch-/Recoverygrenzen.

**Nicht Bestandteil dieser Datei:** SSH-Adresse, Benutzername, Passwort,
ser2net-Zieladresse, Geräte-Credentials, SIM-/IMEI-/DeviceSecret-Werte und andere
Zugangsdaten. Der Besitzer stellt dem nächsten Workchat benötigte Zugänge
separat bereit.

## 2. Aktueller Gesamtstatus

Der LTE→Mainboard-Transport ist sowohl statisch als auch dynamisch weitgehend
verstanden:

- C350, C357 und C5A8 können bytegenau erzeugt werden.
- C36E und C371 können ausgewertet werden.
- Der komplette V3.3-Datenstrom mit 1712 C5A8-Blöcken wurde mit dem originalen
  ARM-Programm `phnixIot4G` in einer isolierten QEMU-Umgebung beobachtet.
- Ein unabhängiger Python-Sender erzeugt alle 1714 Requests bytegenau wie das
  Originalprogramm.
- Der Sender unterstützt TCP/ser2net und USB-RS485, öffnet aber standardmäßig
  keine Verbindung.
- Ein flashloser Boardsimulator validiert vollständige Transfers.
- Lokale und VM-interne TCP-Loopback-Volltransfers mit der echten V3.3-Datei
  waren erfolgreich.
- Die reale Wärmepumpe und die PHNIX-Cloud wurden bei der Entwicklung des
  unabhängigen Senders nicht kontaktiert.

Noch nicht gelöst:

- Eine echte, passende V3.4-Datei liegt nicht vor.
- Der residente Loader/Bootloader ab `0x08000000` wurde nicht gedumpt und nicht
  vollständig analysiert.
- Slot-Promotion, finaler Commit, Bootentscheidung und automatisches Rollback
  sind deshalb noch nicht vollständig abgesichert.
- Der unabhängige Sender stoppt absichtlich vor diesem Abschlussbereich.

## 3. Wichtigste Sicherheitsregel für die Fortsetzung

Ohne neue ausdrückliche Freigabe des Besitzers:

- nichts an die reale Wärmepumpe senden,
- keinen realen ser2net-/RS485-Endpunkt öffnen,
- nichts an die PHNIX-Cloud oder deren MQTT-Topics senden,
- keine Firmware auf Mainboard oder LTE-Modem flashen,
- keine Dateien auf dem LTE-Modem verändern,
- keine Prozesse auf dem LTE-Modem beenden oder neu starten.

Offline-Analyse, lokale Simulation, Hashprüfung, Vergleich mit vorhandenen
Captures und Tests in der isolierten Labor-VM sind der vorgesehene Standard.

Wichtig: Bereits der erste C5A8-Block wird vom echten Mainboard in den
OTA-Stagingbereich geschrieben. „Vor Status 5 stoppen“ bedeutet daher nicht,
dass bis dahin kein Flashbereich verändert wurde.

## 4. Untersuchte Artefakte

### 4.1 LTE-Programm

```text
Name:    phnixIot4G
Größe:   747440 Byte
MD5:     CDCF34DA5F039CEB1084DA835425F3A1
SHA256:  7C573431F0A67620D473419644A83A4F4DC04B8A91BDE5923C74A63BA1EAEDB7
Format:  ungestripptes ARM-ELF, 32 Bit, little endian
Entry:   0xA0C8
```

Das Programm ist nicht nur für Updates zuständig. Es enthält die gesamte
Kommunikation zwischen Wärmepumpe/Mainboard und Cloud:

- Warmlink-/RS485-Empfang und -Versand,
- transparente normale MQTT-Bridge,
- OTA für LTE-Anwendung und Mainboard,
- QMI/NAS/UIM- und SIMCom-Anbindung,
- Credential-HTTP,
- MQTT-Verbindung und Geräteauthentifizierung,
- lokale Statistik-, Fehler- und OTA-Persistenz.

### 4.2 V3.3-Mainboard-Firmware

Die echte Referenzdatei wurde vom Cache eines LTE-Modems gesichert und wird aus
Lizenz-/Gerätegründen nicht ins Repository eingecheckt.

```text
Dateigröße:       287598 Byte
MD5:              CEB6A4BF386FF644E23E410023E74673
SHA256:           6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
Softwarecode:     82400644
interne Version:  0033
Anzeigeversion:   V3.3
Initial SP:       0x2000EB90
Reset Handler:    0x080927D1
```

Die Zeichenfolge `824006440033` befindet sich bei Dateioffset `0x42780`.

### 4.3 OTA-Persistenzdatei

```text
/data/phnixIot_device_OTA_INFO
Größe: 220 Byte
```

Bekannter Originalzustand nach Wiederherstellung im Labor:

```text
SHA256: F5E31095C7366C4245A97F2EEAFEF76B2A4774405F589D0E8D5578A5B62136BB
```

Die Statistikdatei ist getrennt:

```text
/data/phnixIot_device_statisic
```

Sie enthält unter anderem die persistierte OTA-SSID. Für sie lag nach einem
frühen Labortest keine unveränderte Vor-Test-Kopie vor; deshalb wurde sie nicht
mit geratenen Daten überschrieben.

## 5. Cache-Lebenszyklus

Die Datei `/cache/phnixIot_device_OTA` wird nach einem erfolgreichen
Mainboard-Update nicht automatisch gelöscht. Deshalb lag die V3.3-Datei noch
auf dem LTE-Modem und konnte gesichert werden.

Erst ein später angenommenes Cloudkommando `0033` führt im LTE-Programm zu:

```text
alte Cachedatei löschen
OTA_INFO leeren
neuen Download beginnen
```

Die OTA-SSID wird davor bereits separat in der Statistikdatei persistiert.

## 6. Cloud- und MQTT-Erkenntnisse

Relevante Topics:

```text
Publish normal:  /<productKey>/<deviceName>/user/update
Subscribe normal:/<productKey>/<deviceName>/user/get
Publish OTA:     /<productKey>/<deviceName>/user/OTA_UPDATE
Subscribe OTA:   /<productKey>/<deviceName>/user/OTA_GET
```

Für Mainboard-Firmware:

```text
0003 = ausgehender Versionsbericht
0023 = ausgehende Upgrade-/Freigabemeldung, nicht Voraussetzung für 0003
0033 = eingehendes Firmwareangebot mit URL, MD5, Größe, Version und SSID
0053 = erfolgreicher Board-OTA-Abschluss, progress 100
0083 = endgültiger Fehler nach Wiederholungen
0093 = Downloadfehler
```

Der `0003`-Originaldatensatz des untersuchten Boards enthält:

```text
deviceSoftwareCode: 82400644
deviceSoftwareVer:  V3.3
ssid:               0063
```

Wichtig: `0033` ist die interne Softwareversion beziehungsweise der
OTA-Antwortcode in den jeweiligen Kontexten, aber nicht automatisch die SSID.
Die live bestätigte SSID des Boards lautet `0063`.

Kontrollierte aktive `0003`-Publishes wurden in einer früheren, ausdrücklich
freigegebenen Phase ausgeführt. Sie waren syntaktisch gültig, aber es wurde
keine `OTA_GET`-/`0033`-Antwort beobachtet. Damit wurde weder V3.4 noch eine
Download-URL angeboten. Wahrscheinlich muss ein Firmwarepaket serverseitig dem
Geräteprofil zugeordnet sein.

Die vollständige Firmware-URL ist nicht statisch im Binary vorhanden. Sie wird
von der Cloud als `param.otaFileDownloadAddr` geliefert und unverändert als
libcurl-URL verwendet. Der Boarddownload setzt keine eigenen HTTP-Authheader.

## 7. Exakte Bedingungen für den originalen `0003`-Report

Ein gültiges Mainboardframe auf Register C544 löst
`board_softcode_ver_handle()` aus. Der Handler schreibt die Boarddaten, erhöht
einen Pending-Zähler und legt einen 596-Byte-Snapshot in einer FIFO ab.

Der spätere Publish erfolgt nur, wenn:

1. die DTU-/Cloudinitialisierung vollständig ist (`dtu_run_step == 11`),
2. `board_ota_step != 3` gilt,
3. kein vorrangiger allgemeiner Geräteinfo-Upload ansteht,
4. mindestens ein Boardinfo-Ereignis pending ist,
5. ein passender FIFO-Datensatz vorhanden ist,
6. SIM/UIM und MQTT beim Publish betriebsbereit sind.

Weder `0023` noch `0033` oder ein anderes Cloudkommando ist Voraussetzung für
das Erzeugen von `0003`.

## 8. Live-Warmlink-Ergebnis

In einer ausdrücklich freigegebenen früheren Phase wurde einmalig der feste
FC03-Read auf Register `0x0004` gesendet. Die konkrete Netzwerkadresse wird hier
nicht dokumentiert.

Request:

```text
63 03 00 04 00 01 CD 89
```

Folge:

- acht 90-Register-Blöcke ab `03E9`, `0443`, `049D`, `04F7`, `0551`, `05AB`,
  `07D1`, `082B`,
- LTE-Modem quittierte jeden FC10-Block,
- etwa 49 Sekunden später reales C544,
- danach weitere 120 Sekunden keine RS485-Bytes und kein OTA-Start.

Reales C544:

```text
63 10 C5 44 00 0D 1A
00 63
38 32 33 30 30 33 31 34
30 30 30 30
38 32 34 30 30 36 34 34
30 30 33 33
CC F0
```

Dekodiert:

```text
SSID:             0063
Hardwarecode:     82300314
Hardwareversion:  0000
Softwarecode:     82400644
Softwareversion:  0033 / V3.3
```

LTE-Antwort C37B/status 7:

```text
63 10 C3 7B 00 02 04 00 63 00 07 B5 A8
```

Mainboard-ACK darauf:

```text
63 10 C3 7B 00 02 05 D7
```

Damit ist `0x0004` praktisch als Trigger für einen vollständigen
Device-Info-/Paketzyklus einschließlich späterem C544 bestätigt.

## 9. RS485-OTA-Protokoll

Grundparameter:

```text
Modbus RTU ähnlich
Slave:       0x63
Funktion:    0x10
Baudrate:    9600
Format:      8N1
CRC:         Modbus CRC16, Low-Byte zuerst auf dem Draht
Blockgröße:  standardmäßig 168 Byte
```

Vom LTE-Programm intern interpretierte Register:

| Register | Bedeutung |
|---:|---|
| `C350` | Ziel-Softwarecode und Zielversion |
| `C357` | Dateigröße und erwarteter MD5 |
| `C36C` | Abbruchbestätigung |
| `C36E` | Board-OTA-Status/Freigabe |
| `C371` | Block-ACK |
| `C378` | Rollback/Initialisierung |
| `C5A8` | Firmwaredatenblock |
| `C544` | laufende Boardcodes und Version |

### 9.1 C350

Layout:

```text
63 10 C3 50 00 07 0E
SSID_BE16
softwareCode ASCII[8]
version485 ASCII[4]
CRC_LO CRC_HI
```

V3.3 bytegenau:

```text
63 10 C3 50 00 07 0E 00 63
38 32 34 30 30 36 34 34
30 30 33 33
59 4D
```

Für V3.4 ist – bei unverändertem Softwarecode – `version485 = "0034"` zu
erwarten. Das muss mit der echten V3.4-Datei nochmals geprüft werden.

### 9.2 C357

Layout:

```text
63 10 C3 57 00 13 26
SSID_BE16
fileSize_BE32
MD5_ASCII_LOWERCASE[32]
CRC_LO CRC_HI
```

### 9.3 C36E

Board→LTE. Die echte V3.3-Mainboard-Firmware baut zwei Register beziehungsweise
vier Nutzbytes:

```text
SSID_BE16
status_BE16
```

Der LTE-Handler akzeptiert zusätzlich eine synthetische 6-Byte-Variante mit
optionaler Blockgröße in `data[4:5]`. Diese wurde im Labor verwendet, ist aber
kein behauptetes echtes Mainboard-Wireformat.

Statusbedeutung aus der Mainboard- und LTE-Analyse:

| Status | Bedeutung |
|---:|---|
| 1 | Upgrade erlaubt / Metadatenpfad fortsetzen |
| 2 | Transfer-/Handshake-Fortsetzung |
| 3 | Gesamtimage-MD5 erfolgreich |
| 4 | Gesamtimage-MD5 beziehungsweise Push fehlgeschlagen |
| 5 | späterer Commit-/Slot-/Handoff-Erfolg |
| 6 | Descriptor-/Copy-/Upgradefehler |

Status 3 ist ein Erfolgspfad und kein Fehler. Status 5 bedeutet nicht lediglich
„MD5 OK“, sondern tritt erst später auf.

### 9.4 C5A8

Bei Blockgröße 168:

```text
63 10 C5 A8 00 57 A8
SSID_BE16
total_blocks_BE16
current_block_BE16
firmware_data[168]
CRC_LO CRC_HI
```

Die Quantity berücksichtigt die sechs Headerbytes und die Firmwaredaten. Das
Bytecount-Feld enthält in diesem proprietären Profil nur die Länge der
Firmwaredaten.

Der letzte Block wird mit `0xFF` auf die volle Blockgröße aufgefüllt.

### 9.5 C371

Board→LTE:

```text
SSID_BE16
ackA_BE16       erwartet 1
ackB_BE16       1 = weiterer Block, 2 = letzter Block
ackBlock_BE16
```

Der echte Mainboardpfad sendet am letzten Block `ackB=2`. Dadurch setzt das
LTE-Modem den persistenten Offset direkt auf `fileSize`.

## 10. V3.3-Finalblock und Offsetkorrektur

```text
Blockzahl:                 1712
offset_before letzter:     287448
reale Bytes letzter Block: 150
Padding:                   18 × FF
```

Ein absichtlicher LTE-Handler-Grenztest verwendete auch am letzten Block
`ackB=1`:

```text
offset_after_ack = 287448 + 168 = 287616
```

Das war ein synthetischer Boundary-Test. Im echten normalen Mainboardpfad gilt:

```text
finales ackB=2
persistierter Endoffset = fileSize = 287598
```

Die Werte 287616 und 287598 dürfen nicht als widersprüchliche Ergebnisse
vermischt werden.

## 11. Mainboard-Flashpfad aus V3.3

Wesentliche statische Erkenntnisse:

- C350 vergleicht Ziel- und laufende Firmwareidentität.
- C357 akzeptiert maximal `0x4B000` Byte und übernimmt Länge/MD5.
- C5A8-Daten werden in einen Stagingpfad um `0x080A1000` geschrieben.
- C371 wird erst nach erfolgreichem Commit des jeweiligen Blocks gesendet.
- Duplicate-Blöcke können erneut quittiert werden, ohne nochmals zu flashen.
- Nach dem letzten Block wird der gesamte Stagingbereich per MD5 geprüft.
- MD5 erfolgreich führt zu C36E/status 3, MD5-Fehler zu status 4.
- Danach folgen Descriptor-CRC, Copy-/Slotpfade und eine zweite MD5-Prüfung
  eines Bereichs ab `0x08050000`.
- Ein späterer erfolgreicher Commit-/Handoff-Pfad führt zu C36E/status 5.
- Schließlich existieren direkte Chain-Jumps zum residenten Loaderbereich ab
  `0x08000000` beziehungsweise zu `0x08050000`.

Der Loader selbst ist nicht Teil der analysierten V3.3-Datei. Deshalb bleibt
ein echter vollständiger OTA bis zur Loader-/Recoveryanalyse riskant.

## 12. Isolierte Laborumgebung

Das originale ARM-Programm wurde in einer Linux-VM unter QEMU ausgeführt.
Innerhalb des Test-Namespace gab es nur Loopback und keine IPv4-/IPv6-
Defaultroute.

Lokale Ersatzdienste emulierten:

- SIMCom-AT,
- QMI/QMUX/NAS/UIM,
- Credential-HTTP,
- TLS/MQTT,
- Firmware-HTTP,
- Mainboard-RS485 über PTY.

Damit lief der originale OTA-Codepfad, ohne reales LTE-Modem, reales Mainboard
oder echte Cloud zu kontaktieren.

Der nächste Workchat bekommt VM-/SSH-Zugang separat vom Besitzer. Übliche
Laborstruktur in der VM:

```text
/opt/phnix-lab/rootfs
/opt/phnix-lab/tools
/opt/phnix-lab/fixtures
/opt/phnix-lab/logs
/opt/phnix-lab/state
```

V3.3-Fixture in der bisherigen VM:

```text
/opt/phnix-lab/fixtures/phnixIot_device_OTA.v3.3
```

Vor Verwendung immer Größe und beide Hashes erneut prüfen.

## 13. Dynamische Originalprogramm-Validierung

Kontrollierter Downloadtest des originalen `phnixIot4G`:

```text
C350
 -> synthetische Bestätigung
 -> C36E/status 1
C357
 -> synthetische Bestätigung
 -> C36E/status 2
 -> lokaler HTTP-Download
 -> MD5-Prüfung
 -> board_ota_step 6
```

Der erste Lauf stoppte unmittelbar vor dem ersten C5A8.

Im vollständigen Lauf:

```text
C5A8-Frames:              1712
rekonstruierte Nutzbytes: 287598
SHA256:                   6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Der Guard stoppte vor dem Übergang in die Abschlussphase. Im Emulator wurden
kein C36E/status 5, kein C37B-Abschluss, kein MQTT-0053 und kein Neustart oder
Flashen ausgeführt.

## 14. Unabhängiger Python-Sender

Datei:

[`devtools/phnix_ota_sender.py`](../../devtools/phnix_ota_sender.py)

Funktionen:

- `plan`: nur Firmware und Frames planen, garantiert ohne Transport,
- `simulate`: vollständige interne Rekonstruktion ohne Transport,
- `compare-capture`: alle erzeugten Requests mit einem Originalcapture
  bytegenau und in Reihenfolge vergleichen,
- `send`: gesperrter Live-Modus für TCP/ser2net oder USB-RS485.

Schutzmechanismen:

- ohne `send` kein physischer I/O-Codepfad,
- SHA-256-basierte Freigabephrase erforderlich,
- im Live-Modus sind erwarteter MD5 und Dateigröße Pflicht,
- Standard-Livegrenze ist `--stop-after handshake`, also kein C5A8,
- C5A8 erfordert zusätzlich `--stop-after data`,
- Fail-fast bei CRC-, SSID-, Status-, ACK-Art- oder Blocknummerfehler,
- vollständiges JSONL-Protokoll,
- kein C37B/status-3-/status-5-ACK nach Ende der Datenphase.

Die Freigabephrase wird von `plan` ausgegeben und besitzt das Format:

```text
PHNIX-LIVE-TRANSFER-<SHA256-DER-FIRMWARE>
```

### 14.1 Boardsimulator

[`devtools/phnix_ota_board_simulator.py`](../../devtools/phnix_ota_board_simulator.py)

- bindet ausschließlich an Loopback,
- besitzt keinen Flash-, MQTT-, HTTP- oder Serial-Code,
- validiert C350, C357 und jeden C5A8-Block,
- rekonstruiert die Firmware,
- sendet C371/`ackB=1` beziehungsweise final `ackB=2`,
- erzeugt kein C37B.

### 14.2 Tests

[`tests/test_phnix_ota_sender.py`](../../tests/test_phnix_ota_sender.py)

Aktuell elf gezielte Tests für:

- Versionsumwandlung `V3.4 -> 0034`,
- bekanntes exaktes V3.3-C350,
- C357-Größe/MD5,
- CRC und Frameparser,
- fragmentierte TCP-/Serial-Eingänge,
- vollständige Firmware-Rekonstruktion,
- Final-Padding,
- `ackB=2` nur am letzten Block,
- vollständige simulierte Zustandsmaschine,
- Defaultstopp vor dem ersten C5A8,
- USB-RS485 mit 9600/8N1, Flush, Read und Close.

Testkommando:

```text
python -m unittest tests.test_phnix_ota_sender -v
```

## 15. Validierung des unabhängigen Senders

### 15.1 Vergleich mit dem Originalprogramm

Ein vorhandener Rohmitschnitt des originalen `phnixIot4G` aus der VM wurde mit
dem unabhängigen Sender verglichen:

```text
Capturegröße:             313382 Byte
erwartete Requests:       1714
                          C350 + C357 + 1712 × C5A8
bytegenau gefunden:       1714
erstes Match:             Offset 16
letztes Match:            Offset 313199
Ende des letzten Frames:  Offset 313382
Ergebnis:                 alle bytegenau und in Originalreihenfolge
```

Der Capture selbst wird nicht ins Repository eingecheckt. Der Besitzer oder die
Labor-VM kann ihn dem neuen Workchat bei Bedarf bereitstellen.

### 15.2 TCP-End-to-End

Der vollständige Sender wurde lokal und anschließend nochmals innerhalb der
Labor-VM über einen echten TCP-Loopback-Socket gegen den Boardsimulator
ausgeführt:

```text
Sender-Rückgabecode:       0
Simulator-Rückgabecode:    0
JSONL-Ereignisse:          3431
Blöcke:                    1712
rekonstruierte Bytes:      287598
MD5/SHA256:                exakt wie V3.3-Fixture
finales ACK:               ackB=2
C37B erzeugt:              nein
```

Ein Sperrtest mit falscher Freigabephrase endete mit Rückgabecode 3, bevor ein
Socket geöffnet oder eine Logdatei angelegt wurde.

## 16. QMI/NAS/UIM-Kurzstand

Diese Erkenntnisse waren nötig, um das Originalprogramm vollständig isoliert
starten zu können:

- NAS-Indication-Callbacks treiben den produktiven Zustand nicht.
- Registration-State stammt aus einem synchronen 5-Sekunden-Poll von NAS
  Message `0x24`.
- produktiver Serving-System-Cache: `0x981B4`.
- `process_simcom_ind_message()` ist in diesem Build nur ein Debug-Stub.
- UIM `0x2F` und eine vorhandene READY-USIM waren Teil der Startvoraussetzungen.
- Die reale SIM war per AT `CPIN: READY`; SIM-Identitäten werden hier bewusst
  nicht dokumentiert.

Die minimal erforderlichen QMI-Antworten, Clientinitialisierung und
Serving-Systemlayouts sind in den verlinkten QMI-Dokumenten vollständig
beschrieben.

## 17. Normale RS485-/Cloudbridge und Watchdog

`phnixIot4G` dekodiert nur acht spezielle OTA-/Service-Register semantisch.
Normale Warmlink-FC10-Frames werden binär auf `/user/update` publiziert und lokal
quittiert.

Bekannte feste Reads:

```text
0x0004 = Device-Info-/Paketzyklus nach erfolgreicher MQTT-Initialisierung
0x0006 = Check485Statue-Watchdogprobe
0x07D1 / 90 Register = Geräteidentitäts-/Infoblock
```

`0x0006` wird nach etwa 300 Sekunden höherwertiger Service-Inaktivität ungefähr
alle 20 Sekunden als Probe gesendet.

Fehlerstatus:

```text
Bit 6  = länger als 420 s kein Frame von Slave 0x63
Bit 12 = länger als 420 s kein CRC-gültiges Frame
Bit 5  = länger als 420 s kein erwartetes höherwertiges Board-Serviceevent;
         0x0006 wird vorher aktiv als Probe gesendet
```

## 18. Realistische Wege zu V3.4

Die Übertragung ist inzwischen besser verstanden als die Beschaffung der Datei.
Sinnvolle Quellen, in dieser Reihenfolge:

1. Cachedatei eines kompatiblen LTE-Modems nach einem erfolgreichen V3.4-Update
   rein lesend sichern.
2. Dazu möglichst auch ursprüngliche `0033`-Metadaten beziehungsweise
   `OTA_INFO` dokumentieren.
3. Serverseitige Firmwarezuweisung über Hersteller/Installateur klären.
4. Weitere kontrollierte Cloudtests nur nach neuer ausdrücklicher Freigabe und
   mit garantiert isoliertem realem `phnixIot4G`.

Für eine fremde V3.4-Datei werden mindestens benötigt:

```text
Firmwaredatei
Dateigröße
MD5
SHA256
softwareCode
softwareVer
SSID beziehungsweise ursprüngliche OTA-Metadaten
Board-/Hardwarevariante des Quellgeräts
```

Vor jeder Verwendung prüfen:

- `softwareCode` muss zur Zielplatine passen,
- Vektortabelle und Imagebasis müssen plausibel sein,
- Versionstring muss zum erwarteten `0034` passen,
- kein Delta-/Teilimage,
- Boardhardware und Produktserie müssen kompatibel sein,
- V3.3↔V3.4-Diff auf neue Header, Descriptoren oder Flashbereiche prüfen.

## 19. Recovery vor einem echten V3.4-Lauf

Vor dem ersten C5A8 an ein echtes Mainboard sollten vorliegen:

1. vollständiger Dump des aktuell laufenden Mainboard-Flashs,
2. insbesondere Dump/Analyse des Loaderbereichs ab `0x08000000`,
3. verifizierter SWD/JTAG- oder anderer Hardware-Recoveryweg,
4. stabile Spannungsversorgung,
5. sichere Trennung anderer Busmaster, insbesondere des LTE-Modems,
6. passiver Mitschnitt des gesamten Vorgangs,
7. geprüfte V3.4-Hashes und Boardkompatibilität.

Ein echter V3.3-Reflash auf dem bereits mit V3.3 laufenden Board ist kein guter
Probelauf: C350 kann gleiche Zielidentität ablehnen oder einen Sonderpfad wählen,
und der Versuch erzeugt unnötiges Flashrisiko.

## 20. Empfohlener Fortsetzungsplan für den neuen Workchat

### Phase A – Umgebung nachvollziehen

1. Repository klonen und mindestens Commit `43e7f26` verifizieren.
2. Aktuellen `main`-Stand prüfen; keine fremden Änderungen überschreiben.
3. Vom Besitzer separat VM-Zugang und bei Bedarf lokale Artefaktpfade erhalten.
4. V3.3-Fixture anhand Größe, MD5 und SHA-256 prüfen.
5. Elf Sender-Tests ausführen.
6. `simulate` und `compare-capture` erneut ausführen.

### Phase B – V3.4 beschaffen und offline analysieren

1. V3.4 nur rein lesend übernehmen.
2. Hashes und Herkunft dokumentieren.
3. Binaryaufbau mit V3.3 vergleichen.
4. Software-/Hardwarecode und interne Version belegen.
5. Sender zunächst ausschließlich mit `plan` und `simulate` testen.
6. Erzeugte V3.4-Frames in der VM gegen das Originalprogramm validieren.

### Phase C – Loader und Recovery

1. Loaderdump sichern.
2. Boot-/Slot-/Rollbacklogik rekonstruieren.
3. Hardware-Recovery praktisch testen, bevor OTA versucht wird.
4. Status-3→Status-5- und C37B-Abschlussunterstützung erst danach ergänzen.

### Phase D – späterer echter Test, nur mit neuer Freigabe

1. Busmaster trennen und nur passiv verbinden.
2. Optional ausschließlich C350/C357-Handshakestufe testen; Standardgrenze des
   Senders sendet noch keinen C5A8-Block.
3. Ergebnis und Boardstatus prüfen.
4. Für C5A8 separate Freigabe einholen.
5. Datenphase lückenlos protokollieren.
6. Bei jeder Abweichung sofort stoppen; keine automatischen Retries erzwingen.
7. Abschlussphase status 3/5 erst nach Loaderfreigabe.

## 21. Mögliche Windows-Anwendung als zweiter Schritt

Der Python-Protokollkern ist von einer Oberfläche getrennt. Eine spätere
PySide6-/Windows-EXE sollte mindestens folgende Gates besitzen:

1. Firmware auswählen und Hash/Boardprofil anzeigen,
2. Offline-Simulation zwingend erfolgreich abschließen,
3. TCP oder USB-RS485 auswählen,
4. Verbindung zunächst ausschließlich passiv testen,
5. C350/C357 und C5A8 als getrennte Freigabestufen,
6. gut sichtbares Rohbyte-/Statusprotokoll mit Export,
7. Status-3-/Status-5-/C37B-Pfad separat gesperrt,
8. keine gespeicherten Zugangsdaten in Programm oder Log.

## 22. Wichtigste Repository-Dateien

### Einstieg und Gesamtsicht

- [`PHNIX_phnixIot4G_RE.md`](PHNIX_phnixIot4G_RE.md)
- [`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md)
- [`FW3.3-OTA-ERKENNTNISSE.md`](FW3.3-OTA-ERKENNTNISSE.md)

### Sender und Tests

- [`../../devtools/phnix_ota_sender.py`](../../devtools/phnix_ota_sender.py)
- [`../../devtools/phnix_ota_board_simulator.py`](../../devtools/phnix_ota_board_simulator.py)
- [`../../tests/test_phnix_ota_sender.py`](../../tests/test_phnix_ota_sender.py)
- [`../HowTo/phnix_ota_sender.md`](../HowTo/phnix_ota_sender.md)

### OTA-Protokoll und Zustände

- [`PHNIX_phnixIot4G_ota_full_path.md`](PHNIX_phnixIot4G_ota_full_path.md)
- [`PHNIX_phnixIot4G_0033_handler_breakpoint.md`](PHNIX_phnixIot4G_0033_handler_breakpoint.md)
- [`PHNIX_phnixIot4G_0033_to_board_bin_transfer.md`](PHNIX_phnixIot4G_0033_to_board_bin_transfer.md)
- [`PHNIX_phnixIot4G_ota_rs485_frames.md`](PHNIX_phnixIot4G_ota_rs485_frames.md)
- [`PHNIX_phnixIot4G_board_is_allow_upg_handle.md`](PHNIX_phnixIot4G_board_is_allow_upg_handle.md)
- [`PHNIX_phnixIot4G_board_ota_state_machine.md`](PHNIX_phnixIot4G_board_ota_state_machine.md)
- [`PHNIX_phnixIot4G_board_ota_completion.md`](PHNIX_phnixIot4G_board_ota_completion.md)
- [`PHNIX_phnixIot4G_board_ota_http_download.md`](PHNIX_phnixIot4G_board_ota_http_download.md)
- [`PHNIX_phnixIot4G_ota_persistence.md`](PHNIX_phnixIot4G_ota_persistence.md)
- [`PHNIX_phnixIot4G_ota_cancel_rollback_restart.md`](PHNIX_phnixIot4G_ota_cancel_rollback_restart.md)
- [`PHNIX_phnixIot4G_C544_softcode_resume.md`](PHNIX_phnixIot4G_C544_softcode_resume.md)

### MQTT, normale Bridge und Identität

- [`PHNIX_phnixIot4G_mqtt_connect_exact.md`](PHNIX_phnixIot4G_mqtt_connect_exact.md)
- [`PHNIX_phnixIot4G_mqtt_runtime_corrections.md`](PHNIX_phnixIot4G_mqtt_runtime_corrections.md)
- [`PHNIX_phnixIot4G_tls_mqtt_trust.md`](PHNIX_phnixIot4G_tls_mqtt_trust.md)
- [`PHNIX_phnixIot4G_normal_mqtt_bridge.md`](PHNIX_phnixIot4G_normal_mqtt_bridge.md)
- [`PHNIX_phnixIot4G_uart_provisioning.md`](PHNIX_phnixIot4G_uart_provisioning.md)
- [`PHNIX_phnixIot4G_device_identity_block.md`](PHNIX_phnixIot4G_device_identity_block.md)
- [`PHNIX_phnixIot4G_rs485_runtime.md`](PHNIX_phnixIot4G_rs485_runtime.md)
- [`PHNIX_phnixIot4G_error_status.md`](PHNIX_phnixIot4G_error_status.md)

### QMI/NAS

- [`PHNIX_phnixIot4G_qmi_nas.md`](PHNIX_phnixIot4G_qmi_nas.md)
- [`PHNIX_phnixIot4G_qmi_nas_followup.md`](PHNIX_phnixIot4G_qmi_nas_followup.md)
- [`PHNIX_phnixIot4G_qmi_data_path.md`](PHNIX_phnixIot4G_qmi_data_path.md)
- [`PHNIX_phnixIot4G_nas_serving_system_layout.md`](PHNIX_phnixIot4G_nas_serving_system_layout.md)
- [`PHNIX_phnixIot4G_qmi_minimal_responses.md`](PHNIX_phnixIot4G_qmi_minimal_responses.md)
- [`PHNIX_phnixIot4G_qmi_client_init.md`](PHNIX_phnixIot4G_qmi_client_init.md)

### VM-Laborwerkzeuge

- [`../../devtools/phnix_ota_lab/README.md`](../../devtools/phnix_ota_lab/README.md)

Der später erweiterte Runner `run_offline_lab.sh` und die vollständigen
Laufzeitlogs liegen in der bisherigen Labor-VM unter `/opt/phnix-lab`; der
Runner ist im aktuellen Repositorystand noch nicht eingecheckt. Vor einer
Übernahme zuerst auf Zugangsdaten und gerätespezifische Inhalte prüfen.

## 23. Informationen, die der neue Workchat vom Besitzer separat benötigt

Je nach nächstem Schritt:

- SSH-/VM-Zugang,
- Pfad oder Kopie der V3.3-Fixture,
- gegebenenfalls Original-RS485-Capture,
- später eine V3.4-Datei samt Herkunft und Metadaten,
- erst bei ausdrücklich freigegebenem Hardwaretest den realen RS485-/ser2net-
  Endpunkt,
- Auskunft über vorhandenen SWD/JTAG-/Recoveryzugang.

Diese Angaben gehören nicht in öffentliche GitHub-Dateien oder Logs.

## 24. Kurzfazit für den übernehmenden Workchat

Nicht erneut bei null beginnen. Die LTE-Transportseite ist bereits sehr stark
belegt und der unabhängige Sender stimmt bytegenau mit dem Original überein.

Der nächste höchste Erkenntnisgewinn liegt bei:

1. Beschaffung und Offlineprüfung einer echten V3.4,
2. Dump und Analyse des residenten Mainboard-Loaders,
3. praktisch geprüftem Recoveryweg,
4. erst danach Erweiterung des Senders über die aktuelle sichere Grenze nach
   finalem C371/`ackB=2` hinaus.

Bis dahin sind `plan`, `simulate`, `compare-capture` und der Loopback-
Boardsimulator die sicheren Arbeitsmittel.
