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

Der berechnete Durchfluss wird auch für die Fehlerüberwachung verwendet:

- **E035:** Ist der berechnete Durchfluss bei aktiver Überwachung ungefähr **6 Sekunden lang unter 50 % von A40**, kann der Fehler auftreten. Je nach Betriebszustand kann es länger dauern.
- **E030:** Beim Abtauen gibt es zusätzlich eine Durchflussüberwachung mit dem Einstellwert **D22**.
- **E032:** Dieser Fehler gehört zum **mechanischen Durchflussschalter am Eingang S3** und ist von der Berechnung über die Pumpe zu unterscheiden.

**Wichtig:** Ein plausibler angezeigter Durchfluss garantiert nicht, dass tatsächlich genügend Wasser fließt. Und **D22 = 0 deaktiviert E035 nicht**.

Weitere Informationen und praktische Prüfschritte: [Wasserdurchfluss und Pumpenbetriebsarten](wasserdurchfluss_pumpe.md#durchflussfehler-e030-e032-und-e035).
