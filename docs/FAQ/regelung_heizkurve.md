# Heizungsregelung und Heizkurve – welche Temperatur soll die FoxAir erreichen?

Bei der FoxAir bestimmen vor allem zwei Einstellungen, **welche Temperatur sie erreichen soll**:

- **H25:** An welcher Temperatur orientiert sich die Heizungsregelung?
- **H36 / AT-Entschädigung:** Soll die gewünschte Heizwassertemperatur mit der Außentemperatur verändert werden?

Wenn diese Einstellungen nicht zusammenpassen, wirkt es manchmal so, als würde die Wärmepumpe zu früh abschalten, nicht starten oder einen unerwarteten Sollwert verwenden.

## H25 – welche Temperatur wird verwendet?

| H25 | Einstellung | Was bedeutet das? |
| ---: | --- | --- |
| **0** | **Outlet Water Temp.** (Vorlauf / Auslass) | Die Wärmepumpe orientiert sich an der Temperatur des Wassers, das sie zum Heizkreis schickt. |
| **1** | **Room Temp.** (Raum) | Ein Raumfühler beeinflusst die benötigte Heizwassertemperatur. |
| **2** | **Buffer Tank Temp.** (Puffer) | Die Temperatur eines Pufferspeichers dient als Vorgabe für die Regelung. |
| **3** | **Inlet Water Temp.** (Rücklauf / Einlass) | Die Wärmepumpe orientiert sich an der Temperatur des zurückkommenden Wassers. |

**Für viele Anlagen ohne zusätzlichen Raum- oder Pufferfühler ist H25 = 0 ein sinnvoller Ausgangspunkt.** Das gilt besonders, wenn die FoxAir direkt einen Heizkreis versorgt.

Bei **H25 = 1 oder 2** muss der passende Fühler auch wirklich angeschlossen und richtig positioniert sein. Fehlt er, kann die Wärmepumpe die gewünschte Raum- bzw. Puffertemperatur nicht zuverlässig beurteilen.

Wichtig: Auch bei einer Raumtemperaturregelung wird die Heizleistung letztlich über das erwärmte Wasser bereitgestellt. Das ist keine direkte Einstellung der Kompressorfrequenz.

## Feste Vorlauftemperatur oder Heizkurve?

Es gibt zwei typische Möglichkeiten:

**Feste Solltemperatur:** Du stellst beispielsweise 35 °C ein. Dieser Wert bleibt grundsätzlich gleich, egal ob es draußen +10 °C oder -5 °C hat. Weitere aktivierte Funktionen können ihn dennoch beeinflussen.

**Heizkurve / AT-Entschädigung:** Die Wärmepumpe passt die gewünschte Heizwassertemperatur an die Außentemperatur an.

Die Grundidee ist einfach:

- **Draußen wärmer:** Das Haus braucht meist eine niedrigere Heizwassertemperatur.
- **Draußen kälter:** Das Haus braucht meist eine höhere Heizwassertemperatur.

Damit kann die Wärmepumpe witterungsabhängig heizen, ohne dass du die Solltemperatur ständig selbst ändern musst.

## H36 – die Heizkurve einstellen

Bei den untersuchten Mainboard-Firmwares **V3.4 und V3.5** gibt es folgende Möglichkeiten:

| H36 | Funktion |
| ---: | --- |
| **0 – Aus** | Keine Außentemperatur-Anpassung über diese Heizkurve |
| **1 – Linear** | Eine einfache Heizkurve mit Steigung und Verschiebung |
| **2 – 7-Punkt** | Du legst die gewünschte Heizwassertemperatur für sieben Außentemperaturen fest |

### Lineare Heizkurve

Hier legst du die Kurve über **Steigung** und **Verschiebung / Offset** fest:

- Über die **Steigung** bestimmst du, wie stark sich die Solltemperatur verändert, wenn es draußen kälter oder wärmer wird.
- Mit der **Verschiebung** hebst oder senkst du das Temperaturniveau der Kurve.

Ist es bei kaltem Wetter zu kühl im Haus, kann eine steilere Kurve sinnvoll sein. Ist es dagegen bei fast jeder Außentemperatur zu kühl, kann eher eine Verschiebung nach oben nötig sein.

