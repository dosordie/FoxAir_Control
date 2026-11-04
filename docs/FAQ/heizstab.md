# Elektrischer Heizstab – Zuschaltung und Heizstufen

Die FoxAir-/PHNIX-Wärmepumpe kann eine **externe elektrische Zusatzheizung** ansteuern. Ein Heizstab ist bei der üblichen FoxAir GL9 **nicht fest eingebaut**; die Steuerung stellt dafür Ausgänge bereit.

## Kurz erklärt

### Wofür ist die Zusatzheizung gedacht?

Bei großer Kälte oder wenn die Wärmepumpe die gewünschte Temperatur über längere Zeit nicht erreicht, kann ein angeschlossener Heizstab zusätzliche Wärme liefern. Auch für bestimmte Sonderbetriebsarten, beispielsweise das Abtauen, gibt es eine eigene Freigabe.

Die elektrische Zusatzheizung arbeitet mit einem **COP von ungefähr 1**. Deshalb sollte sie nur dann mitlaufen, wenn die zusätzliche Leistung wirklich benötigt wird.

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

**Ja.** In der untersuchten Firmware V3.5 gibt es neben einem unmittelbaren Zuschaltpfad auch eine **zeitabhängige Staffelung**:

1. Zuerst kann **Stufe 1** eingeschaltet werden.
2. Bleibt der zusätzliche Wärmebedarf bestehen, kann die Steuerung auf **Stufe 2** wechseln. Stufe 1 wird dabei abgeschaltet.
3. Bei weiterem Bedarf kann sie schließlich **beide Heizstäbe gemeinsam** einschalten.

Die im Menü ausgewählte Heizstufe begrenzt, **wie weit die Steuerung hochschalten darf**. Das bedeutet insbesondere: Die Einstellung „Stufe 2“ bedeutet im normalen Ablauf nicht zwingend, dass ausschließlich der zweite Heizstab verwendet wird.

### Wann wird zugeschaltet?

Entscheidend sind unter anderem **Heizbedarf, Soll-/Isttemperatur, Außentemperatur und die eingestellte Wartezeit**. „Nach 30 Minuten“ ist keine allgemeine Werkseinstellung: Die Wartezeit ist einstellbar.

Bei sehr niedrigen Außentemperaturen kann ein **separater Kältepfad** die normale Verzögerung umgehen. Andere Betriebszustände, Störungen oder Schutzfunktionen können die Zuschaltung verhindern oder beenden.

### Worauf muss ich beim Anschluss achten?

Die Heizstäbe werden **nicht allein durch die Menüeinstellung anschlussfertig**. Die Ausgänge sind Steuersignale; erforderliche Leistungsschütze, passende elektrische Absicherung, Übertemperaturschutz und die zulässigen Anschlusswerte müssen zur Anlage passen. Die konkrete Mainboard- und Klemmfeldbelegung ist vor der Verdrahtung zu prüfen.

---

## Technischer Teil: Regelung und Zusammenhänge (Firmware V3.5)

Die folgenden Angaben beziehen sich auf die untersuchte **Mainboard-Firmware V3.5 der Softwarefamilie 82400644**. Die Schaltfolge und wesentliche Zeit-/Temperaturpfade wurden im disassemblierten Firmwarecode nachvollzogen. Wo eine Hardware- oder Schutzpriorität nicht vollständig geschlossen ist, wird das ausdrücklich gekennzeichnet.

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

Dieser Unterschied ist wichtig: Der Firmwarecode enthält einen Zweig, der **direkt** die zu H18 passende Ausgangskombination setzt, und einen anderen, der die Stufen **nacheinander** erreicht. Die frühere Annahme „H18 wählt immer ausschließlich eine feste Relaiskombination“ ist damit widerlegt.

### Wie funktioniert die zeitliche Staffelung?

**A32 / Modbus 1050** bestimmt den Zeitabstand in Minuten. Die Firmware begrenzt den intern verwendeten Wert auf **mindestens 10 Minuten**.

