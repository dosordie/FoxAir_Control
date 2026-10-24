# Auslauftemperatur und Kompressorfrequenz – wie regelt die FoxAir?

Die FoxAir passt ihre Heizleistung hauptsächlich über die **Drehzahl des Kompressors** an. Diese wird als **Frequenz in Hertz (Hz)** angezeigt.

Dabei gilt: **Die Kompressorfrequenz wird nicht einfach aus der Vorlauftemperatur berechnet.** Entscheidend ist vor allem, wie weit die gemessene Temperatur vom gewünschten Wert entfernt ist und wie sie sich im Laufe der Zeit verändert.

Die folgenden Erklärungen beziehen sich auf die untersuchte **Mainboard-Firmware V3.5**. Bei älteren Firmwareständen kann sich die Regelung im Detail unterscheiden.

## Welche Temperatur soll erreicht werden?

Steht **H25 = 0 (Outlet Water Temp.)**, orientiert sich die Wärmepumpe an der **Auslauftemperatur T02**, also am Vorlauf.

Ein Beispiel:

- Gewünscht sind **35 °C Vorlauf**.
- Tatsächlich kommen nur **30 °C** aus der Wärmepumpe.
- Die Regelung erkennt, dass noch Wärme benötigt wird, und kann die Kompressorleistung erhöhen.
- Nähert sich der Vorlauf den **35 °C**, wird weniger Leistung benötigt.

Der gewünschte Wert kann fest eingestellt oder durch eine **Heizkurve** abhängig von der Außentemperatur verändert werden. Deshalb ist der **aktuell gültige Sollwert** wichtig – nicht nur die Temperatur, die einmal manuell eingestellt wurde.

Was H25 und die Heizkurve genau machen, steht hier:

[Heizungsregelung und Heizkurve – welche Temperatur soll die FoxAir erreichen?](regelung_heizkurve.md)

## Wie verändert die FoxAir die Kompressorfrequenz?

Die Regelung schaut nicht nur auf den aktuellen Abstand zum Sollwert, sondern auch darauf, wie sich die Temperatur entwickelt. In der Firmware übernimmt das ein sogenannter **PID-Regler**.

Vereinfacht lässt sich das so beschreiben:

| Beobachtung | Typische Reaktion |
| --- | --- |
| **Vorlauf deutlich unter Soll** | Der Kompressor kann höher drehen, damit mehr Wärme erzeugt wird. |
| **Vorlauf nähert sich dem Soll** | Die Regelung kann die Frequenz zunächst halten oder schrittweise anpassen. |
| **Vorlauf über Soll** | Die Regelung versucht, die Heizleistung zu senken. Reicht das nicht, schaltet der Verdichter bei entsprechender Abschaltbedingung ab. |

Die Frequenz muss sich also **nicht sofort** ändern, nur weil sich die Vorlauftemperatur um 1 °C verändert hat.

Ebenso gibt es keine feste Formel wie **„Vorlauftemperatur in °C + 2 = Kompressorfrequenz in Hz“**. Wenn diese beiden Werte zeitweise ähnlich aussehen, ist das kein Beweis für einen solchen Zusammenhang.

## Warum dreht der Kompressor manchmal nicht weiter herunter?

Die FoxAir kann ihre Leistung nicht beliebig weit reduzieren. Der Verdichter hat eine **Mindestfrequenz**.

Diese wird unter anderem durch **C02 (minimale Kompressorfrequenz)** vorgegeben. Dazu können je nach Betriebszustand weitere Grenzen kommen.

Wenn das Haus gerade weniger Wärme benötigt, als die Wärmepumpe bei ihrer niedrigsten möglichen Leistung erzeugt, kann sie die Solltemperatur überschreiten und anschließend abschalten. Später startet sie bei erneutem Wärmebedarf wieder.

**Das ist nicht automatisch eine fehlerhafte Regelung.** Es kann schlicht daran liegen, dass die aktuell benötigte Heizleistung zu gering für einen dauerhaft laufenden Verdichter ist.

Die Mindestfrequenz sollte nicht auf Verdacht abgesenkt werden: Die zulässigen Betriebsgrenzen des Kompressors müssen eingehalten werden.

## Warum dreht der Kompressor manchmal nicht schneller hoch?

Auch nach oben ist die Drehzahl begrenzt. **C03** gibt die eingestellte Höchstfrequenz vor.

Zusätzlich können Schutzfunktionen die Leistung vorübergehend einschränken, etwa aufgrund von Druck, Temperatur oder elektrischer Belastung. Auch bestimmte Betriebsarten und externe Steuerungen können Grenzen setzen.

Deshalb kann die Vorlauftemperatur deutlich unter dem Soll liegen, obwohl die Wärmepumpe die Frequenz nicht weiter erhöht.

Ein kurzer Anstieg oder Abfall der Frequenz muss ebenfalls kein Fehler sein. Zum Beispiel verändern [Abtauen und Frostschutz](abtauen_frostschutz.md) sowie die [Ölrückführung (Oil Return)](oelrueckfuehrung.md) den normalen Betriebsablauf.

## Warum verhält sich die Frequenz beim Warmwasser anders?

Bei der **Warmwasserbereitung** wird ein Speicher erwärmt. Dafür muss das Heizwasser Wärme an den Speicher übertragen.

**Speichertemperatur und Vorlauftemperatur sind dabei zwei verschiedene Werte.** Die Wärmepumpe muss das Heizwasser normalerweise wärmer machen als den Speicher, damit die Wärme übertragen werden kann.

Mit zunehmender Speichertemperatur verändern sich die Arbeitsbedingungen. Dadurch können auch Frequenz und Heizleistung anders verlaufen als beim normalen Heizen.

