# SG Ready

Diese Seite dokumentiert die bestätigte SG-Ready-Zuordnung der untersuchten FoxAir/PHNIX-Mainboard-Firmware V3.3 einschließlich des inzwischen **live bestätigten virtuellen SG-Ready-Eingangs über Modbus**.

Stand der Live-Verifikation: 24. August 2026.

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
| ---: | ---: | --- |
| 1334 | 0x0536 | SG-Ready-Quelle: `0` = Aus, `1` = 1 Kontakt, `2` = 2 physische Kontakte, **`3` = virtueller SG-Ready-Eingang über Modbus** |
| 1335 | 0x0537 | SG Mode 1 Schlafmodus-Zeit in Minuten |
| 1336 | 0x0538 | SG Mode 2 Leistung / wenig PV in kW, Skalierung `RAW / 10` |
| 1337 | 0x0539 | SG Mode 3 Leistung / mittel PV in kW, Skalierung `RAW / 10` |
| 1338 | 0x053A | SG Mode 4 Temperatur-Offset / Sollwertanhebung 1 |
| 1339 | 0x053B | SG Mode 4 Temperatur-Offset / Sollwertanhebung 2 |
| 1340 | 0x053C | SG Mode 4 Temperatur-Offset / Sollwertanhebung 3; im Kühlbetrieb kann ein positiver Wert den Kühl-Sollwert effektiv senken, weil der Offset vom Kühl-Sollwert abgezogen wird |
| 1341 | 0x053D | SG Mode 4 E-Heizer / Zusatzfunktion |
| 2034 | 0x07F2 | physische Schalter-/Kontaktzustände als Bitfeld |
| 2133 | 0x0855 | tatsächlich aktiver SG-Ready-Modus |
| **8801** | **0x2261** | **virtueller SG-Ready-Zustand, wirksam bei `1334 = 3`** |

## Virtueller SG-Ready-Eingang über Register 8801

Die V3.3 besitzt einen in älteren Registerlisten nicht dokumentierten vierten SG-Quellenmodus:

```text
1334 = 3
```

In diesem Modus wertet die SG-Ready-Zustandsmaschine nicht die beiden physischen SG-Kontakte aus, sondern Register:

```text
8801 / 0x2261
```

Die Zuordnung ist aus der Firmware rekonstruiert und am realen Gerät bestätigt:

| 8801 | virtueller Kontakt A | virtueller Kontakt B | SG-Modus |
| ---: | ---: | ---: | --- |
| 1 | 1 | 0 | Mode 1 / Schlafmodus |
| 2 | 0 | 0 | Mode 2 / wenig PV / Normalzustand |
| 3 | 0 | 1 | Mode 3 / mittel PV |
| 4 | 1 | 1 | Mode 4 / High PV |

`8801 = 0` erzeugt keinen gültigen virtuellen SG-Modus. Werte `>=5` werden von V3.3 ebenfalls nicht als gültiger SG-Zustand akzeptiert.

### Live bestätigt

Am untersuchten Mainboard wurde über den direkten User-Modbus bestätigt:

- `8801` war initial `0`.
- `8801` ist lesbar.
- Werte `0..4` lassen sich schreiben und wieder zurücklesen.
- Die geschriebenen Werte bleiben im Register stehen.
- `8801 = 1` führte bei aktivem virtuellen SG-Modus zu Mode 1; die Wärmepumpe blieb im Schlafmodus und startete nicht.
- `8801 = 4` führte zu Mode 4; die Wärmepumpe startete mit der erwarteten High-Power-Reaktion.
- Die Zuordnung und das Umschaltverhalten über `8801` wurden insgesamt praktisch bestätigt.

Damit ist `8801` nicht nur ein statischer Reverse-Engineering-Fund, sondern ein **real nutzbarer SG-Ready-Steuereingang**.

## Fester 10-Minuten-Hold zwischen SG-Moduswechseln

V3.3 übernimmt Änderungen des gewünschten SG-Modus **nicht beliebig schnell hintereinander**.

Nach jeder tatsächlich akzeptierten SG-Modusänderung wird intern ein Hold-Timer auf:

```text
1200 Zyklen
```

gesetzt. Die SG-Routine läuft effektiv alle `0,5 s`, daher:

```text
1200 × 0,5 s = 600 s = 10 Minuten
```

Während dieser 10 Minuten kann `8801` sofort geändert und zurückgelesen werden, der effektive Modus in `2133` bleibt aber zunächst auf dem zuletzt akzeptierten SG-Modus.

Beispiel:

```text
2133 = 1
8801 = 3
-> 8801 liest sofort 3
-> 2133 bleibt zunächst 1

anschließend noch innerhalb des Holds:
8801 = 2
-> 8801 liest sofort 2
-> 2133 bleibt zunächst 1

nach Ablauf des Holds:
-> der dann aktuell anliegende Wert 2 wird übernommen
-> 2133 wechselt 1 -> 2
```

Ein nur kurz während des Hold-Zeitraums eingestellter Zwischenwert muss deshalb nie in `2133` sichtbar werden.

### Änderung von 1334 setzt den Hold-Timer zurück

Ebenfalls aus V3.3 rekonstruiert und **am realen Gerät bestätigt**:

> Eine Änderung der SG-Quellenauswahl in `1334` setzt den 10-Minuten-Hold und die zugehörigen internen Übergangszustände zurück.

Für einen kontrollierten Test kann daher beispielsweise:

```text
8801 = gewünschter Modus
1334 = 0
1334 = 3
```

dazu führen, dass der aktuelle `8801`-Wert wieder unmittelbar als neuer SG-Modus angenommen werden kann. Nach der Annahme beginnt erneut der 10-Minuten-Hold.

Das sollte als Diagnose-/Testmechanismus verstanden werden, nicht als Methode für häufiges Umschalten im normalen Automatikbetrieb.

## Mode-1-Schlafzeit 1335 ist ein separater Timer

Der feste 10-Minuten-Hold ist **nicht** die in `1335` eingestellte Schlafzeit.

Es existieren zwei getrennte Zeitmechanismen:

```text
fester Hold:
    10 Minuten
    nach jeder akzeptierten SG-Modusänderung

1335:
    konfigurierbarer Minutenwert
    spezielle Zeitlogik für SG Mode 1 / Schlafmodus
```

## Kontaktstatus in Register 2034 / 0x07F2

Register `2034` zeigt die **physischen** Klemmzustände direkt als Schalter-/Kontakt-Bitfeld an.

| Bit | Kontakt | Bedeutung | Logik |
| --- | --- | --- | --- |
| 12 | SG Kontakt 1 | Klemme 1–2 / AI-DI16 / Remote On/Off / Fernschalter | active-high: `0` = Aus, `1` = Ein |
| 13 | SG Kontakt 2 | Klemme 7–8 / DIN_1 / Heat/Cool On/Off / PV-Kontakt | active-high: `0` = Aus, `1` = Ein |

Die bestehende S01–S10-Kontaktlogik bleibt davon getrennt: die bekannten PHNIX-Kontakte auf Bit `0`, `1`, `2`, `3`, `4`, `5`, `6` und `9` sind active-low (`0` = Ein, `1` = Aus).

Bei `1334 = 3` müssen Bit 12/13 **nicht** der virtuellen Vorgabe aus `8801` folgen. Sie bleiben die Rohzustände der realen Eingangsklemmen.

## Aktiver SG-Modus in Register 2133 / 0x0855

Register `2133` zeigt den tatsächlich aktiven SG-Ready-Modus.

| Wert | Bedeutung |
| ---: | --- |
| 0 | WP aus oder SG deaktiviert |
| 1 | SG Mode 1 / Schlafmodus |
| 2 | SG Mode 2 / wenig PV |
| 3 | SG Mode 3 / mittel PV |
| 4 | SG Mode 4 / High PV |

Am untersuchten Gerät ist `2133` insbesondere bei eingeschalteter/aktiver Wärmepumpe als Rückmeldung sinnvoll; bei ausgeschalteter WP wird der aktive SG-Zustand nicht in gleicher Weise fortlaufend aktualisiert.

Für den virtuellen Pfad ist daher die sinnvolle Beobachtung:

```text
8801 = gewünschter Zustand
2133 = tatsächlich übernommener Zustand
```

## User-Modbus versus Warmlink-/LTE-Modbus

Die beiden Zugangswege dürfen nicht gleichgesetzt werden.

### Direkter User-/Mainboard-Modbus

Für `8801` am untersuchten Gerät praktisch bestätigt:

```text
FC03 lesen    -> funktioniert
Schreiben     -> funktioniert
0..4          -> bleiben im Register stehen
```

Dieser Pfad ist für die Nutzung von `8801` derzeit der bestätigte Weg.

### Warmlink-/LTE-Bus, Slave 0x63

Live beobachtet:

```text
1334 lesen/schreiben -> funktioniert
2133 lesen           -> funktioniert
8801 FC03            -> Timeout / keine Antwort
8801 FC16            -> formal passender Modbus-ACK
```

Der formal korrekte FC16-ACK auf `8801` hat im Cross-Bus-Test jedoch **keinen sicheren Nachweis einer Änderung des echten User-Modbus-Registers 8801 geliefert**. Deshalb darf dieser ACK nicht als Beweis gewertet werden, dass der LTE-/0x63-Pfad `8801` tatsächlich anwendet.

Aktueller belastbarer Stand:

> `8801` über den direkten User-Modbus verwenden. Der Warmlink-/LTE-0x63-Pfad verhält sich für dieses Engineeringregister anders und ist hierfür nicht als funktionaler Schreibpfad bestätigt.

## Empfehlung für externe Steuerungen

Für eine dauerhafte Modbus-Steuerung:

```text
1. 1334 = 3 konfigurieren
2. 8801 auf 1..4 setzen
3. 8801 zurücklesen
4. 2133 als tatsächlich aktiven SG-Modus überwachen
5. den festen 10-Minuten-Hold bei Sollwertwechseln berücksichtigen
```

Nach Mainboard-Neustarts sollte ein externer Controller den gewünschten Zustand erneut prüfen. Für `8801` sollte keine ungetestete Persistenzannahme über einen vollständigen Neustart getroffen werden.

Die detaillierte Firmwareanalyse steht im Reverse-Engineering-Repository unter `FW3.3-SG-READY-MODBUS-8801.md`.