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

Die aus der Firmware rekonstruierten Umrechnungen sind im Artikel [PWM-Rückmeldung und Durchflusskennlinien](pwm_durchflusskennlinien.md) beschrieben.

## P01 – Betriebsmodus der Hauptumwälzpumpe

Parameter **P01** bestimmt vor allem das Verhalten der Hauptumwälzpumpe in Wartephasen, wenn die **Wärmepumpe eingeschaltet** ist, der Verdichter aber z. B. wegen erreichter Solltemperatur gerade nicht läuft.

Ist die Wärmepumpe selbst ausgeschaltet, bleibt auch die Hauptumwälzpumpe normalerweise aus. Frostschutz-, Schutz- und andere Sonderanforderungen können die Pumpe trotzdem einschalten.

Die V3.4-Firmware unterscheidet drei Modi:

| P01 | Funktion |
| ---: | --- |
| **0 – Always On** | Pumpe läuft bei eingeschalteter Wärmepumpe auch in solchen Wartephasen dauerhaft weiter |
| **1 – Saving** | Wartephasen werden mit einem festen internen Ein-/Aus-Takt überbrückt |
| **2 – Interval** | Wartephasen werden mit dem über P02/P03 einstellbaren Ein-/Aus-Takt überbrückt |

### 0 – Always On

Bei eingeschalteter Wärmepumpe wird die Hauptumwälzpumpe auch dann dauerhaft betrieben, wenn der Verdichter gerade nicht heizt bzw. kühlt.

Übergeordnete Betriebs-, Schutz- oder Sonderzustände können die Pumpenansteuerung trotzdem beeinflussen.

Dieser Modus ist zum Testen einfach nachvollziehbar, verursacht aber unnötigen Pumpenstrom, wenn gerade keine Wärme benötigt wird.

### 1 – Saving

Der **Saving-Modus** verwendet für solche Wartephasen einen eigenen, fest in der Firmware hinterlegten Takt.

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

Im **Interval-Modus** wird der Pumpentakt für diese Wartephasen über **P02** und **P03** eingestellt:

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

## H40 – Funktion des externen Pumpenausgangs RO05

Über **H40 (Register 1345)** lässt sich festlegen, wofür der Relaisausgang **RO05 / K5** (*Hot Water Pump*) verwendet wird:

| H40 | Funktion |
|---:|---|
| **0** | Warmwasserpumpe |
| **1** | Warmwasser-Zirkulationspumpe |
| **2** | Ausschaltsignal beim Abtauen |

Mit **H40 = 2** kann der Ausgang beispielsweise genutzt werden, um eine externe Pumpe beim Abtauen abzuschalten. Die tatsächliche Schaltwirkung hängt von der Verdrahtung ab.

**Nicht verwechseln:** RO05 / K5 ist ein zusätzlicher Pumpenausgang. Die **Hauptumwälzpumpe** hängt an **RO04 / K4**; ihre Regelung über P01, P10 und die Pumpenautomatik wird durch H40 nicht umgestellt. Beim Abtauen muss der notwendige Heizwasserdurchfluss erhalten bleiben.

Die komplette Belegung steht unter [Relaisausgänge RO01–RO15 am Mainboard](relais_ausgaenge.md).

## P10 – Pumpendrehzahl

**P10** gibt die gewünschte Drehzahl der Hauptumwälzpumpe in Prozent vor.

Bei älteren Firmwareständen bzw. manueller Regelung kann darüber direkt eine feste Pumpendrehzahl eingestellt werden.

> **Wichtig bei festem P10:** Eine separate, einstellbare Drehzahlerhöhung fürs **Abtauen** ist nicht nachgewiesen. Die Firmware kann die feste Vorgabe zwar in Sonderzuständen übersteuern, darauf sollte man sich aber nicht verlassen. Der Durchfluss muss auch beim Abtauen ausreichen.