Bei Problemen mit der Warmwasserbereitung sollte man deshalb nicht nur die Kompressorfrequenz anschauen, sondern auch den **Warmwasser-Sollwert, die tatsächliche Speichertemperatur und die Einlass- und Auslasstemperatur**.

Weitere Grundlagen findest du unter [Warmwasser mit der FoxAir](warmwasser.md).

## Was bedeutet eine Spreizung von nur 2 °C?

Die **Spreizung** ist die Temperaturdifferenz zwischen Vorlauf (Auslass / T02) und Rücklauf (Einlass / T01).

Sie hängt sowohl von der **abgegebenen Wärmeleistung** als auch vom **Wasserdurchfluss** ab:

- **Mehr Wasserdurchfluss** bei gleicher Heizleistung → kleinere Spreizung.
- **Weniger Wasserdurchfluss** bei gleicher Heizleistung → größere Spreizung.
- **Weniger Heizleistung** bei gleichem Wasserdurchfluss → ebenfalls kleinere Spreizung.

**Eine Spreizung von 2 °C ist daher nicht automatisch ein Fehler.** Bei 1 m³/h Wasserdurchfluss entsprechen 2 °C Spreizung ungefähr 2,3 kW übertragener Wärmeleistung.

Eine möglichst große Spreizung ist kein Selbstzweck. Der Durchfluss muss weiterhin zur Anlage passen und insbesondere für den Abtaubetrieb ausreichend sein.

### Hat die PWM-Umwälzpumpe damit zu tun?

Ja. Über die Pumpendrehzahl verändert sich der Wasserdurchfluss und damit auch die Spreizung.

**Wichtig:** Eine korrekt angeschlossene PWM-Leitung bedeutet noch nicht, dass die Wärmepumpe ihre Pumpendrehzahl automatisch nach der Spreizung regelt.

Die automatische Spreizungsregelung der Pumpe ist bei der untersuchten Mainboard-Firmwarefamilie **ab V3.3** vorhanden. Dafür müssen der richtige Pumpentyp (**H31**) und der Automatikbetrieb (**P10 = 0 %**) eingestellt sein. Über **P11** wird die gewünschte Spreizung vorgegeben.

Bei älterer Firmware oder fester Pumpendrehzahl kann die Spreizung deshalb niedriger ausfallen, ohne dass die Kompressorregelung fehlerhaft ist.

Mehr dazu: [Wasserdurchfluss und Pumpenbetriebsarten](wasserdurchfluss_pumpe.md) und [Automatische Regelung der Umwälzpumpe](automatische_up_regelung.md).

## Wie finde ich heraus, ob die Regelung richtig arbeitet?

Ein einzelner Messwert sagt meist wenig aus. Besser ist es, die Entwicklung über mehrere Minuten zu beobachten – am besten getrennt im **Heizbetrieb** und bei der **Warmwasserbereitung**.

Hilfreich sind folgende Werte:

| Wert | Warum ist er interessant? |
| --- | --- |
| **Aktueller Temperatur-Sollwert** | Welche Temperatur soll tatsächlich erreicht werden? |
| **Einlass- und Auslasstemperatur (T01 / T02)** | Wie warm ist das Wasser vor und nach der Wärmepumpe? |
| **Kompressor-Sollfrequenz und Istfrequenz** | Welche Drehzahl wird angefordert und welche tatsächlich erreicht? |
| **Wasserdurchfluss** | Hilft dabei, die Spreizung richtig einzuschätzen. |
| **H25, C02 und C03** | Welche Temperaturregelung und Frequenzgrenzen sind eingestellt? |
| **Pumpeneinstellung (P10 / H31)** | Läuft die Umwälzpumpe fest oder automatisch? |

Diese Werte lassen sich – je nach Anzeige und Verbindung – mit **FoxAir Control**, über die **WarmLink-App** oder am Display nachvollziehen.

Als Anhaltspunkte:

- **Kompressor läuft nahe seiner Mindestfrequenz:** Möglicherweise ist die benötigte Wärmeleistung zu gering, um weiter herunterzuregeln.
- **Vorlauf bleibt deutlich unter Soll und die Frequenz steigt nicht:** Einstellungen, Betriebszustand und mögliche Frequenzbegrenzungen prüfen.
- **Angeforderte und tatsächliche Kompressorfrequenz weichen länger deutlich voneinander ab:** Mögliche Betriebs- oder Schutzbegrenzungen prüfen.
- **Spreizung ist klein, Durchfluss ist hoch:** Erst den Zusammenhang mit der Pumpendrehzahl und der aktuellen Heizleistung beurteilen.

## Kann ein Firmwareupdate helfen?

**Möglich, aber nicht garantiert.** Die Mainboard-Firmware V3.3 und neuer bietet gegenüber der älteren V1.3 zusätzliche Funktionen, unter anderem die automatische Regelung der Umwälzpumpe auf eine gewünschte Spreizung.

Ein Update bedeutet aber nicht automatisch, dass der Kompressor danach schneller hochregelt oder weiter heruntermodulieren kann.

Vorher sollten **Mainboard-Firmwareversion, Einstellungen und Messwerte** geprüft werden. Die **Display-Firmware** ist davon unabhängig.

Mehr dazu: [Firmware-Versionen und Update](firmware.md).

---

**Kurz gesagt:** Die Kompressorfrequenz richtet sich nach dem Wärmebedarf und mehreren Betriebsgrenzen, nicht nach einer festen Umrechnung der Vorlauftemperatur in Hertz. Eine kleine Spreizung oder eine zeitweise gleichbleibende Frequenz ist deshalb noch kein Hinweis auf einen Defekt.
