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
| 1334 | 0x0536 | SG Ready Auswahl: `0` = Aus, `1` = 1 Kontakt, `2` = 2 Kontakte |
| 1335 | 0x0537 | SG Mode 1 Schlafmodus Zeit in Minuten |
| 1336 | 0x0538 | SG Mode 2 Leistung / wenig PV in kW, Skalierung `RAW / 10` |
| 1337 | 0x0539 | SG Mode 3 Leistung / mittel PV in kW, Skalierung `RAW / 10` |
| 1338 | 0x053A | SG Mode 4 Temperatur-Offset / Sollwertanhebung 1 |
| 1339 | 0x053B | SG Mode 4 Temperatur-Offset / Sollwertanhebung 2 |
| 1340 | 0x053C | SG Mode 4 Temperatur-Offset / Sollwertanhebung 3; im Kühlbetrieb kann ein positiver Wert den Kühl-Sollwert effektiv senken, weil der Offset vom Kühl-Sollwert abgezogen wird |
| 1341 | 0x053D | SG Mode 4 E-Heizer / Zusatzfunktion |
| 2034 | 0x07F2 | Schalterzustände / Kontakte / SG Ready als Bitfeld |
| 2133 | 0x0855 | Aktiver SG-Ready-Modus |

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

Diese Verzögerung ist laut Kaisai-Manual plausibel und wurde praktisch beobachtet. Deshalb ist es keine direkte Fehlinterpretation, wenn `2034` bereits den neuen Kontaktzustand zeigt, `2133` aber kurzzeitig noch auf dem alten Modus steht.
