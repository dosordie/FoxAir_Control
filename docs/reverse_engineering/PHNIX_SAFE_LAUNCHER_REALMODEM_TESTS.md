# PHNIX Safe-Launcher – Tests auf dem realen LTE-Modem

Stand: 2026-08-23

Es wurde kein aktiver Mainboard-OTA gestartet und kein OTA-Frame absichtlich
auf den RS485-Bus gesendet.

## Identität des Originaldienstes

```text
Architektur: ARMv7 / 32 Bit
Build-ID:    af4dcae12639bedce833ee5efa5da009777b6319
SHA-256:     7c573431f0a67620d473419644a83a4f4dc04b8a91bde5923c74a63ba1eaedb7
Threads:     13
```

Die vom Modem gelesene Binary war byteidentisch zur analysierten Datei.

## Supervisor

Auf dem Modem laufen zwei parallele Prozesse:

```text
/bin/sh /data/helloworld
```

Sie prüfen den Originaldienst ungefähr alle fünf Sekunden. Der Dienst war Kind
einer dieser Schleifen. Ein kontrollierter Stop führte nach ungefähr zwei
Sekunden zu einem neuen `phnixIot4G`-Prozess. Anschließend bestanden wieder:

- 13 Threads;
- `TracerPid: 0`;
- beide ursprünglichen Watchdog-Prozesse;
- eine aktive MQTT-Verbindung.

Die Cloud-IP wechselte beim Neuverbinden. Eine Sperre darf daher nicht an eine
einzelne Ziel-IP gebunden sein. Der Launcher sperrt stattdessen TCP-Port 1883
auf `rmnet_data0` in beide Richtungen.

## Persistenz vor und nach Dienst-Restart

Die SHA-256-Werte blieben exakt unverändert:

```text
/data/phnixIot4G                 7c573431f0a67620d473419644a83a4f4dc04b8a91bde5923c74a63ba1eaedb7
/data/phnixIot_device_OTA_INFO  2a8f2207089b2a99f390ede4d1e7170e2f1fda135e4c1dd59ad4383194b5c4a4
/data/phnixIot_device_statisic  1cb3a4dbfc0c2f2d9878f8e773a9596f92f6728de0ef24f38040a04a76ab585c
```

## GDB und Breakpoints

Direktes GDB-Attach erkannte wegen einer nicht passenden `libthread_db` nur den
Hauptthread. Der funktionierende Pfad ist:

```text
gdbserver --attach -> GDB target remote 127.0.0.1:12345
```

Damit wurden alle 13 Threads erkannt. Attach/Detach hinterließ
`TracerPid: 0`. Zehn benötigte Softwarebreakpoints konnten im angehaltenen
Prozess gemeinsam gesetzt, aufgelistet, entfernt und anschließend sauber
detacht werden:

```text
0x1FDAC  kontrollierte Parserinjektion/Rückkehr
0x1D2F8  bedingter set_dtu_run_step(7 -> 11)-Override
0x1C4BC  C350-Sendepfad
0x1CEA0  C357-Sendepfad
0x1C7CC  C5A8-Sendepfad
0x18D04  lokales 0023-Ergebnis
0x191C0  lokales 0053-Ergebnis
0x19264  lokales 0083-Ergebnis
0x1DA3C  Erfolg nach ausgeführtem Step-12-Setter
0x1D748  Fehler nach ausgeführtem Step-12-Setter
```

Keiner dieser Breakpoints wurde während des Installationstests ausgeführt.

## Normalzustand aus dem Prozessspeicher

Passiv gelesen wurden:

```text
dtu_run_step     = 11
board_ota_step   = 12
uart485SendFlag  = 0
```

GPIO 50 war als Ausgang konfiguriert und in fünf Stichproben jeweils `0`.
Die Disassemblierung von `Reset_All_DOG()` zeigt `usleep(2)`, nicht `sleep(2)`.

## Lokale Firmwarebereitstellung

Die Firmware wurde testweise per USB nach `/data` kopiert und mit BusyBox-httpd
über folgende ausschließlich lokale Adresse bereitgestellt:

```text
http://127.0.0.1:8081/FW3.3.bin
```

Der über HTTP gelesene MD5 stimmte. Der Testserver wurde danach beendet.

## Abschlusszustand des Modems

Nach den Tests wurden sämtliche Laborartefakte entfernt. Bestätigt wurden:

- Originaldienst aktiv, 13 Threads, `TracerPid: 0`;
- beide Watchdogs aktiv;
- Cloud-MQTT wieder verbunden;
- kein lokaler Listener auf Port 8081;
- keine von den Tests stammende Port-1883-Firewallregel;
- keine GDB-/gdbserver-Prozesse;
- keine Launcher-, Firmware- oder Statusdateien mehr auf dem Modem;
- unveränderte Hashes von Dienst, OTA_INFO und Statistik.

## Noch offen

Der aktive Launcherpfad wurde bewusst nicht auf dem echten Mainboard gestartet.
Insbesondere fehlt weiterhin ein automatisch ausführbarer und anschließend über
`C36C Status 1` bestätigter Cancelpfad. Bis dieser getestet ist, bleibt ein
nichtterminaler Fehler im fail-closed `guarded-hold` und verlangt eine bewusste
Recoveryentscheidung.
