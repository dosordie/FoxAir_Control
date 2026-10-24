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

Die FoxAir verwendet für die normale Leistungsregelung einen **PID-Regler**. Er schaut nicht nur darauf, *wie groß* die Temperaturabweichung ist, sondern auch darauf, *wie lange* sie schon besteht und *wie schnell* sie sich verändert.

### Was bedeuten P, I und D?

Ein PID-Regler besteht aus drei Anteilen, die zusammen bestimmen, welche Kompressorfrequenz angefordert wird:

| Anteil | Einfach erklärt | Wirkung im Alltag |
| --- | --- | --- |
| **P – proportional** | Reagiert auf die **aktuelle Temperaturabweichung**. Je größer der Abstand zwischen Soll- und Isttemperatur, desto größer kann die Korrektur sein. | Liegt der Vorlauf weit unter dem Sollwert, fordert die Regelung eher mehr Leistung an. |
| **I – integral** | Berücksichtigt, **wie lange** eine Abweichung schon besteht. Kleine, länger anhaltende Abweichungen sammeln sich sozusagen an. | Wenn die Wärmepumpe über längere Zeit nicht warm genug wird, kann die angeforderte Frequenz weiter steigen, obwohl der Temperaturabstand gleich bleibt. |
| **D – differential** | Betrachtet, **wie schnell sich die Temperaturabweichung verändert**. | Wenn sich der Vorlauf rasch dem Soll nähert, kann dieser Anteil einer zu starken Reaktion entgegenwirken. |

**Beispiel:** Die Wärmepumpe soll 35 °C erreichen und liefert erst 30 °C. Der P-Anteil reagiert auf die 5 °C Unterschied. Bleibt der Vorlauf trotzdem länger zu kühl, wirkt zusätzlich der I-Anteil. Steigt die Temperatur anschließend schnell, berücksichtigt der D-Anteil diese Veränderung.

Deshalb folgt die Frequenz keiner einfachen Regel wie „5 °C zu kalt = genau 10 Hz mehr“. Der Regler bewertet die gesamte Entwicklung.

### Was macht die Firmware V3.5 konkret?

Aus der Firmwareanalyse kennen wir auch einige Besonderheiten des Reglers:

- Der **Regler berechnet ungefähr alle 0,5 Sekunden** einen neuen Frequenz-Sollwert. Der Kompressor selbst muss deshalb nicht alle 0,5 Sekunden seine Drehzahl ändern.
- **Beim Annähern an den Sollwert** gibt es einen kleinen Bereich, in dem die Regelung die Frequenz zunächst halten kann, statt sie bei jeder kleinen Temperaturänderung anzupassen.
- **Bei einer deutlichen Unterschreitung des Sollwerts** kann die angeforderte Frequenz steigen. Wie stark, hängt unter anderem vom bisherigen Verlauf ab.
- **Wenn die Temperatur über den Sollwert steigt**, wirkt die Regelung auf ein Absenken der Frequenz hin. Die Firmware besitzt hierfür zusätzlich einen beschleunigten Abbau des gespeicherten I-Anteils.
- **Nach bestimmten Zustandswechseln** wird der gespeicherte I-Anteil an die aktuelle Frequenzreferenz angepasst. Er startet also nicht grundsätzlich wieder bei null.
- **Die berechnete Frequenz ist nur eine Anforderung.** Mindest- und Höchstfrequenz sowie Schutzfunktionen begrenzen weiterhin, was der Verdichter tatsächlich ausführen darf.

Genau deshalb kann die Wärmepumpe trotz erreichter Solltemperatur eine Zeit lang mit ähnlicher Frequenz weiterlaufen – oder bei Überschreitung rascher herunterregeln. Erst der zeitliche Verlauf zeigt, ob das Verhalten zur Regelung passt.

### Welche Einstellungen beeinflussen den PID-Regler?

Die zugehörigen Serviceparameter sind:

| Parameter | Funktion |
| --- | --- |
| **C13** | Stärke des **P-Anteils** |
| **C14** | Skalierung des **I-Anteils** – in der Firmware wird durch C14 geteilt |
| **C15** | Stärke des **D-Anteils** |

Für technisch Interessierte ist die vereinfachte Berechnung:

```text
P = C13 × Temperaturabweichung
I = bisheriger I-Wert + Temperaturabweichung / C14
D = C15 × Änderung der Temperaturabweichung
```

Die Beiträge werden zur Frequenzanforderung verarbeitet. Der tatsächliche Firmwareablauf enthält zusätzliche Regeln für das Halten, Absenken und Begrenzen der Frequenz.

**Wichtig:** C13 bis C15 sind keine Einstellungen, die man zum schnellen „Optimieren“ auf Verdacht verändern sollte. Gerade **C14 darf nicht 0 sein**, weil es intern als Divisor verwendet wird. Auch die Werte für **C02 (Mindestfrequenz)** und **C03 (Höchstfrequenz)** bleiben unabhängig davon relevant.

Eine feste Formel wie **„Vorlauftemperatur in °C + 2 = Kompressorfrequenz in Hz“** gibt es in der untersuchten V3.5-Regelung nicht. Dass beide Anzeigen zufällig ähnliche Zahlen zeigen, bedeutet keinen solchen Zusammenhang.

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
