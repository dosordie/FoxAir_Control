# Elektrischer Heizstab – Zuschaltung und Heizstufen

Die **FoxAir GL9 hat keinen eingebauten Heizstab**. Die Steuerung kann aber eine **extern installierte elektrische Zusatzheizung** ansteuern.

## Kurz erklärt

### Wofür ist die Zusatzheizung gedacht?

Bei großer Kälte oder wenn die Wärmepumpe die gewünschte Temperatur über längere Zeit nicht erreicht, kann ein angeschlossener Heizstab zusätzliche Wärme liefern. Auch für bestimmte Sonderbetriebsarten, beispielsweise das Abtauen, gibt es eine eigene Freigabe.

Die elektrische Zusatzheizung arbeitet mit einem **COP von 1**. Deshalb sollte sie nur dann mitlaufen, wenn die zusätzliche Leistung wirklich benötigt wird.

### Zwei Anschlüsse, drei Heizstufen

Das Mainboard bietet **zwei getrennte Schaltausgänge** für die Zusatzheizung. Durch die Kombination sind drei Leistungsstufen möglich.

Beispiel bei einem Heizstab mit 1 kW und einem zweiten mit 2 kW:

| Stufe | Eingeschaltete Heizstäbe | Zusätzliche Leistung |
| --- | --- | ---: |
| 1 | Heizstab 1 | 1 kW |
| 2 | Heizstab 2 | 2 kW |
| 3 | Beide zusammen | 3 kW |

Die Leistungen sind **Beispiele**, keine Vorgabe der FoxAir. Die Steuerung schaltet nur die Ausgänge; sie regelt die tatsächliche Heizstableistung nicht stufenlos.

### Schaltet die FoxAir automatisch hoch?

**Ja.** In der Firmware V3.5 gibt es sowohl eine **zeitabhängige Staffelung** als auch die Möglichkeit, bei besonders niedriger Außentemperatur die Zusatzheizung ohne diese Wartezeit zuzuschalten:

1. Zuerst kann **Stufe 1** eingeschaltet werden.
2. Bleibt der zusätzliche Wärmebedarf bestehen, kann die Steuerung auf **Stufe 2** wechseln. Stufe 1 wird dabei abgeschaltet.
3. Bei weiterem Bedarf kann sie schließlich **beide Heizstäbe gemeinsam** einschalten.

Die im Menü ausgewählte Heizstufe begrenzt, **wie weit die Steuerung hochschalten darf**. Das bedeutet insbesondere: Die Einstellung „Stufe 2“ bedeutet im normalen Ablauf nicht zwingend, dass ausschließlich der zweite Heizstab verwendet wird.

### Wann wird zugeschaltet?

Entscheidend sind unter anderem **Heizbedarf, Soll-/Isttemperatur, Außentemperatur und die eingestellte Wartezeit**. „Nach 30 Minuten“ ist keine allgemeine Werkseinstellung: Die Wartezeit ist einstellbar.

Bei sehr niedrigen Außentemperaturen kann die Steuerung die Zusatzheizung auch **ohne die normale Wartezeit** einschalten. Andere Betriebszustände, Störungen oder Schutzfunktionen können die Zuschaltung verhindern oder beenden.

**Welcher Außentemperaturfühler zählt?** Normalerweise verwendet die FoxAir den eingebauten Außentemperaturfühler **T04**. Ist ein externer Außentemperaturfühler aktiviert und liefert er einen gültigen Wert, verwendet die Heizstabregelung dessen Temperatur.

### Worauf muss ich beim Anschluss achten?

**Ein Heizstab darf nicht direkt an RO07 oder RO08 angeschlossen werden.** Zwischen den Steuerausgängen des Mainboards und dem Heizstab muss jeweils ein **für die Heizstableistung geeignetes Relais oder Schütz** geschaltet werden. Außerdem sind eine passende Absicherung und ein unabhängiger Übertemperaturschutz erforderlich. Die konkrete Anschlussbelegung muss vor der Verdrahtung geprüft werden.

