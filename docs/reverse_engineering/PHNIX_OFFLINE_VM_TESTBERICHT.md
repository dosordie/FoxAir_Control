# PHNIX/FoxAir – Offline-VM-Testbericht mit originalem `phnixIot4G`

Stand: 23. August 2026

## Testaufbau

- Originales ARM-Programm `phnixIot4G` unter QEMU in der Labor-VM
- lokale Ersatzdienste für Credentials, TLS/MQTT, Firmware-HTTP, QMI und RS485
- Netzwerk-Namespace ohne IPv4-/IPv6-Default-Route
- kein Zugriff auf ser2net, reales Mainboard oder PHNIX-Cloud
- Originalbinary inhaltlich unverändert; für den lokalen MQTT-Test wurde die bereits etablierte TLS-Labkopie mit lokalem CA-Vertrauen verwendet
- vor jedem unabhängigen Szenario Rücksetzen von `OTA_INFO`, Statistikdatei und Cache

## Wesentliche Ergebnisse

| Szenario | Beobachtung |
|---|---|
| C350 Status 0 | Kein C357 und kein C5A8 |
| C350 ohne Statusantwort | Kein Fortschritt; kein C357/C5A8 |
| C357 ohne Statusantwort | Kein C5A8 |
| Kein ACK für Block 1 | Block 1 dreimal gesendet; kein Fortschritt zu Block 2 |
| Falsche ACK-Blocknummer | ACK verworfen; Block 1 erneut gesendet |
| Falsche ACK-SSID | Vom Originaldienst nicht verworfen; Transfer lief mindestens bis Block 101 weiter |
| Erstes ACK verloren | Block 1 wiederholt; anschließend normaler Fortschritt |
| Falscher Download-MD5 | Vollständiger Download in Cache, kein C5A8, anschließend Fehler `0083` |
| Falsche deklarierte Größe | Vollständiger Download in Cache, kein C5A8, anschließend Fehler `0083` |
| Zweites `0033` früh | Neue SSID/Version übernommen; neuer C350; alte Datei blieb im Cache; alter Ablauf endete mit `0083` |
| Zweites `0033` während Datenphase | Laufender Transfer wurde nicht sofort sauber ersetzt; Verhalten ist phasenabhängig |
| Cloud-Cancel nach vier Sekunden | Erster C5A8 und C36A waren bereits auf dem Bus; C36C wurde verarbeitet |
| Cloud-Cancel vor C357 | Trotz C36A/C36C folgten C357 und C5A8; innerhalb der Laufzeit wurden 97 Blöcke gesendet |
| Cloud-Rollback | Erster C5A8 war bereits gesendet; danach wiederholte C375-Rollbackrequests mangels C378-Antwort |
| Neustart nach `0033`-Kollision | Cache und persistierte Zustände beeinflussten den Folgelauf; kein sauber zustandsloser Neustart |
| Vollständiger Referenztransfer | 1712 Blöcke, 287598 Bytes, korrekter SHA-256, letzter ACK `ackB=2` |

## Vollständiger Referenztransfer

```text
C5A8-Blöcke:       1712
Nutzbytes:          287598
Letzter Block:      150 reale Bytes + 18 × FF
Finales C371:       ackB=2
SHA-256:            6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Der Simulator erzeugte absichtlich keine C36E-Status-3/5-, C37B-, Flash-, Jump- oder Neustartphase.

## Sicherheitsrelevante Schlussfolgerungen

1. Der Originaldienst ist bei Blocknummern und fehlenden ACKs robust, prüft aber die ACK-SSID nicht streng.
2. Ein Cloud-Cancel ist kein zuverlässiger Guard, um C5A8 zu verhindern. Selbst ein vor C357 bestätigter Cancel entfernte den bereits eingeplanten Transfer nicht.
3. Ein konkurrierendes `0033` kann Firmware-, SSID-, Cache- und Zustandskontexte überlagern. Das Verhalten hängt vom Zeitpunkt ab.
4. Eine offene echte Cloud sollte bei einem lokal kontrollierten Update deshalb nicht bestehen.
5. Für einen ersten realen Vortest ist nur ein direkt kontrolliertes C350 mit identischer aktueller Kennung und erwarteter Antwort Status 0 vertretbar. Kein C357, kein C36A und kein C5A8.
6. Die Tests klären weiterhin nicht das fehlende IAP-/Phase-A-Image oder den realen Loader-/Recoverypfad.

## Wiederhergestellter VM-Ausgangszustand

```text
OTA_INFO SHA-256:
F5E31095C7366C4245A97F2EEAFEF76B2A4774405F589D0E8D5578A5B62136BB

Statistik SHA-256:
1B4F6D5AE996001A7357A7C973039E15C89C4B417A1E0E00788B2A4AACE231BE

Firmwarecache: nicht vorhanden
```
