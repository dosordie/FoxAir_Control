# Wasserdurchfluss und Pumpenbetriebsarten

Ein ausreichender Wasserdurchfluss ist für den Betrieb der FoxAir wichtig.

Zu wenig Durchfluss kann unter anderem zu:

- schlechter Wärmeübertragung
- sehr großer Spreizung zwischen Vorlauf und Rücklauf
- Problemen beim Abtauen
- Durchflussfehlern / Abschaltung

führen.

## Durchfluss anzeigen

Der aktuelle Wasserdurchfluss kann am Display bzw. in FoxAir Control angezeigt werden, wenn die Pumpen-/Durchflusserkennung passend konfiguriert ist.

Wichtig ist dafür insbesondere **H31 – Pump Type**.

Bei der GL9 mit der häufig verbauten APM-Pumpe muss dort der passende Pumpentyp ausgewählt werden.

Erst mit korrekt eingestelltem Pumpentyp kann die Regelung den Durchfluss sinnvoll erfassen und anzeigen.

## H31 – Pumpentyp

H31 enthält mehrere Pumpentypen, unter anderem:

- Grundfos 25-75
- Grundfos 25-105
- Grundfos 25-125
- APM25 9-130
- APM25 12-130

Der eingestellte Typ muss zur tatsächlich eingebauten Pumpe passen.

Nicht einfach einen anderen Typ wählen, nur damit irgendein Durchflusswert erscheint.

## P01 – Betriebsmodus der Hauptumwälzpumpe

Parameter **P01** bestimmt, wann die Hauptumwälzpumpe läuft.

| P01 | Funktion |
| ---: | --- |
| **0 – Always On** | Pumpe läuft dauerhaft |
| **1 – Saving** | Pumpe läuft bedarfsabhängig |
| **2 – Interval** | Pumpe wird regelmäßig kurz eingeschaltet |

### Always On

Die Pumpe läuft ständig.

Das kann für Testzwecke hilfreich sein, verursacht aber auch unnötigen Stromverbrauch, wenn gerade keine Wärme benötigt wird.

### Saving

Im Saving-Modus läuft die Pumpe im Wesentlichen dann, wenn sie für den aktuellen Betrieb benötigt wird.

Für viele normal betriebene Anlagen ist das sinnvoller als ein dauerhafter Pumpenlauf.

### Interval

Im Intervallbetrieb schaltet die Wärmepumpe die Pumpe regelmäßig kurz ein, um die aktuelle Wassertemperatur zu erfassen.

Dafür gelten:

- **P02** = Abstand zwischen den Intervallen
- **P03** = Laufzeit der Pumpe pro Intervall

Beispiel:

```text
P02 = 30 min
P03 = 3 min
```

Dann läuft die Pumpe ungefähr alle 30 Minuten für 3 Minuten.

## P05 – Warmwasserpumpe

Für die Warmwasserpumpe gibt es mit **P05** eine vergleichbare Betriebsart:

- Always On
- Saving
- Interval

Dieser Parameter betrifft die Warmwasserpumpenlogik und ist nicht mit P01 der Hauptumwälzpumpe zu verwechseln.

## P10 – Pumpendrehzahl

**P10** gibt die gewünschte Drehzahl der Hauptumwälzpumpe in Prozent vor.

Bei älteren Firmwareständen bzw. manueller Regelung kann darüber direkt eine feste Pumpendrehzahl eingestellt werden.

Wenn die Pumpe trotz Änderung von P10 immer mit voller Drehzahl läuft, sollte die Verdrahtung geprüft werden.

Bei vielen FoxAir GL9 liegt die PWM-Steuerleitung ab Werk auf GND und muss für eine echte Drehzahlregelung auf **P1-DO** umgeklemmt werden.

[Umwälzpumpe am Mainboard umklemmen](up_umklemmen.md)

## Automatische Pumpenregelung ab V3.3

Ab Mainboard-Firmware **V3.3** steht eine automatische Regelung der Pumpendrehzahl zur Verfügung.

Dafür wird **P10 = 0 %** verwendet. Die Firmware übernimmt dann die Drehzahlregelung selbst.

Wichtige Parameter sind dabei unter anderem:

- **P11** – Ziel-Temperaturdifferenz / Spreizung
- **P12** – Anpassbereich der Pumpendrehzahl
- **A40** – Nenn-Wasserdurchfluss

Die automatische Regelung ist hier ausführlicher beschrieben:

[Automatische Regelung der Umwälzpumpe](automatische_up_regelung.md)

## A40 – Nenn-Wasserdurchfluss

**A40** beschreibt den Nenn-Wasserdurchfluss der Anlage.

Bei der automatischen Pumpenregelung wird dieser Wert unter anderem als Bezug für Mindest- und Freigabebedingungen verwendet.

A40 sollte deshalb nicht willkürlich verändert werden.

## Welche Spreizung ist richtig?

Eine größere Spreizung bedeutet:

```text
weniger Durchfluss
→ größere Temperaturdifferenz zwischen Vorlauf und Rücklauf
```

Eine kleinere Spreizung bedeutet entsprechend mehr Durchfluss.

Es gibt keinen einzigen optimalen Wert für jede Anlage. Er hängt unter anderem ab von:

- Heizflächen
- benötigter Leistung
- Hydraulik
- Geräuschen im Rohrnetz
- Pumpenleistung
- Außentemperatur und Vorlauftemperatur

Sehr niedriger Durchfluss nur mit dem Ziel einer besonders großen Spreizung ist nicht automatisch effizienter.

Entscheidend ist, dass die Wärmepumpe stabil arbeitet und der benötigte Wärmetransport erreicht wird.

## Durchfluss beim Abtauen

Beim Abtauen benötigt die Wärmepumpe ausreichend Wasserenergie.

Parameter **D22** betrifft den Wasserdurchfluss beim Abtauen.

Dieser Wert sollte nicht ohne konkreten Grund verändert werden. Ein zu geringer Durchfluss kann die Abtauung verschlechtern.

## Wenn ein Durchflussfehler auftritt

Prüfen:

- sind alle Absperrventile offen?
- ist ausreichend Anlagendruck vorhanden?
- Heizkreis / Wärmetauscher entlüftet?
- Schmutzfänger frei?
- läuft die Umwälzpumpe tatsächlich?
- H31 passend zur eingebauten Pumpe?
- PWM-Leitung korrekt angeschlossen?
- Durchflusswert plausibel?
- externe Pumpen bzw. Ventile richtig geschaltet?

Bei einem frisch befüllten System ist **Luft im Heizkreis** eine häufige Ursache für schwankenden oder zu geringen Durchfluss.
