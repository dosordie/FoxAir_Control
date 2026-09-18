# SG Ready und PV-Überschusssteuerung

Mit **SG Ready** kann eine externe Steuerung der Wärmepumpe mitteilen, ob gerade wenig oder viel elektrische Energie zur Verfügung steht.

Typische Anwendungen sind:

- PV-Überschuss nutzen
- Wärmepumpe bei wenig verfügbarer Leistung begrenzen
- bei viel PV-Leistung gezielt mehr Heiz- oder Warmwasserenergie speichern
- Wärmepumpe zeitweise sperren bzw. in den Schlafmodus schicken

Die FoxAir unterstützt dafür sowohl **physische Kontakte** als auch – bei neueren Firmwareständen – eine **virtuelle Steuerung über Modbus**.

## Die vier SG-Ready-Zustände

Die FoxAir unterscheidet vier Betriebszustände:

| SG-Modus | Bedeutung | Typische Verwendung |
| ---: | --- | --- |
| **1** | Schlafmodus / Sperre | Wärmepumpe soll möglichst nicht laufen |
| **2** | wenig PV / Normalzustand | normale bzw. reduzierte Leistung |
| **3** | mittel PV | erhöhte Leistungsfreigabe |
| **4** | High PV | viel Überschuss, Sollwerte dürfen angehoben werden |

Welche Leistung bzw. Sollwertänderung tatsächlich verwendet wird, lässt sich über die SG-Parameter einstellen.

## Physische SG-Ready-Kontakte

Am Klemmfeld sind zwei SG-Kontakte vorhanden:

- **SG1: Klemme 1–2**
- **SG2: Klemme 7–8**

Bei Verwendung beider Kontakte ergeben sich die vier Zustände aus deren Kombination:

| SG1 | SG2 | SG-Modus |
| ---: | ---: | --- |
| EIN | AUS | **Mode 1** – Schlafmodus |
| AUS | AUS | **Mode 2** – wenig PV / Normalzustand |
| AUS | EIN | **Mode 3** – mittel PV |
| EIN | EIN | **Mode 4** – High PV |

Die Kontakte sind als Steuereingänge gedacht. Keine Fremdspannung auf die Eingänge geben, wenn die konkrete Beschaltung nicht sicher bekannt ist.

## SG-Ready-Quelle einstellen

Register **1334** legt fest, wie die SG-Ready-Steuerung erfolgt:

| Wert | Funktion |
| ---: | --- |
| **0** | SG Ready aus |
| **1** | Steuerung über einen physischen Kontakt |
| **2** | Steuerung über zwei physische SG-Kontakte |
| **3** | virtuelle SG-Ready-Steuerung über Modbus |

Für eine klassische Verdrahtung mit beiden SG-Kontakten wird daher **1334 = 2** verwendet.

Für eine Gebäudeautomation oder PV-Steuerung per Modbus wird **1334 = 3** verwendet.

## Steuerung über Modbus

Bei **1334 = 3** kann der gewünschte SG-Modus direkt über Register **8801** vorgegeben werden:

| Register 8801 | SG-Modus |
| ---: | --- |
| **1** | Mode 1 – Schlafmodus |
| **2** | Mode 2 – wenig PV / Normalzustand |
| **3** | Mode 3 – mittel PV |
| **4** | Mode 4 – High PV |

Dieser Weg wurde am **direkten Benutzer-Modbus der Wärmepumpe** praktisch bestätigt.

Für eine externe Steuerung ist damit im einfachsten Fall nur nötig:

```text
1334 = 3
8801 = gewünschter SG-Modus 1..4
```

Register **2133** zeigt anschließend den tatsächlich aktiven SG-Modus an.

> Wichtig: Für Register 8801 ist der direkte Benutzer-Modbus der bestätigte Weg. Der interne Warmlink-/LTE-Bus verhält sich bei diesem Register anders.

## Was bewirken Mode 2 und Mode 3?

