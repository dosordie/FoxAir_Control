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

Bei der GL9 mit der häufig verbauten APM-Pumpe muss dort der APM25 9-130 Pumpentyp ausgewählt werden.

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

Parameter **P01** bestimmt, wie die Hauptumwälzpumpe außerhalb aktiver Heiz-, Warmwasser- und Schutzanforderungen betrieben wird.

Die V3.4-Firmware unterscheidet drei Modi:

| P01 | Funktion |
| ---: | --- |
| **0 – Always On** | Pumpe wird im normalen Betrieb dauerhaft angefordert |
| **1 – Saving** | Energiesparbetrieb mit festem internen Takt |
| **2 – Interval** | frei einstellbarer Intervallbetrieb über P02/P03 |

### 0 – Always On

Die Hauptumwälzpumpe wird im normalen Betrieb dauerhaft betrieben.

Übergeordnete Betriebs-, Schutz- oder Sonderzustände können die Pumpenansteuerung trotzdem beeinflussen.

Dieser Modus ist zum Testen einfach nachvollziehbar, verursacht aber unnötigen Pumpenstrom, wenn gerade keine Wärme benötigt wird.

### 1 – Saving

Der **Saving-Modus** verwendet einen eigenen, fest in der Firmware hinterlegten Takt.

In den entsprechenden Ruhe-/Standbyphasen läuft die Pumpe ungefähr:

```text
ca. 2 Minuten EIN
ca. 30 Minuten AUS
danach beginnt der Zyklus erneut
```

**P02 und P03 werden für diesen Saving-Zyklus nicht verwendet.**

Wichtig: Das bedeutet nicht, dass die Pumpe bei aktivem Heiz-, Warmwasser-, Frostschutz- oder anderem Sonderbetrieb immer 30 Minuten ausgeschaltet bleibt. Solche Anforderungen können die Pumpe unabhängig vom Saving-Takt einschalten.

Der 2-/30-Minuten-Ablauf ist aus der Firmware bestätigt. Die genaue Herstellerbezeichnung des internen Freigabe-/Standbyzustands, in dem dieser Takt aktiv ist, ist noch nicht vollständig geklärt.

### 2 – Interval

Im **Interval-Modus** wird der Pumpentakt über **P02** und **P03** eingestellt:

- **P02** = Pause / Pumpe AUS
- **P03** = Laufzeit / Pumpe EIN

Der Ablauf ist:

```text
P02 Minuten AUS
P03 Minuten EIN
danach beginnt der Zyklus erneut
```

Beispiel:

```text
P02 = 30 min
P03 = 3 min

→ 30 min AUS
→  3 min EIN
→ danach wieder 30 min AUS
```

Der gesamte Zyklus dauert damit ungefähr **33 Minuten**.

Die frühere vereinfachte Beschreibung „alle 30 Minuten für 3 Minuten“ ist daher nicht ganz korrekt.

## P05 – Warmwasserpumpe

Für die Warmwasserpumpe gibt es mit **P05** eine vergleichbare Betriebsart:

- Always On
- Saving
- Interval

Dieser Parameter betrifft die Warmwasserpumpenlogik und ist nicht mit P01 der Hauptumwälzpumpe zu verwechseln.

## P10 – Pumpendrehzahl

**P10** gibt die gewünschte Drehzahl der Hauptumwälzpumpe in Prozent vor.

Bei älteren Firmwareständen bzw. manueller Regelung kann darüber direkt eine feste Pumpendrehzahl eingestellt werden.

> **Achtung bei fester P10-Vorgabe:** Wird die Pumpe manuell auf einen festen Prozentwert eingestellt, bleibt diese Vorgabe auch beim **Abtauen** bestehen. Die Wärmepumpe erhöht die Pumpendrehzahl in diesem Modus nicht automatisch. Der eingestellte Durchfluss muss deshalb auch für den Abtaubetrieb ausreichend sein.

Das wurde an der GL9 praktisch beobachtet. Bei zu niedrig gewählter fester Drehzahl kann während des Abtauens zu wenig Wasserenergie zur Verfügung stehen.

