# SG Ready

Diese Seite dokumentiert die bestätigte SG-Ready-Zuordnung für FoxAir/PHNIX-nahe Geräte.

## Physische Klemmen und I/O-Zuordnung

| SG-Kontakt | Klemme | I/O | Weitere Bezeichnung |
| --- | --- | --- | --- |
| SG1 | Klemme 1–2 | AI-DI16 | Remote On/Off / Fernschalter |
| SG2 | Klemme 7–8 | DIN_1 | Heat/Cool On/Off / PV-Kontakt |

Laut AirWende/PHNIX-naher Anleitung gilt damit:

- `AI/DI16` = Fernschalter / SG-1
- `DIN_1` = Heizungs- und Kühlfunktionsschalter / SG2

## Registerübersicht

| Register dez | Register hex | Bedeutung |
| --- | --- | --- |
| 1334 | 0x0536 | SG Ready Auswahl: `0` = Aus, `1` = 1 Kontakt, `2` = 2 Kontakte, `3` = Modbus / virtueller SG-Eingang |
| 1335 | 0x0537 | SG Mode 1 Schlafmodus Zeit in Minuten |
| 1336 | 0x0538 | SG Mode 2 Leistung / wenig PV in kW, Skalierung `RAW / 10` |
| 1337 | 0x0539 | SG Mode 3 Leistung / mittel PV in kW, Skalierung `RAW / 10` |
| 1338 | 0x053A | SG Mode 4 Temperatur-Offset / Sollwertanhebung 1 |
| 1339 | 0x053B | SG Mode 4 Temperatur-Offset / Sollwertanhebung 2 |
| 1340 | 0x053C | SG Mode 4 Temperatur-Offset / Sollwertanhebung 3; im Kühlbetrieb kann ein positiver Wert den Kühl-Sollwert effektiv senken, weil der Offset vom Kühl-Sollwert abgezogen wird |
| 1341 | 0x053D | SG Mode 4 E-Heizer / Zusatzfunktion |
| 2034 | 0x07F2 | Schalterzustände / Kontakte / SG Ready als Bitfeld |
| 2133 | 0x0855 | Aktiver SG-Ready-Modus |
| 8801 | 0x2261 | Virtueller SG-Zustand, **nur direkter User-/Mainboard-Modbus** |

## Virtueller SG-Eingang über direkten Modbus

Bei `1334 = 3` ignoriert die V3.3-Firmware die physischen SG-Kontakte und verwendet Register `8801`: `1` = Mode 1 / Schlafmodus, `2` = Mode 2 / Normal / wenig PV, `3` = Mode 3 / mittel PV und `4` = Mode 4 / High PV. Register `8801` ist am **direkten User-/Mainboard-Modbus** les- und schreibbar bestätigt. Der Warmlink-/LTE-Pfad auf Slave `0x63` stellt es dagegen nicht als normales Register bereit; insbesondere funktioniert dort FC03 auf `8801` nicht.

Da die Anwendung derzeit dasselbe Hauptregister-Mapping für direkten Modbus und Warmlink verwendet, ist `8801` bewusst nicht in `data/foxair_phnix_registers.json` aufgenommen. So suggeriert die Registerliste keine nicht vorhandene Warmlink-/LTE-Unterstützung.

## Kontaktstatus in Register 2034 / 0x07F2

Register `2034` zeigt den Klemmstatus sofort als Schalterzustand-/Kontakt-Bitfeld an.

| Bit | Kontakt | Bedeutung | Logik |
| --- | --- | --- | --- |
| 12 | SG Kontakt 1 | Klemme 1–2 / AI-DI16 / Remote On/Off / Fernschalter | active-high: `0` = Aus, `1` = Ein |
| 13 | SG Kontakt 2 | Klemme 7–8 / DIN_1 / Heat/Cool On/Off / PV-Kontakt | active-high: `0` = Aus, `1` = Ein |

Die bestehende S01–S10-Kontaktlogik bleibt davon getrennt: die bekannten PHNIX-Kontakte auf Bit `0`, `1`, `2`, `3`, `4`, `5`, `6` und `9` sind active-low (`0` = Ein, `1` = Aus).

## Aktiver SG-Modus in Register 2133 / 0x0855

Register `2133` zeigt den aktiven SG-Ready-Modus.

| Wert | Bedeutung |
| --- | --- |
| 0 | WP aus oder SG deaktiviert |
| 1 | SG Mode 1 / Schlafmodus |
| 2 | SG Mode 2 / wenig PV |
| 3 | SG Mode 3 / mittel PV |
| 4 | SG Mode 4 / High PV |

## Verzögerung zwischen Kontaktstatus und aktivem Modus

Register `2034` zeigt eine Kontaktänderung direkt am Eingang sofort an. Register `2133` schaltet dagegen zeitverzögert auf den tatsächlich aktiven SG-Modus um.

Eine Änderung von `8801` startet eine feste 10-minütige Umschaltsperre. Während dieser Zeit enthält `8801` bereits den neuen Wert, `2133` zeigt aber weiterhin den alten aktiven Modus. Nach Ablauf der 10 Minuten wird der neue Wert aus `8801` übernommen. Die Sperre lässt sich vorzeitig löschen, indem `1334` zunächst auf `0` und anschließend wieder auf `3` gestellt wird. Dieses Verhalten ist im V3.3-Binary und am realen Gerät bestätigt.
