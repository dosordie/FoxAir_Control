# SG Ready

Diese Seite dokumentiert die SG01-Auswahlfamilien, den virtuellen SG-Ready-Eingang und den erweiterten SG/PV-Pfad der V3.4-Firmware.

Stand der Live-Verifikation: 13. September 2026.

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
| 1334 | 0x0536 | SG01: `0` Aus; klassisch `1` ein Kontakt, `2` zwei Kontakte, `3` Modbus 8801 / vier Zustände; `4` AI Saving / Remote Energy Control; erweitert `5` ein Kontakt (Neutral/High), `6` zwei Kontakte (Low/Neutral/High), `7` Modbus 8801 (Low/Neutral/High) |
| 1335 | 0x0537 | SG02 – Schlaf-/Sperrzeit klassischer Mode 1 in Minuten |
| 1336 | 0x0538 | SG03 – Low-PV- beziehungsweise klassische Mode-2-Leistungsgrenze, `RAW / 10` kW |
| 1337 | 0x0539 | SG04 – klassische Mode-3-/Medium-PV-Leistung, `RAW / 10` kW; keine eigene Stufe der Familie 5/6/7 |
| 1338 | 0x053A | SG05 – High-PV-Warmwasser-Sollwertanhebung |
| 1339 | 0x053B | SG06 – High-PV-Heiz-Sollwertanhebung |
| 1340 | 0x053C | SG07 – High-PV-Kühl-Sollwertänderung; ein positiver Offset wird vom Kühl-Sollwert abgezogen |
| 1341 | 0x053D | SG08 – High-PV-E-Heizer / Zusatzfunktion |
| 2034 | 0x07F2 | physische Schalter-/Kontaktzustände als Bitfeld |
| 2133 | 0x0855 | tatsächlich aktiver SG-Ready-/SG-PV-Status |
| **8801** | **0x2261** | **virtueller Eingang, ausschließlich bei `1334 = 3` oder `1334 = 7` verwendet** |

## Drei SG01-Familien

SG01 unterscheidet drei Regelpfade:

- `1/2/3`: klassische SG-Ready-Familie mit einem Kontakt, zwei Kontakten oder dem virtuellen Vier-Zustands-Eingang 8801.
- `4`: **AI Saving / Remote Energy Control**. Dieser Wert wurde an realer V3.4 beim Aktivieren von AI Saving beziehungsweise des dynamischen Stromtarifs in der PHNIX-App beobachtet. Er ist ein separater Remote-Regelpfad und kein klassischer SG-Ready-Zustand. Der Regelkomplex besteht bereits in V3.4; V3.5 ergänzt weitere Warmlink-Stellgrößen. „AI“ ist die App-Bezeichnung und kein Firmwarebeleg für Machine Learning.
- `5/6/7`: zweite, funktional als **erweiterte SG/PV-Familie** bezeichnete Firmwarefamilie. Diese Formulierung ist kein bekannter offizieller PHNIX-Name.

### Erweiterte SG/PV-Familie (`1334 = 5/6/7`)

Die V3.4-Firmware paart `1 ↔ 5` (ein Kontakt), `2 ↔ 6` (zwei Kontakte) und `3 ↔ 7` (Modbus). Funktional arbeitet die erweiterte Familie mit **Low PV / Neutral / High PV**:

| SG01 | Eingang und erreichbare Stufen |
| ---: | --- |
| 5 | ein physischer Kontakt: Kontakt `0` = Neutral, Kontakt `1` = High PV |
| 6 | zwei physische Kontakte: Kontakt 1=`1` = Low PV; beide `0` = Neutral; Kontakt 1=`0`, Kontakt 2=`1` = High PV |
| 7 | virtuell über 8801: `1` = Low PV, `2` = Neutral, `3` = High PV; Wert `4` ist hier nicht gültig |

Für die nicht eindeutig dokumentierte Kontaktkombination `1/1` bei SG01=6 wird keine zusätzliche Bedeutung angenommen. Low PV begrenzt die Leistung über `1336 / SG03` und verwendet keine WW-/Heiz-/Kühl-Offsets. Neutral bedeutet Normalbetrieb ohne SG-bedingte Leistungs- oder Temperaturanpassung. High PV verwendet den High-PV-/Mode-4-Pfad: WW-Sollwert `+ SG05/1338`, Heiz-Sollwert `+ SG06/1339`, Kühl-Sollwert `- SG07/1340`.

„Low / Neutral / High“ ist die funktionale Interpretation der Firmware. Die Werte 5 und 6 sind statisch in V3.4 bestätigt, jedoch noch nicht am realen Gerät live verifiziert. Wert 7 und der virtuelle Dreistufenpfad sind zusätzlich praktisch wesentlich besser bestätigt. AI Saving (`4`) ist ausdrücklich **nicht** Teil dieses dreistufigen Modells.

Bei `1334 = 7` meldet Register `2133` die wirksame Stufe `1/2/3` mit derselben Bedeutung zurück. Für `1334 = 5/6` ist die Detailsemantik von 2133 noch nicht ausreichend geklärt und darf nicht aus dem Kontaktmodell abgeleitet werden.

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

V3.3 übernimmt Änderungen des gewünschten SG-Modus **nicht beliebig schnell hintereinander**. Diese 10-minütige Umschaltsperre betrifft den klassischen virtuellen Pfad; für Modus 7 ist sie durch die bisherigen Live-Tests nicht bestätigt.

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

Für einen kontrollierten Test kann `1334` zunächst auf `0` und anschließend wieder auf `3` gesetzt werden. Zusammen mit dem gewünschten virtuellen Wert entspricht dies beispielsweise:

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

Register `2133` zeigt den tatsächlich aktiven SG-Ready-/SG-PV-Status. Die folgende Tabelle gilt für den klassischen Pfad; bei SG01=7 gelten stattdessen 1=Low PV, 2=Neutral und 3=High PV. Für SG01=5/6 bleibt die genaue Statussemantik offen.

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

Für eine dauerhafte klassische Modbus-Steuerung:

```text
1. 1334 = 3 konfigurieren
2. 8801 auf 1..4 setzen
3. 8801 zurücklesen
4. 2133 als tatsächlich aktiven SG-Modus überwachen
5. den festen 10-Minuten-Hold bei Sollwertwechseln berücksichtigen
```

Für den erweiterten virtuellen Pfad wird stattdessen `1334 = 7` mit `8801 = 1..3` verwendet. Bei allen anderen SG01-Werten ist 8801 kein SG-Stufeneingang.

Nach Mainboard-Neustarts sollte ein externer Controller den gewünschten Zustand erneut prüfen. Für `8801` sollte keine ungetestete Persistenzannahme über einen vollständigen Neustart getroffen werden.

Die detaillierte Firmwareanalyse steht im Reverse-Engineering-Repository unter `FW3.3-SG-READY-MODBUS-8801.md`.

## Abgrenzung zu MAIN:1540 (V3.5)

AI Saving (`SG01`/MAIN:1334 = 4) aktiviert den bereits in V3.4 vorhandenen Remote-Komplex um 8001/8004/8006, 0x20016A54 und MAIN1691/1692. V3.5 ergänzt separat MAIN:1540 für 8021–8028. In der Mainboard-Firmware ist kein Setter `SG01=4 -> MAIN1540=1` bestätigt; beide Gates sind daher nicht gleichzusetzen.