Änderungen am besten in kleinen Schritten durchführen und dem Haus genügend Zeit geben, darauf zu reagieren.

### 7-Punkt-Heizkurve

Hier kannst du für diese sieben festen Außentemperaturen jeweils eine gewünschte Heizwassertemperatur einstellen:

**-20 / -10 / -5 / 0 / +5 / +10 / +20 °C**

Die FoxAir berechnet die Werte dazwischen automatisch.

**Beispiel:** Du stellst bei -5 °C Außentemperatur einen Vorlauf-Sollwert von 36 °C und bei 0 °C einen Wert von 32 °C ein. Bei -2,5 °C ergibt sich daraus ungefähr **34 °C**. Das ist nur ein Rechenbeispiel, keine allgemeine Einstellungsempfehlung.

Außerhalb des Bereichs von -20 bis +20 °C verwendet die untersuchte Kurvenberechnung den jeweiligen Randpunkt. Außerdem gelten weiterhin die eingestellten **minimalen und maximalen Heiz-Solltemperaturen (R10 / R11)**.

Die Kurve sollte zu deinem Gebäude und deinen Heizflächen passen. Eine pauschal richtige Einstellung gibt es nicht.

## Wo kann ich die Heizkurve ansehen und ändern?

Die Einstellungen lassen sich – je nach Firmware und vorhandener Anzeige – am **Display**, über **WarmLink** oder mit **FoxAir Control** aufrufen.

In FoxAir Control findest du dafür die **AT-Kompensation**. Dort kannst du die Kurvenwerte ansehen, ändern und die berechnete Solltemperatur nachvollziehen.

Wichtig ist, nach einer Änderung zu prüfen, ob die neuen Werte tatsächlich übernommen wurden und welcher **aktuelle Sollwert** daraus entsteht. Eine aktive Heizkurve kann dafür sorgen, dass der wirksame Sollwert von dem ursprünglich manuell eingestellten Wert abweicht.

## Warum startet die Wärmepumpe nicht oder heizt anders als erwartet?

Prüfe zunächst diese Punkte:

1. **H25:** Wird die richtige Temperatur als Grundlage verwendet?
2. **Fühler:** Ist ein benötigter Raum- oder Puffertemperaturfühler vorhanden und zeigt er plausible Werte?
3. **H36:** Ist eine Heizkurve aktiv, obwohl du mit einem festen Sollwert rechnest?
4. **Soll-/Isttemperatur:** Welche Heizwassertemperatur soll die Wärmepumpe *aktuell* erreichen, und wie warm ist das Wasser tatsächlich?
5. **Betriebszustand:** Ist Heizen überhaupt freigegeben, oder befindet sich die Wärmepumpe bereits in einer Wartephase, innerhalb ihrer Ein-/Ausschaltschwellen oder in einer Störung?

Für einen übersichtlichen Test kann es helfen, vorübergehend **H25 = 0** zu wählen und die **AT-Entschädigung (H36 = 0)** auszuschalten. Mit einer geeigneten festen Vorlauftemperatur lässt sich dann leichter prüfen, ob die Wärmepumpe grundsätzlich erwartungsgemäß arbeitet. Anschließend kann die Heizkurve wieder aktiviert werden.

## Wie regelt die FoxAir anschließend ihre Leistung?

**Die Heizkurve bestimmt die gewünschte Temperatur – nicht direkt die Kompressorfrequenz.** Wie schnell die FoxAir aufheizt, warum der Verdichter manchmal nicht weiter herunterregelt und welche Grenzen es gibt, ist in einem eigenen Artikel erklärt:

[Auslauftemperatur und Kompressorfrequenz – wie regelt die FoxAir?](auslauftemperatur_kompressorfrequenz.md)

## Ab welcher Firmware gelten diese Angaben?

Die beschriebene **lineare und 7-Punkt-Heizkurve** ist für die untersuchten **Mainboard-Firmwares V3.4 und V3.5** dokumentiert. Bei älteren Versionen kann der Funktionsumfang abweichen. Ein Firmwareupdate sollte deshalb nicht allein aufgrund einer abweichenden Anzeige durchgeführt werden.

Mehr dazu: [Firmware-Versionen und Update](firmware.md).
