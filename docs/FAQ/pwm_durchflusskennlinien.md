# PWM-Rückmeldung und Wasserdurchfluss

Die FoxAir zeigt den aktuellen Wasserdurchfluss an. Bei vielen Geräten wird dieser Wert allerdings **nicht mit einem eigenen Durchflussmesser gemessen**. Stattdessen wird er aus der **Rückmeldung der Umwälzpumpe** berechnet.

Der angezeigte Wert ist deshalb eine **Schätzung**. Er kann vom tatsächlich gemessenen Durchfluss abweichen.

## Was muss richtig eingestellt sein?

Besonders wichtig ist **H31 – Pumpentyp**. Nur wenn der passende Pumpentyp ausgewählt ist, kann die FoxAir einen sinnvollen Durchfluss berechnen.

| H31 | Pumpentyp |
| ---: | --- |
| **1** | Grundfos 25-75 |
| **2** | Grundfos 25-105 |
| **3** | Grundfos 25-125 |
| **4** | Shimge APM25 9-130 |
| **5** | Shimge APM25 12-130 |

Den berechneten Wasserdurchfluss kann man über **Register 2077 (T39)** bzw. in FoxAir Control ablesen.

Die **PWM-Rückmeldung** der Pumpe ist nicht dasselbe wie die eingestellte Pumpendrehzahl. Die FoxAir nutzt die Rückmeldung zusammen mit der ausgewählten Pumpenkennlinie für ihre Berechnung.

## Warum kann die Durchflussanzeige abweichen?

Mögliche Ursachen sind:

- **H31** passt nicht zur eingebauten Pumpe.
- Die Pumpe liefert keine plausible Rückmeldung.
- Die tatsächlichen Eigenschaften der Pumpe weichen von der hinterlegten Kennlinie ab.
- In bestimmten Betriebszuständen zeigt die FoxAir vorübergehend **0** an.

Kleine Schwankungen sind normal. Bei ungewöhnlich kleinen oder großen Anzeigewerten sollte der Durchfluss möglichst mit einem unabhängigen Messgerät verglichen werden.

## Welche Bedeutung hat das für Durchflussfehler?

Der aus der Pumpenrückmeldung berechnete Durchfluss wird auch für die Überwachung verwendet. Deshalb ist ein korrekt eingestellter Pumpentyp **H31** wichtig. Die Meldung **E035** betrifft diesen berechneten Durchfluss; **E032** dagegen den mechanischen Schalter **S3**.

Was die einzelnen Fehler bedeuten und wann sie wieder verschwinden, steht in der [Fehlermeldungsübersicht](fehlermeldungen.md#die-durchflussfehler-im-detail).