Die Leistung für die beiden mittleren SG-Stufen kann separat eingestellt werden:

- **Register 1336** = Leistung für **Mode 2 / wenig PV**
- **Register 1337** = Leistung für **Mode 3 / mittel PV**

Die Werte werden in **0,1 kW** gespeichert.

Beispiel:

```text
1336 = 30  → 3,0 kW
1337 = 50  → 5,0 kW
```

Damit kann eine PV-Steuerung beispielsweise bei kleinem Überschuss eine niedrigere und bei größerem Überschuss eine höhere Leistungsfreigabe anfordern.

## Was bewirkt Mode 4 / High PV?

Mode 4 ist für einen hohen Energieüberschuss gedacht.

Dafür stehen zusätzliche Einstellungen zur Verfügung:

- **1338** = Sollwertanhebung 1
- **1339** = Sollwertanhebung 2
- **1340** = Sollwertanhebung 3
- **1341** = E-Heizer / Zusatzfunktion im High-PV-Modus

Damit können im High-PV-Modus z. B. Heiz- oder Warmwassersollwerte angehoben werden, um überschüssige PV-Energie thermisch zu speichern.

Welche der drei Temperaturvorgaben Heizen, Warmwasser oder Kühlen zugeordnet ist, hängt vom jeweiligen Betriebsmodus ab. Im Kühlbetrieb wird der entsprechende Offset technisch vom Sollwert abgezogen.

## Mode 1 / Schlafmodus

Mode 1 ist der Sperr- bzw. Schlafmodus.

Register **1335** bestimmt die zugehörige Schlafzeit in Minuten.

Wichtig: Diese einstellbare Schlafzeit ist **nicht** dasselbe wie die feste Verzögerung zwischen SG-Moduswechseln.

## 10 Minuten Verzögerung zwischen SG-Moduswechseln

Die Wärmepumpe übernimmt neue SG-Zustände nicht beliebig schnell hintereinander.

Nach einem akzeptierten Wechsel bleibt der aktuelle SG-Modus für ungefähr **10 Minuten** bestehen.

Das bedeutet zum Beispiel:

```text
aktuell Mode 2
→ Steuerung fordert Mode 4 an
→ Mode 4 wird übernommen
→ innerhalb der nächsten 10 Minuten wird ein weiterer Wechsel zunächst nicht wirksam
```

Bei Modbus kann Register **8801** während dieser Zeit bereits den neuen gewünschten Wert anzeigen, während **2133** noch den tatsächlich aktiven alten SG-Modus zeigt.

Für eine Gebäudeautomation sollte deshalb gelten:

- **8801** = gewünschter SG-Modus
- **2133** = tatsächlich aktiver SG-Modus

Den Zustand nicht im Sekundentakt wechseln.

## Sinnvolle PV-Strategie

Ein einfaches Beispiel:

- kaum oder kein Überschuss → **Mode 2**
- kleiner stabiler Überschuss → **Mode 3**
- großer Überschuss → **Mode 4**
- gezielte Sperrzeit → **Mode 1**

Wegen der 10-Minuten-Umschaltzeit sollte die PV-Steuerung nicht auf jede kurze Wolke reagieren, sondern mit ausreichend langen Zeitfenstern bzw. Hysterese arbeiten.

## Wichtige Register

| Register | Bedeutung |
| ---: | --- |
| **1334** | SG-Ready-Quelle |
| **1335** | Schlafzeit Mode 1 |
| **1336** | Leistung Mode 2 |
| **1337** | Leistung Mode 3 |
| **1338–1341** | High-PV-/Mode-4-Einstellungen |
| **2034** | Status der physischen SG-Kontakte |
| **2133** | tatsächlich aktiver SG-Modus |
| **8801** | virtueller SG-Modus über Modbus |

## Weitere technische Details

Die ausführliche technische Dokumentation mit Registerdetails, Kontaktbits und den bestätigten Firmwarepfaden gibt es hier:

[SG-Ready-Dokumentation](../sg_ready.md)
