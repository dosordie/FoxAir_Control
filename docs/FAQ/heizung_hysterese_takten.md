# Warum taktet die FoxAir? – Heizungs-Hysterese R04/R05

Wenn die FoxAir ihre Solltemperatur erreicht, reduziert sie zunächst die Kompressorleistung. Reicht die niedrigste mögliche Leistung immer noch aus, um das Heizwasser weiter zu erwärmen, kann der Verdichter abschalten. Sobald wieder Wärme benötigt wird, startet er erneut. Dieses **Ein- und Ausschalten nennt man Takten**.

Wie oft die Wärmepumpe taktet, hängt nicht nur von der Heizkurve und der benötigten Heizleistung ab. Auch die **Ein- und Ausschaltschwellen R04 und R05** spielen eine Rolle.

## Wann schaltet die Wärmepumpe im Heizbetrieb ab oder wieder ein?

Die FoxAir verwendet zwei getrennte Temperaturdifferenzen:

| Einstellung | Bedeutung |
| --- | --- |
| **R04 / Register 1160** | Wiedereinschalt-Differenz **unterhalb** des Heizsollwerts |
| **R05 / Register 1161** | Ausschalt-Differenz **oberhalb** des Heizsollwerts |

Vereinfacht gelten für die normale Heizungsregelung folgende Schwellen:

- **Einschaltanforderung:** wirksame Temperatur ist höchstens **Heizsollwert − R04**.
- **Ausschaltanforderung:** wirksame Temperatur ist mindestens **Heizsollwert + R05**.

**Beispiel:** Bei 35 °C Heizsollwert, R04 = 2 K und R05 = 1 K liegt die Einschaltschwelle bei **33 °C** und die Ausschaltschwelle bei **36 °C**. Dazwischen bleibt die bisherige Heizanforderung grundsätzlich erhalten.

Entscheidend ist dabei der **aktuell wirksame Heizsollwert**, der beispielsweise durch die [Heizkurve](regelung_heizkurve.md) verändert werden kann. Welche Temperatur zur Regelung verwendet wird, hängt außerdem von **H25** ab (beispielsweise Auslauf- oder Puffertemperatur).

R04 und R05 sind also **keine Zeitangaben** und auch nicht einfach zwei Namen für denselben Hysteresewert.

## Warum läuft der Verdichter nach Überschreiten der Ausschaltschwelle noch weiter?

Die untersuchte **Mainboard-Firmware V3.4 (Softwarecode 82400644)** schaltet bei Erreichen von „Soll + R05“ nicht sofort den Kompressor aus.

Zunächst muss die Abschaltanforderung über einen internen Filter ausreichend lange bestehen bleiben. Aus dem Firmwareablauf ergibt sich unter normalen stabilen Bedingungen eine **Qualifizierung von ungefähr 17–18 Sekunden**, bevor die entsprechende Betriebsfreigabe wegfällt.

Danach kann die separate Stopplogik des Verdichters noch zusätzliche Zeit benötigen, bis die tatsächliche Kompressorfrequenz auf **0 Hz** sinkt.

**Wichtig:** Die 17–18 Sekunden sind aus Firmware und Zeitbasis rekonstruiert, aber noch nicht durch einen gezielten Live-Test mit Stoppuhr bestätigt. Sie gelten nicht pauschal für alle Firmwareversionen oder jede Abschaltursache.

Auch das Wiedereinschalten besitzt eine interne Zustandsqualifizierung. Für die Einschaltseite sollte daraus jedoch keine ungeprüfte feste Wartezeit abgeleitet werden.

## Warum taktet die Wärmepumpe häufig?

Ein häufiger Grund ist, dass die Anlage gerade **weniger Wärme benötigt, als der Kompressor bei seiner Mindestfrequenz noch erzeugt**. Dann steigt die Wassertemperatur trotz heruntergeregeltem Verdichter weiter bis zur Ausschaltschwelle.

Weitere Punkte, die bei der Beurteilung eine Rolle spielen können:

- **R04/R05:** Sehr enge Schaltschwellen können häufigere Starts begünstigen; größere Abstände verändern aber auch die Wassertemperaturen.
- **Heizkurve und H25:** Der aktuelle Sollwert und die ausgewählte Regeltemperatur bestimmen, wann die Schwellen erreicht werden.
- **Durchfluss und Wärmeabnahme:** Ändert sich die Wärmeabnahme der Heizkreise, verändert sich auch der Temperaturverlauf.
- **Andere Betriebszustände:** Warmwasser-Vorrang, Abtauen, Schutzfunktionen oder eine externe Sperre können den Verdichter unabhängig von R04/R05 beeinflussen.

Eine kurze Temperaturspitze über „Soll + R05“ muss in V3.4 wegen der internen Qualifizierung **noch keinen Stopp auslösen**.

## Was sollte man bei häufigem Takten prüfen?

1. **Heizsollwert und Isttemperatur** über mehrere Takte beobachten, nicht nur einen einzelnen Messpunkt.
2. **H25, R04 und R05** prüfen: Welche Temperatur wird tatsächlich geregelt, und wie breit ist das Schaltband?
3. **Kompressorfrequenz** beobachten: Läuft er vor dem Abschalten bereits an seiner unteren Betriebsgrenze?
4. **Wasserdurchfluss und Heizkreisabnahme** prüfen. Auch Änderungen durch Raumthermostate können den Verlauf beeinflussen.
5. Ereignisse wie **Warmwasserbereitung, Abtauen oder Schutzbegrenzungen** zeitlich abgleichen.

R04/R05 nicht ohne nachvollziehbaren Grund vergrößern oder verkleinern. Eine größere Hysterese kann die Zahl der Starts reduzieren, zugleich aber größere Temperaturschwankungen verursachen. **Kompressor-Mindestfrequenz und Schutzparameter nicht auf Verdacht absenken.**

## Für welche Firmware gilt das?

Die Schaltschwellen und der zeitliche Filter sind anhand der **Mainboard-Firmware V3.4 / 82400644** untersucht. Die grundsätzliche Hysterese ist auch in verwandten Firmwareständen vorhanden; **die konkrete Verzögerungszeit ist jedoch nicht für alle Versionen live bestätigt**.

Mehr zur laufenden Leistungsregelung: [Auslauftemperatur und Kompressorfrequenz](auslauftemperatur_kompressorfrequenz.md). Weitere Hinweise zum Heizsollwert: [Heizungsregelung und Heizkurve](regelung_heizkurve.md).