---

## Technischer Teil: Regelung und Zusammenhänge (Firmware V3.5)

Die folgenden Einstellungen und Zusammenhänge beschreiben die **Heizstabregelung der Firmware V3.5**.

### Heizstufenauswahl H18 und die Ausgänge

Die normale Zusatzheizung verwendet zwei logische Ausgänge:

| Ausgang | Funktion | Modbus-Rückmeldung |
| --- | --- | --- |
| **RO07** | Heizstab/Stufe 1 | **2019 Bit 7** |
| **RO08** | Heizstab/Stufe 2 | **2019 Bit 8** |

**H18 / Modbus 1032** gibt die maximal zulässige Heizstufe vor:

| H18 | Maximale Stufe im normalen Ablauf | Verhalten bei unmittelbarer Freigabe |
| ---: | --- | --- |
| **1** | nur Stufe 1 | RO07 |
| **2** | bis Stufe 2 | RO08 |
| **3** | bis Stufe 3 | RO07 und RO08 |

**Wichtig:** Bei normalem Heizbedarf schaltet die FoxAir die Stufen nacheinander hoch. Bei sehr niedriger Außentemperatur kann sie dagegen **direkt die mit H18 gewählte maximale Stufe** einschalten. H18 ist also keine Einstellung, die in jedem Fall nur einen bestimmten Heizstab dauerhaft auswählt.

### Wie funktioniert die zeitliche Staffelung?

**A32 / Modbus 1050** bestimmt den Zeitabstand in Minuten. Die Firmware begrenzt den intern verwendeten Wert auf **mindestens 10 Minuten**.

Besteht weiterhin Heizbedarf, gelten im normalen Betrieb diese drei Zeitgrenzen:

| Erreichte Zeit | Bedingung | Ausgangszustand |
| --- | --- | --- |
| **1 × A32** | H18 ≥ 1 | Stufe 1: RO07 |
| **2 × A32** | H18 ≥ 2 | Stufe 2: RO08, RO07 aus |
| **3 × A32** | H18 ≥ 3 | Stufe 3: RO07 + RO08 |

Beispiel **A32 = 30 Minuten**: 30 / 60 / 90 Minuten. Bei **A32 = 60 Minuten**: 60 / 120 / 180 Minuten.

**Wichtig:** Die Wartezeit zählt nur, solange die Voraussetzungen für die Zuschaltung erfüllt sind. Wird das Temperaturziel erreicht oder die Zusatzheizung gesperrt, kann die Staffelung unterbrochen werden.

### Temperaturbedingungen und früheres Abschalten

Für die normale Zuschaltung sind insbesondere diese Zusammenhänge relevant:

- **A31** legt eine Außentemperaturgrenze fest.
- **A33** legt fest, wie groß die relevante Temperaturabweichung für die Zusatzheizungsanforderung sein muss.
- **H17** beschreibt eine Temperaturdifferenz für das Abschalten beziehungsweise die Rücknahme der elektrischen Zusatzheizung.
- Die ausgewertete Wasser- oder Regeltemperatur kann sich je nach Anlagen- und Betriebsart unterscheiden; die allgemeine Wahl der Regeltemperatur erfolgt über **H25**.

Die Steuerung prüft den Heizbedarf auch nach dem Zuschalten weiter. Nur weil A32 abgelaufen ist, muss sie daher nicht automatisch bis zur dritten Stufe hochschalten.

### Sonderfall: sehr niedrige Außentemperatur (R45)

**R45 / Modbus 1231** ist ein zusätzlicher Außentemperatur-Grenzwert. Wird er unterschritten und sind die übrigen Voraussetzungen erfüllt, kann die FoxAir **direkt die über H18 festgelegte Stufe einschalten**, ohne die normalen Wartezeiten abzuwarten.

Für die Rückschaltung gibt es eine Hysterese von etwa **2 °C**. Das verhindert, dass der Heizstab bei kleinen Temperaturschwankungen ständig ein- und ausgeschaltet wird.

