# Lokaler PHNIX-OTA-Launcher – einfache Bedienung

Stand: 2026-08-23

## Wichtiger Status

Der Launcher ist ein **experimentelles Laborwerkzeug** für genau den geprüften
Build von `phnixIot4G`. Vorprüfungen, Dienst-Restart, Debugger-Attach und alle
benötigten Breakpoints wurden auf dem realen LTE-Modem getestet. Ein aktiver
Firmwaretransfer an ein echtes Mainboard wurde mit diesem Launcher noch nicht
ausgeführt.

Der aktive Modus darf erst verwendet werden, wenn:

- eine ruhige RS485-Phase bestätigt ist;
- stabile Stromversorgung besteht;
- ein Bediener den gesamten Vorgang überwacht;
- für einen nichtterminalen Fehler ein Recoveryplan vorhanden ist.

Der Launcher besitzt absichtlich keinen automatischen, unbestätigten Cancel.
Bei einem nichtterminalen Fehler hält er Dienst, Cloud und Watchdogs in einem
geschützten Zustand an, statt unkontrolliert in den Normalbetrieb zurückzugehen.

## Dateien

- `tools/phnix_ota/phnix_local_ota_controller.py`: Bedienung auf dem Raspberry Pi
- `tools/phnix_ota/phnix_ota_runtime_hook`: buildgebundener Helfer auf dem LTE-Modem

## 1. Dateien auf den Raspberry Pi kopieren

Auf dem Pi müssen folgende Dateien liegen:

```text
phnix_local_ota_controller.py
phnix_ota_runtime_hook
FW3.3.bin
```

Die erwartete Firmware besitzt:

```text
Größe: 287598 Byte
MD5:   CEB6A4BF386FF644E23E410023E74673
```

## 2. Runtime-Helfer vorübergehend installieren

```sh
adb push phnix_ota_runtime_hook /data/phnix_ota_runtime_hook
adb shell chmod 755 /data/phnix_ota_runtime_hook
```

Der Helfer akzeptiert ausschließlich den verifizierten Originaldienst mit:

```text
Build-ID: af4dcae12639bedce833ee5efa5da009777b6319
SHA-256:  7c573431f0a67620d473419644a83a4f4dc04b8a91bde5923c74a63ba1eaedb7
```

## 3. Nur lesende Vorprüfung

```sh
python3 phnix_local_ota_controller.py preflight --firmware FW3.3.bin
```

Erwartetes Ergebnis:

- `ok: true`
- ADB-Zustand `device`
- Originaldienst läuft
- Service-SHA stimmt
- zwei `helloworld`-Watchdogs werden erkannt
- OTA_INFO-CRC ist gültig
- `offset == 0` und `length == 0`
- genügend Platz in `/data` und `/cache`

## 4. Ungefährliche Debuggertests

Nur Attach, Threadliste und sofortiges Detach:

```sh
adb shell /data/phnix_ota_runtime_hook attach-test
```

Alle benötigten Breakpoints im angehaltenen Prozess setzen und sofort wieder
entfernen:

```sh
adb shell /data/phnix_ota_runtime_hook breakpoint-test
```

Diese Tests injizieren kein `0033` und senden keine OTA-Frames.

## 5. Kompletter Trockenlauf

```sh
python3 phnix_local_ota_controller.py run --firmware FW3.3.bin
```

Ohne `--execute` werden weder Modem- noch Buszustand verändert.

## 6. Aktiver Start – noch nicht für unbeaufsichtigte Nutzung

```sh
python3 phnix_local_ota_controller.py run \
  --firmware FW3.3.bin \
  --execute
```

Der Ablauf:

1. sichert OTA_INFO und Statistik auf dem Pi;
2. kopiert die geprüfte Firmware per USB auf das Modem;
3. stellt sie lokal über `127.0.0.1:8081` bereit;
4. blockiert MQTT auf `rmnet_data0`, Port 1883;
5. pausiert beide `helloworld`-Watchdogs;
6. verwendet `gdbserver`, der alle 13 Threads erkennt;
7. erlaubt während `launcher_armed` nur den Run-Step-Override `7 -> 11`;
8. aktiviert die Publish-Stubs erst nach akzeptiertem Original-`0033`;
9. bestätigt lokal ausschließlich `0023`, `0053` und `0083`;
10. überwacht CRC, Metadaten, Offset und Phasenzeit;
11. beendet den Hook erst nach dem echten terminalen Übergang auf
    `board_ota_step == 12`.

## 7. Guarded Hold

Bei CRC-Fehler, falschen Metadaten, rückwärts laufendem Offset, Timeout oder
unerwartetem Helper-Ende wird nicht automatisch aufgeräumt. Der Status lautet:

```json
{"phase":"guarded-hold","terminal":false,"recovery_required":true}
```

Dann gelten folgende Regeln:

- LTE-Modem und Wärmepumpe nicht stromlos machen;
- nicht unüberlegt `stop --force` verwenden;
- Cloud-Sperre und pausierte Watchdogs zunächst bestehen lassen;
- Zustand von Mainboard, OTA_INFO und Bus auswerten;
- einen bestätigten Cancel `C36A -> C36C Status 1` oder einen anderen bewusst
  gewählten Recoveryweg durchführen.

`stop --force` ist nur ein manueller Notausgang. Er beweist keinen sicheren
Cancel und darf deshalb nicht Bestandteil eines automatischen Ablaufs sein.

## 8. Status lesen

```sh
python3 phnix_local_ota_controller.py status
```

Während C5A8 zählt nur der CRC-validierte persistente OTA_INFO-Offset als
bestätigter Fortschritt.

## 9. Laborartefakte wieder entfernen

Nur nach einem sicheren terminalen Zustand oder wenn kein aktiver OTA gestartet
wurde:

```sh
adb shell rm -f /data/phnix_ota_runtime_hook
adb shell rm -rf /data/phnix_local_ota /tmp/phnix_ota_hook
adb shell rm -f /tmp/phnix_ota_status.json
```

Danach prüfen:

```sh
adb shell pidof phnixIot4G
adb shell cat /proc/$(adb shell pidof phnixIot4G)/status
adb shell netstat -nt
adb shell netstat -lnt
adb shell iptables -S INPUT
adb shell iptables -S OUTPUT
```

Erwartet werden `TracerPid: 0`, zwei laufende Watchdogs, eine wiederhergestellte
Cloudverbindung, kein Listener auf Port 8081 und keine OTA-Regel für Port 1883.
