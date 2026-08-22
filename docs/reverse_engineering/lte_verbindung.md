# LTE-Verbindung des FoxAir/PHNIX-Modems

Diese Datei dokumentiert die bislang direkt am LTE-Modem ermittelten Mobilfunk- und Verbindungsdaten.

## Zugriff auf das Modem

Das LTE-Modem lässt sich per USB über ADB ansprechen. Unter Windows wurde dafür der SIMCom-Treiber `SIMCOM_Windows_USB_Drivers_V1.0.2` benötigt.

Auf einem Raspberry Pi wird das Gerät direkt vom Linux-Kernel erkannt:

```text
Bus 001 Device 006: ID 1e0e:9001 Qualcomm / Option SimTech, Incorporated
```

Die USB-Interfaces werden unter Linux u. a. als mehrere serielle Ports, QMI und ADB bereitgestellt:

```text
/dev/ttyUSB0
/dev/ttyUSB1
/dev/ttyUSB2
/dev/ttyUSB3
/dev/ttyUSB4
```

ADB funktioniert nach einer passenden udev-Regel für `1e0e:9001` ohne Root-Rechte:

```text
0123456789ABCDEF       device
```

Damit kann der Raspberry Pi dauerhaft an der Wärmepumpe verbleiben und als ADB-/Analysezugang verwendet werden.

## AT-Zugriff

Der verwendete AT-Port ist `/dev/ttyUSB2`.

Auf dem Raspberry Pi wurde der Port zunächst durch `ModemManager` belegt. Nach Stoppen des Dienstes war der Zugriff möglich:

```bash
sudo systemctl stop ModemManager
```

Die funktionierende serielle Konfiguration entspricht der zuvor unter Windows verwendeten Einstellung:

```text
2400 Baud
8 Datenbits
Even Parity
1 Stopbit
```

Beispiel mit `picocom`:

```bash
picocom -b 2400 -d 8 -p e -s 1 /dev/ttyUSB2
```

Test:

```text
AT
OK
```

## Aktuell eingebuchtes Mobilfunknetz

Abfrage:

```text
AT+COPS?
```

Antwort:

```text
+COPS: 0,0,"Telekom.de",7
```

Damit ist das Modem aktuell im Netz von **Telekom Deutschland** eingebucht.

Die RAT-Kennung `7` steht hier für LTE.

## LTE-Funkparameter

Abfrage:

```text
AT+CPSI?
```

Antwort:

```text
+CPSI: LTE,Online,262-01,0x580E,44867840,496,EUTRAN-BAND3,1300,5,5,-129,-1092,-763,16
```

Daraus ergeben sich folgende Werte:

| Parameter | Wert |
|---|---|
| Netztyp | LTE |
| Status | Online |
| PLMN | 262-01 |
| Netz | Telekom Deutschland |
| LTE-Band | Band 3 |
| Frequenzbereich | 1800 MHz |
| EARFCN | 1300 |
| PCI | 496 |
| Cell-ID | 44867840 |
| RSRQ | ca. -12,9 dB |
| RSRP | ca. -109,2 dBm |
| RSSI | ca. -76,3 dBm |
| RSSNR/SINR | ca. 1,6 dB |

Die Funkverbindung ist damit brauchbar, aber insbesondere RSRP und RSRQ sind eher mittelmäßig bis schwach.

Zusätzliche Abfrage:

```text
AT+CSQ
```

Antwort:

```text
+CSQ: 18,99
```

`CSQ 18` entspricht ungefähr einem RSSI von -77 dBm und passt damit gut zum aus `AT+CPSI?` gemeldeten RSSI.

## Roaming-Status

Abfrage:

```text
AT+CEREG?
```

Antwort:

```text
+CEREG: 0,5
```

Der Status `5` bedeutet: registriert, Roaming.

Das Modem befindet sich also im Telekom-Netz, die SIM selbst stammt aber nicht aus dem deutschen Telekom-Heimatnetz.

## SIM-Provider

Die IMSI beginnt mit:

```text
208-01...
```

Zusätzlich liefert:

```text
AT+CSPN?
```

```text
+CSPN: "Orange F",0
```

Damit ist die SIM dem Heimatnetz **Orange France** zuzuordnen.

Die Wärmepumpe verwendet somit eine Orange-France-basierte M2M-/IoT-SIM und roamt in Deutschland aktuell im Telekom-Netz.

Hinweis: IMSI und ICCID sind eindeutige SIM-Identifikatoren und sollten nicht vollständig veröffentlicht werden.

## APN und PDP-Kontext

Abfrage:

```text
AT+CGDCONT?
```

Relevante Antworten:

```text
+CGDCONT: 1,"IPV4V6","orange.m2m.spec",...,0,0,0,0
+CGDCONT: 2,"IPV4V6","ims",...,0,0,0,0
+CGDCONT: 6,"IPV4V6","orange.m2m.spec",...,0,0,0,0
```

Der aktive Datenzugang verwendet den APN:

```text
orange.m2m.spec
```

Das bestätigt die Verwendung eines Orange-M2M-Zugangs.

## Aktive IP-Verbindung

Abfrage:

```text
AT+CGPADDR
```

Antwort für den aktiven Kontext:

```text
+CGPADDR: 1,10.214.199.17
```

Der aktive PDP-Kontext nutzt damit eine private IPv4-Adresse aus dem RFC1918-Bereich.

Weitere Details liefert:

```text
AT+CGCONTRDP
```

Antwort:

```text
+CGCONTRDP: 1,5,orange.m2m.spec,10.214.199.17,,192.168.10.110,194.51.3.56
```

Aktuell beobachtet:

| Parameter | Wert |
|---|---|
| PDP Context ID | 1 |
| APN | `orange.m2m.spec` |
| IP-Adresse | `10.214.199.17` |
| DNS 1 | `192.168.10.110` |
| DNS 2 | `194.51.3.56` |

Die LTE-Verbindung läuft damit sinngemäß über folgenden Pfad:

```text
FoxAir / PHNIX LTE-Modem
        |
        | Orange-France-M2M-SIM
        v
Roaming im Telekom-Netz Deutschland
        |
        | LTE Band 3
        v
Orange M2M Core
APN: orange.m2m.spec
private IP: 10.214.199.17
        |
        v
PHNIX / Warmlink Backend
```

## Offene Punkte

Für die weitere Reverse-Engineering-Analyse sind insbesondere folgende Punkte interessant:

- aktive TCP-/UDP-Verbindungen des Modems erfassen
- Ziel-IP-Adressen und Ports des Warmlink-/PHNIX-Backends bestimmen
- zugehörige Prozesse im Android-/Linux-System identifizieren
- DNS-Auflösungen beobachten
- Verbindungsaufbau und Reconnect-Verhalten untersuchen
- prüfen, welche Daten lokal zwischen Wärmepumpen-Mainboard und LTE-Anwendung verarbeitet werden