Bei weiterhin erfüllter Heizanforderung sind im normalen Zuschaltpfad drei Zeitgrenzen nachweisbar:

| Erreichte Zeit | Bedingung | Ausgangszustand |
| --- | --- | --- |
| **1 × A32** | H18 ≥ 1 | Stufe 1: RO07 |
| **2 × A32** | H18 ≥ 2 | Stufe 2: RO08, RO07 aus |
| **3 × A32** | H18 ≥ 3 | Stufe 3: RO07 + RO08 |

Beispiel **A32 = 30 Minuten**: 30 / 60 / 90 Minuten. Bei **A32 = 60 Minuten**: 60 / 120 / 180 Minuten.

Die Firmware zählt hierfür zunächst einen kürzeren Zeitabschnitt bis **120 Zyklen** und erhöht anschließend den Minutenzähler. Die bekannte zyklische Zeitbasis dieser Firmware beträgt rund **0,5 Sekunden pro Aufruf**, sodass 120 Zyklen ungefähr einer Minute entsprechen.

**Keine feste Einschaltgarantie:** Der Zeitfortschritt ist an Freigabebedingungen gebunden. Wird das Temperaturziel erreicht oder ein Sperrzustand aktiv, ist das nicht mit einer ununterbrochen laufenden Stoppuhr gleichzusetzen.

### Temperaturbedingungen und früheres Abschalten

Für die normale Zuschaltung sind insbesondere diese Zusammenhänge relevant:

- **A31** legt eine Außentemperaturgrenze fest.
- **A33** legt fest, wie groß die relevante Temperaturabweichung für die Zusatzheizungsanforderung sein muss.
- **H17** beschreibt eine Temperaturdifferenz für das Abschalten beziehungsweise die Rücknahme der elektrischen Zusatzheizung.
- Die ausgewertete Wasser- oder Regeltemperatur kann sich je nach Anlagen- und Betriebsart unterscheiden; die allgemeine Wahl der Regeltemperatur erfolgt über **H25**.

Die Firmware hat ausdrücklich getrennte **Einschalt-, Halte- und Rücknahmezweige**. Deshalb darf man aus A32 allein nicht schließen, dass ein Heizstab unabhängig von der tatsächlichen Temperatur bis zur dritten Stufe hochschaltet.

### Sonderfall: sehr niedrige Außentemperatur (R45)

**R45 / Modbus 1231** ist ein zusätzlicher Kälte-Grenzwert. Für diesen Pfad gibt es eine **unmittelbare Ausgangswahl nach H18**, ohne zuvor sämtliche Stufenwartezeiten zu durchlaufen.

Die R45-Freigabe besitzt eine Rückschalthysterese von etwa **2 K**. Das ist eine eigene Logik und nicht mit der normalen A31-/A32-/A33-Zuschaltung zu verwechseln.

Für **A31 und R45** wird die **wirksame Außentemperatur** verwendet: Bei aktiviertem und gültigem externem Außentemperaturfühler (**Modbus 1463**) kann dessen Messwert maßgeblich sein; andernfalls wird auf den lokalen Sensor zurückgegriffen. Andere Wärmepumpenfunktionen, etwa Teile der Abtauregelung, nutzen dagegen weiterhin den lokalen T04.

### Wichtige Einstellungen und Statuswerte

| Parameter / Register | Bedeutung |
| --- | --- |
| **H18 / 1032** | Maximale elektrische Heizstufe 1–3 |
| **R35 / 1173** | Zuordnung/Verwendung der elektrischen Zusatzheizung; bekannte Menüwerte: 0 = nicht verwendet, 1 = Heizwasserkreis, 2 = Speicher-/Tankheizung |
| **A31 / 1049** | Außentemperaturgrenze für die normale Zuschaltung |
| **A32 / 1050** | Zeitabstand zwischen den Stufen in Minuten |
| **A33 / 1063** | Erforderliche Temperaturabweichung zur Zuschaltung (Temperatur-Rohwert in Zehntelgrad) |
| **H17 / 1031** | Temperaturdifferenz zur Abschaltung |
| **R45 / 1231** | Außentemperaturgrenze für den unmittelbaren Kältepfad |
| **D21 / 1126** | Separate Freigabe der elektrischen Zusatzheizung beim Abtauen |
| **1463** | Auswahl lokaler oder externer Außentemperatur |
| **2019 Bit 7 / 8** | Ausgang RO07 / RO08, jeweils 0 = aus, 1 = ein |