Für **A31 und R45** zählt die Außentemperatur des **externen Fühlers**, wenn dieser über **Modbus 1463** aktiviert ist und gültige Werte liefert. Andernfalls wird der eingebaute Fühler **T04** verwendet. Für andere Funktionen, beispielsweise Teile der Abtauregelung, kann unabhängig davon weiterhin T04 maßgeblich sein.

### Wichtige Einstellungen und Statuswerte

| Parameter / Register | Bedeutung |
| --- | --- |
| **H18 / 1032** | Maximale elektrische Heizstufe 1–3 |
| **R35 / 1173** | Zuordnung/Verwendung der elektrischen Zusatzheizung; bekannte Menüwerte: 0 = nicht verwendet, 1 = Heizwasserkreis, 2 = Speicher-/Tankheizung |
| **A31 / 1049** | Außentemperaturgrenze für die normale Zuschaltung |
| **A32 / 1050** | Zeitabstand zwischen den Stufen in Minuten |
| **A33 / 1063** | Erforderliche Temperaturabweichung zur Zuschaltung (Temperatur-Rohwert in Zehntelgrad) |
| **H17 / 1031** | Temperaturdifferenz zur Abschaltung |
| **R45 / 1231** | Außentemperaturgrenze für die Heizstabzuschaltung ohne Wartezeit |
| **D21 / 1126** | Separate Freigabe der elektrischen Zusatzheizung beim Abtauen |
| **1463** | Auswahl lokaler oder externer Außentemperatur |
| **2019 Bit 7 / 8** | Ausgang RO07 / RO08, jeweils 0 = aus, 1 = ein |

Die genannten Registerwerte sind **nicht automatisch sinnvolle Einstellwerte**. Beispielsweise sind 30 Minuten und eine 1-/2-kW-Bestückung nur Rechen- beziehungsweise Anlagenbeispiele.

### Abtauung, Warmwasser und Schutzfunktionen

Auch beim Abtauen und in anderen Betriebszuständen berücksichtigt die **Firmware V3.5** weitere Freigaben und Schutzbedingungen. Daher bedeutet eine aktivierte **D21** nicht, dass der Heizstab bei jedem Abtauvorgang tatsächlich eingeschaltet wird.

Ein **separater Ausgang RO13** ist für den **Elektroheizer des Warmwasserspeichers** vorgesehen. Er ist von den beiden normalen Zusatzheizstufen zu unterscheiden:

- **RO07 / RO08:** Heizstufen 1 und 2, Status **2019 Bit 7 / 8**
- **RO13:** Warmwasserspeicher-Heizer, Status **2018 Bit 0**

Die Statusregister **2018 und 2019** sind **nur lesbar** und dürfen nicht als Steuerregister beschrieben werden.

### Wie kann ich die Funktion prüfen?

Am einfachsten die betreffenden Einstellungen, den Betriebszustand, die Soll-/Isttemperaturen und die Ausgänge **2019 Bit 7/8** gemeinsam protokollieren. Für die zeitliche Staffelung muss die Wärmeanforderung lange genug anliegen; bei A32 = 30 Minuten sind insbesondere die Zustände um 30, 60 und 90 Minuten interessant.

Wenn die Ausgangsbits schalten, der Heizstab aber kalt bleibt, sollte die externe Leistungsversorgung beziehungsweise Schütz- und Sicherheitskette geprüft werden. Bleiben die Bits aus, können fehlender Heizbedarf, ungeeignete Einstellungen oder aktive Sperren die Ursache sein.

Weitere Informationen: [Relaisausgänge](relais_ausgaenge.md), [Heizungsregelung und Heizkurve](regelung_heizkurve.md) und [Abtauen und Frostschutz](abtauen_frostschutz.md).

> **Sicherheit:** Heizstäbe **niemals direkt an RO07/RO08 anschließen**, sondern über ein geeignetes Leistungsrelais oder Schütz schalten. Absicherung und unabhängiger Übertemperaturschutz müssen zur Anlage passen.