Wenn die Pumpe trotz Änderung von P10 immer mit voller Drehzahl läuft, sollte die Verdrahtung geprüft werden.

Bei vielen FoxAir GL9 liegt die PWM-Steuerleitung ab Werk auf GND und muss für eine echte Drehzahlregelung auf **P1-DO** umgeklemmt werden.

[Umwälzpumpe am Mainboard umklemmen](up_umklemmen.md)

## Automatische Pumpenregelung ab V3.3

Ab Mainboard-Firmware **V3.3** steht eine automatische Regelung der Pumpendrehzahl nach Temperaturdifferenz (ΔT / Spreizung) zur Verfügung.

Dafür wird **P10 = 0 %** verwendet. Die Firmware übernimmt dann die Drehzahlregelung selbst.

Der wichtige Unterschied zur festen Prozentvorgabe: **Im automatischen Modus wird die Pumpendrehzahl für den Abtaubetrieb selbstständig angehoben.** Eine zusätzliche externe Logik, die beim Abtauen manuell auf eine hohe Pumpendrehzahl schaltet, ist damit normalerweise nicht mehr nötig.

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

## Bekannte Auffälligkeit der originalen Shimge-Pumpe

In einigen GL9 ist eine **Shimge APM25-9-130 PWM1** verbaut.

An der hier untersuchten Anlage ist es mehrfach vorgekommen, dass sich die originale Shimge-Pumpe im **PWM-Betrieb aufgehängt** hat:

- an einem Tag zweimal, am folgenden Tag einmal
- der Wasserdurchfluss fiel dadurch aus
- nach **Pumpe Aus / Ein** lief sie wieder normal
- bei dauerhaftem 100-%-Betrieb trat das Verhalten nicht auf

Der damalige Erfahrungsbericht steht hier:

[FoxAir-Forum – Beitrag zur hängenden Shimge-PWM-Pumpe](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=20)

Ein ähnliches Verhalten wird auch bei anderen Wärmepumpen mit derselben **Shimge APM25-9-130 PWM1** beschrieben. Im HaustechnikDialog gibt es Berichte über sporadische **E8-/Wasserflussfehler** und Pumpen, die im PWM-Betrieb nicht mehr korrekt anlaufen:

[HaustechnikDialog – Remeha Tensio C in DIY, Shimge-Pumpenproblem](https://www.haustechnikdialog.de/Forum/t/261411/Remea-Tensio-C-in-DIY?page=7)

> **Einordnung:** Die ähnlichen Berichte zeigen, dass PWM-bezogene Probleme mit dieser Pumpenfamilie auch in anderen Geräten vorkommen. Damit ist aber nicht bewiesen, dass jeder Ausfall einer FoxAir-Shimge-Pumpe exakt dieselbe Ursache hat.

Wenn ein Durchflussfehler sporadisch auftritt und hydraulisch nichts auffällig ist, deshalb auch prüfen, ob die **Pumpe selbst noch läuft**. Ein reines Reinigen des Durchflusssensors hilft nicht, wenn tatsächlich die Umwälzpumpe stehen geblieben ist.

## Wenn ein Durchflussfehler auftritt

Prüfen:

- sind alle Absperrventile offen?
- ist ausreichend Anlagendruck vorhanden?
- Heizkreis / Wärmetauscher entlüftet?
- Schmutzfänger frei?
- läuft die Umwälzpumpe tatsächlich oder hat sich die Shimge-Pumpe möglicherweise aufgehängt?
- hilft testweise Pumpe bzw. Wärmepumpe Aus / Ein?
- H31 passend zur eingebauten Pumpe?
- PWM-Leitung korrekt angeschlossen?
- Durchflusswert plausibel?
- externe Pumpen bzw. Ventile richtig geschaltet?

Bei einem frisch befüllten System ist **Luft im Heizkreis** eine häufige Ursache für schwankenden oder zu geringen Durchfluss.
