# PHNIX-OTA-Simulator auf der Offline-VM

Stand: 2026-08-23

## Zweck

Der Simulator bildet die vom lokalen OTA-Launcher benutzte ADB- und
Modemoberfläche nach. Er verändert weder das LTE-Modem noch die Wärmepumpe und
sendet keine RS485-Frames. Die kopierten Originaldateien auf der VM bleiben
unverändert; alle veränderlichen Simulatordaten liegen unter:

```text
/home/lte/.local/share/phnix-ota-simulator
```

Der Launcher selbst wird unverändert benutzt. Nur der mit `--adb` ausgewählte
Transport zeigt auf den Simulator.

## Installation auf der vorhandenen VM

Die eingerichteten Dateien liegen in:

```text
/home/lte/phnix-ota-lab
```

Die Kurzkommandos `phnix-ota-sim` und `phnix-sim-adb` sind in
`/home/lte/.local/bin` verlinkt.

## Start, Status, Reset und Stop

Simulator mit erfolgreichem Ablauf starten:

```sh
phnix-ota-sim start --scenario success
```

Status anzeigen:

```sh
phnix-ota-sim status
```

Definierten Ausgangszustand wiederherstellen:

```sh
phnix-ota-sim reset --scenario success
```

Simulator stoppen:

```sh
phnix-ota-sim stop
```

`stop` beendet einen eventuell laufenden Simulator-Helfer und setzt simulierte
Cloudsperre, Watchdogpause und HTTP-Server zurück. Es löscht keine Originaldaten
der VM.

## Preflight des Launchers

```sh
cd /home/lte/phnix-ota-lab

./phnix_local_ota_controller.py \
  --adb ./phnix-sim-adb \
  preflight \
  --firmware phnixIot_device_OTA.bin
```

## Vollständiger virtueller Updateablauf

```sh
cd /home/lte/phnix-ota-lab
phnix-ota-sim reset --scenario success

./phnix_local_ota_controller.py \
  --adb ./phnix-sim-adb \
  run \
  --firmware phnixIot_device_OTA.bin \
  --execute
```

Der Launcher führt dabei wirklich seine normalen Hostschritte aus:

1. Firmwaregröße und lokalen MD5 prüfen;
2. OTA_INFO und Statistik sichern;
3. Firmware mit dem simulierten `adb push` nach
   `/data/phnix_local_ota/FW3.3.bin` kopieren;
4. den MD5 der kopierten Datei prüfen;
5. die lokale HTTP-Bereitstellung prüfen;
6. das OTA-Kommando kopieren;
7. Phasen und CRC-validierten Fortschritt überwachen;
8. ausschließlich nach bestätigtem `board_ota_step == 12` Erfolg melden.

Der simulierte Zielpfad befindet sich physisch unter:

```text
/home/lte/.local/share/phnix-ota-simulator/root/data/phnix_local_ota
```

Auf dem echten LTE-Modem verwendet derselbe Launcher über echtes ADB den
tatsächlichen Pfad `/data/phnix_local_ota/FW3.3.bin`.

## Fehlerszenarien

Ein Szenario wird so ausgewählt:

```sh
phnix-ota-sim scenario crc-error
```

Verfügbar sind:

| Szenario | Simuliertes Ergebnis |
|---|---|
| `success` | vollständiger Transfer und bestätigter Step 12 |
| `parser-rejected` | Original-0033 wird abgelehnt; sichere Aufräumphase |
| `crc-error` | OTA_INFO-CRC wird während des Transfers ungültig |
| `metadata-mismatch` | falsche MD5-/Software-Metadaten vor C5A8 |
| `offset-backwards` | persistenter Offset läuft rückwärts |
| `offset-overflow` | Offset überschreitet Firmwarelänge |
| `stall-c350` | Timeout im ersten Handshake |
| `stall-c5a8` | Transferfortschritt bleibt stehen |
| `helper-exit` | Runtime-Helfer endet ohne terminalen Status |
| `success-without-step12` | falsche Erfolgsmeldung bei Board-Step 11 |

Bei allen nichtterminalen Fehlern muss der Launcher in `guarded-hold` enden.
`parser-rejected` ist dagegen ein sicherer terminaler Zustand und wird sauber
aufgeräumt.

## Gesamte Testmatrix

```sh
cd /home/lte/phnix-ota-lab
phnix-ota-sim start --scenario success

./run_simulator_matrix.py \
  --firmware phnixIot_device_OTA.bin

phnix-ota-sim stop
```

Am 2026-08-23 bestanden alle zehn Szenarien. Die Simulation deckte dabei zwei
Zeitfehler im Launcher auf, die anschließend korrigiert wurden:

- Der C5A8-Fortschritts-Timer wird nun erst beim Eintritt in C5A8 gestartet.
- Nach dem Ende des Runtime-Helfers wird ein unmittelbar zuvor geschriebener
  terminaler Status innerhalb einer kurzen Nachlesefrist noch akzeptiert.

## Grenze der Simulation

Der Simulator prüft Hostablauf, Kopieren, Zustandsüberwachung, Timeouts und
Fehlerbehandlung. Er emuliert nicht den ARM-Prozessor, GPIO, reale
GDB-Breakpoints oder das echte RS485-Mainboard. Diese dynamischen Eigenschaften
müssen weiterhin separat und möglichst sparsam am Originalgerät bestätigt
werden.