Mehr dazu unter [Durchfluss beim Abtauen](#durchfluss-beim-abtauen).

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

**A40** beschreibt den Nenn-Wasserdurchfluss der Anlage und ist für die automatische Pumpenregelung wichtig.

**A40 darf dafür nicht auf 0 stehen!** Bei **A40 = 0** gibt die Firmware die automatische Drehzahlabsenkung nicht frei und fordert stattdessen **100 % Pumpenleistung** an – auch wenn **P10 = 0** eingestellt ist.

Bei gültigem A40 verwendet die Automatik den Wert für zwei Bedingungen:

- **Freigabe:** Der Durchfluss muss nach dem Kompressorstart ungefähr **10 Minuten lang mindestens 120 % von A40** erreichen, bevor die Pumpe automatisch herunterregeln darf.
- **Mindestgrenze:** Bei **D22 = 0** darf der Durchfluss durch das automatische Herunterregeln nicht unter ungefähr **80 % von A40** abgesenkt werden. Bei **D22 größer 0** gilt stattdessen der eingestellte D22-Wert.

**Beispiel:** A40 = 1,0 m³/h → Freigabeschwelle etwa **1,2 m³/h**, Mindestgrenze bei D22 = 0 etwa **0,8 m³/h**.

A40 deshalb **nicht willkürlich erhöhen oder verringern**, sondern passend zur Anlage einstellen.

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

Beim Abtauen entzieht die Wärmepumpe dem Heizwasser Wärme. Dafür braucht sie **ausreichend Durchfluss** und genügend Wärme im Heizkreis.

### D22 – Mindestdurchfluss

**D22 (Register 1127)** heißt beim Hersteller „Water Flow of Defrosting“. In der untersuchten Firmware dient er auch als **Untergrenze für die automatische Pumpenregelung**:

| D22 | Mindestdurchfluss der Automatik |
| --- | --- |
| **0** | **80 % von A40** (Nenn-Wasserdurchfluss) |
| **größer 0** | Der eingestellte D22-Wert in **m³/h** |

**Beispiel:** Bei A40 = 1,0 m³/h und D22 = 0 liegt die Untergrenze bei **0,8 m³/h**. Stellt man D22 auf 1,0 m³/h, gilt stattdessen dieser Wert.

Wird die Untergrenze erreicht, darf die Automatik die Pumpendrehzahl **nicht weiter senken**. Erhöhen darf sie sie weiterhin. **D22 stellt also keinen festen Durchfluss ein** und kann fehlende Pumpenleistung nicht ersetzen.

### Pumpendrehzahl während des Abtauens

- **P10 = 0 (Automatik, ab Mainboard-V3.3):** Beim Abtauen fordert die Firmware **100 % Pumpenleistung** an. Anschließend muss die Automatik ihre Freigabebedingungen erneut erfüllen. Daher kann die Pumpe noch etwa **10 Minuten oder länger** mit hoher Drehzahl laufen.
- **P10 größer 0 (feste Drehzahl):** Eine separat einstellbare Abtau-Drehzahl ist **nicht nachgewiesen**. Schutz- und Sonderfunktionen können P10 zwar übersteuern, eine gezielte Erhöhung auf 100 % lässt sich damit aber nicht zuverlässig einstellen.

Wer automatisch mehr Durchfluss beim Abtauen möchte, sollte prüfen, ob **P10 = 0** mit richtig eingestelltem **H31** und passenden **P11/P12** für seine Anlage geeignet ist.

### Was lässt sich kontrollieren?

In FoxAir Control helfen diese Werte:

| Wert | Bedeutung |
| --- | --- |
| **2012 = 2** | Abtaubetrieb |
| **2115** | angeforderte Pumpenleistung in % |
| **2116** | PWM-Rückmeldung der Pumpe |
| **2077** | berechneter Wasserdurchfluss |
| **T01 / T02** | Einlass- und Auslasstemperatur |

Der angezeigte Durchfluss wird bei vielen Pumpentypen aus der PWM-Rückmeldung **berechnet** und nicht unabhängig gemessen.

**Empfehlung:** D22 nicht vorschnell erhöhen. Erst Durchfluss und Temperaturverlauf beim Abtauen beobachten.

Mehr dazu: [Automatische Regelung der Umwälzpumpe](automatische_up_regelung.md).

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
