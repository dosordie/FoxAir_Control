# PHNIX / FoxAir OTA Lab

Isolierte Debian-Testumgebung fuer die Analyse der originalen PHNIX-LTE-Anwendung `phnixIot4G` und des Mainboard-OTA-Protokolls.

Das Lab ist ausdruecklich fuer Offline-/Testbetrieb gedacht. Firmware, DeviceSecrets, IMEI und andere geraetespezifische Kennungen gehoeren **nicht** in dieses oeffentliche Repository.

## Empfohlene VM

- Debian 12 oder 13 minimal
- 2 vCPU
- 2 GB RAM
- 16 GB Disk
- VirtIO-Disk und VirtIO-Netzwerk sind passend
- kein Desktop erforderlich
- fuer spaetere Live-Cloudtests optional Internet; fuer die normale Analyse bevorzugt isoliertes Netz

Auf Proxmox ist eine eigene Bridge ohne physischen Uplink/Gateway fuer den komplett isolierten Betrieb ideal. Das Installationsscript installiert und aktiviert auch `qemu-guest-agent` sowie SSH.

## Installation

Auf einer frisch installierten Debian-VM:

```bash
wget https://raw.githubusercontent.com/dosordie/FoxAir_Control/main/devtools/phnix_ota_lab/install.sh
chmod +x install.sh
sudo ./install.sh
```

Alternativ als `root`:

```bash
wget https://raw.githubusercontent.com/dosordie/FoxAir_Control/main/devtools/phnix_ota_lab/install.sh
chmod +x install.sh
./install.sh
```

Das Script ist idempotent ausgelegt und kann bei Bedarf erneut ausgefuehrt werden.

## Was installiert wird

Unter anderem:

- `qemu-arm-static` / `qemu-user-static`
- `binfmt-support`
- `qemu-guest-agent`
- `openssh-server`
- Python 3 + venv
- `socat`
- Mosquitto + MQTT-Clients
- `tcpdump`
- `strace`
- `gdb-multiarch` sofern verfuegbar
- ARM-Binutils sofern verfuegbar
- `elfutils`, `pax-utils`, `file`, `xxd`
- Build-/Analysewerkzeuge

Der lokale Mosquitto-Testbroker lauscht absichtlich nur auf:

```text
127.0.0.1:1883
```

Dadurch ist der anonyme Testbroker nicht aus dem LAN erreichbar.

## Verzeichnisstruktur

Das Script erzeugt:

```text
/opt/phnix-lab/
├── rootfs/       # spaetere SIM7600/ARM-Runtime-Umgebung
│   ├── lib/
│   ├── usr/lib/
│   ├── etc/
│   ├── data/
│   ├── cache/
│   └── dev/
├── firmware/     # lokale Test-/Firmwareartefakte
├── logs/
├── pcap/
├── tools/
├── tmp/
└── venv/
```

Statuspruefung:

```bash
phnix-lab-info
```

## Geplanter Aufbau

Zielbild:

```text
Fake PHNIX Cloud
(Mosquitto + HTTP)
        |
        | MQTT / HTTP
        v
original phnixIot4G
unter QEMU ARM
        |
        | /dev/ttyHSL2, 9600 8N1
        v
PTY / socat
        |
        v
Python Fake-Mainboard
```

Damit soll spaeter der originale Ablauf gefahrlos nachgestellt werden:

```text
Mainboard-Info 0xC544
 -> MQTT 0003
 -> Fake-Cloud 0033
 -> HTTP-Firmwaredownload
 -> MD5-Pruefung
 -> OTA-Metadaten 0xC357
 -> Freigabe 0xC36E
 -> Firmwarebloecke 0xC5A8
 -> ACK/Fortschritt 0xC371
```

## Was das Installationsscript bewusst NICHT tut

- keine Firmware herunterladen
- keine DeviceSecrets oder IDs abfragen
- keine Dateien vom echten LTE-Modem kopieren
- keine Verbindung zur echten PHNIX-/LinkedGo-Cloud herstellen
- kein Routing und keine Proxmox-Firewall veraendern
- keinen echten RS485-Port ansprechen

## Naechster Schritt

Nach Installation wird zuerst die fuer `phnixIot4G` benoetigte Runtime vom SIM7600 **read-only** bestimmt und gesichert. Anschliessend werden ELF-Interpreter, Shared Libraries, benoetigte Konfigurationsdateien und Device-Zugriffe in der VM schrittweise nachgebildet.