Die genannten Registerwerte sind **nicht automatisch sinnvolle Einstellwerte**. Beispielsweise sind 30 Minuten und eine 1-/2-kW-Bestückung nur Rechen- beziehungsweise Anlagenbeispiele.

### Abtauung, Warmwasser und Schutzfunktionen

Die V3.5 besitzt weitere Bedingungen für Betriebsart, Verdichterzustand, Abtauung und Sicherheitsstatus. Insbesondere sind vor einer Zuschaltung mehrere Status- und Sperrprüfungen zu erkennen. Die **vollständige Prioritätsreihenfolge aller Schutz- und Abtaustufen bis zu den physischen Ausgängen** ist aus den bisher rückverfolgten Pfaden noch **nicht abschließend bewiesen**; daher lässt sich eine Heizstabeinschaltung beim Abtauen nicht allein aus D21 garantieren.

Ein **separater Ausgang RO13** ist für den **Elektroheizer des Warmwasserspeichers** vorgesehen. Er ist von den beiden normalen Zusatzheizstufen zu unterscheiden:

- **RO07 / RO08:** Heizstufen 1 und 2, Status **2019 Bit 7 / 8**
- **RO13:** Warmwasserspeicher-Heizer, Status **2018 Bit 0**

Die Statusregister **2018 und 2019** sind **nur lesbar** und dürfen nicht als Steuerregister beschrieben werden.

### Wie kann ich die Funktion prüfen?

Am einfachsten die betreffenden Einstellungen, den Betriebszustand, die Soll-/Isttemperaturen und die Ausgänge **2019 Bit 7/8** gemeinsam protokollieren. Für die zeitliche Staffelung muss die Wärmeanforderung lange genug anliegen; bei A32 = 30 Minuten sind insbesondere die Zustände um 30, 60 und 90 Minuten interessant.

Wenn die Ausgangsbits schalten, der Heizstab aber kalt bleibt, sollte die externe Leistungsversorgung beziehungsweise Schütz- und Sicherheitskette geprüft werden. Bleiben die Bits aus, können fehlender Heizbedarf, ungeeignete Einstellungen oder aktive Sperren die Ursache sein.

### Stand der Firmwareanalyse

**Direkt im V3.5-Code belegt:** H18 wird in zwei unterschiedlichen Schaltpfaden verwendet; die Ausgangskombinationen der drei Stufen, die gestaffelten Schwellen bei 1×/2×/3×A32, die Mindest-Zeitbasis von 10 Minuten, der Minutenzähler sowie der R45-Kältepfad mit etwa 2 K Hysterese.

**Nicht vollständig geschlossen:** die fachliche Benennung jedes internen Schutz- und Sonderstatus, die Priorität sämtlicher Abtau-/Störfallpfade und die elektrische Verdrahtung jedes Geräte-Klemmfelds. Solche Aussagen wären ohne zusätzlichen Code-/Hardwareabgleich nicht belastbar.

Weitere Informationen: [Relaisausgänge](relais_ausgaenge.md), [Heizungsregelung und Heizkurve](regelung_heizkurve.md) und [Abtauen und Frostschutz](abtauen_frostschutz.md).

> **Sicherheit:** Externe elektrische Heizstäbe nur mit passenden Schaltgeräten, Absicherung und unabhängigen Übertemperatur-Sicherheitseinrichtungen betreiben. Das Mainboardrelais nicht ungeprüft als direkten Lastanschluss verwenden.
