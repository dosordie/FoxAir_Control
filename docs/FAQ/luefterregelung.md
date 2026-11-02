# Lüfterregelung – warum dreht der Ventilator schneller oder langsamer?

Der große Ventilator der FoxAir sorgt dafür, dass Luft durch den Verdampfer strömt. Seine Drehzahl bleibt nicht immer gleich: Die Wärmepumpe passt sie an die Temperaturen und den aktuellen Betriebszustand an.

**Eine wechselnde Lüfterdrehzahl ist deshalb zunächst normal** und bedeutet nicht automatisch, dass der Kompressor ebenfalls schneller oder langsamer laufen muss.

## Wovon hängt die Drehzahl ab?

Aus der untersuchten Mainboard-Firmware kennen wir mehrere Einflussgrößen:

- **Verdampfertemperatur (T03 / Register 2049):** Sie ist eine wesentliche Eingangsgröße für die normale Lüfterkennlinie.
- **Außentemperatur (T04 / Register 2048):** Je nach Temperaturbereich kann die Firmware die Lüftervorgabe zusätzlich begrenzen.
- **Kompressor- und Betriebszustand:** Der Lüfter kann auch außerhalb der normalen Temperaturkennlinie eine andere Vorgabe erhalten.
- **Schutzfunktionen und Abtauen:** Diese können die normale Lüfterregelung vorübergehend übersteuern.

Die Steuerung verwendet dafür Kennlinien mit Temperatur-Stützpunkten. Zwischen diesen Punkten berechnet sie die Lüftervorgabe. **Es gibt also keine allgemeine Regel „je kälter draußen, desto höher die Lüfterdrehzahl“.**

## Silent-Modus – wie wird die FoxAir leiser?

Der **Silent-Modus** soll die Geräusche der Wärmepumpe verringern, etwa nachts. Die untersuchte **Mainboard-Firmware V3.5** begrenzt dazu im normalen Lüfterregler die angeforderte Lüfterdrehzahl. Die Grenze hängt von Betriebsart und **lokaler Außentemperatur T04** ab.

### Wie stark wird die Lüfterdrehzahl begrenzt?

| Betriebsart | Außentemperatur T04 | Berechnete Silent-Obergrenze |
| --- | --- | --- |
| **Heizen** | unter −14 °C | **80 % von F26** |
| Heizen | −14 bis unter 22 °C | **60 % von F26** |
| Heizen | ab 22 °C | **F19** (Minimum Heizen) |
| **Kühlen** | unter 30 °C | **F18** (Minimum Kühlen) |
| Kühlen | 30 bis unter 46 °C | **60 % von F25** |
| Kühlen | ab 46 °C | **80 % von F25** |

**F26 (Register 1104)** ist die obere Lüftervorgabe für das Heizen, **F25 (1103)** für das Kühlen. **F19 (1083)** und **F18 (1081)** sind die jeweiligen Mindestvorgaben. Bei einem erkannten Fehler des lokalen Außentemperaturfühlers verwendet die Firmware in den untersuchten Zweigen ersatzweise **80 % von F25 bzw. F26**.

**Wichtig:** Das sind **Höchstwerte für bestimmte normale Regelzweige**, keine festen Lüfterdrehzahlen. Ist die normale Lüfteranforderung bereits niedriger, bleibt es bei diesem niedrigeren Wert. Andere Betriebs-/Schutzpfade können die Silent-Vorgabe übersteuern. **„Silent = immer 60 %“ ist daher falsch.**

### Wie schalte ich Silent ein?

| Parameter | Bedeutung |
| --- | --- |
| **H22 / 1030** | Grundfreigabe für die Silent-Funktion (0 = gesperrt, 1 = erlaubt) |
| **1016, Bit 1** | Manuelle Silent-Anforderung |
| **2108** | Tatsächlich gebildeter Silent-/Fan-Mute-Status |
| **1244–1246** | Silent-Timer: Start aktivieren, Stunde, Minute |
| **1247–1249** | Silent-Timer: Ende aktivieren, Stunde, Minute |

**H22 = 1 allein schaltet Silent nicht sofort ein.** Zusätzlich muss eine manuelle, zeitgesteuerte oder andere interne Silent-Anforderung vorliegen. Bei **H22 = 0** bleibt der Status 2108 dagegen aus.

Die **manuelle Silent-Anforderung über 1016 Bit 1** wird nach **ungefähr acht Stunden** von der V3.5 automatisch zurückgenommen. Die separat geschaltete Silent-Timer-Anforderung wird dadurch nicht gelöscht. Bei direktem Schreiben auf Register 1016 unbedingt die anderen Steuerbits unverändert lassen.

Der **Silent-Timer** reagiert auf die eingestellten Start- und Endminuten: Bei Erreichen der Startzeit wird seine Silent-Anforderung gesetzt, beim Erreichen der Endzeit gelöscht. Es handelt sich nicht um eine ständig neu berechnete Zeitspanne. Deshalb beide Zeiten sauber einstellen und nach einem Neustart prüfen, ob Silent tatsächlich aktiv ist. Sind beide Uhrzeiten identisch, wird die Schaltlogik dieses Durchlaufs übersprungen.

Die Silent-Zeiten lassen sich auch in **FoxAir Control** bearbeiten: [Funktionen und Bedienung](foxair_control_funktionen.md).

### Hat Silent auch Einfluss auf die Kompressorfrequenz?

**Ja.** In V3.5 wurde ein echter Datenweg von der Silent-Anforderung über **temperaturabhängige Frequenzstufen** bis zur Kompressor-Sollfrequenz und ihrem Modbus-Sendewert nachgewiesen. Dabei spielen Betriebsbedingungen und teilweise auch die adaptive Regelung eine Rolle.

Eine feste Obergrenze wie **„Silent = maximal 50 Hz“** ist **nicht belegt**. Der Kompressor wird weiterhin durch die normalen Mindest-/Höchstfrequenzen, Temperaturregelung und Schutzfunktionen beeinflusst. Mehr dazu: [Auslauftemperatur und Kompressorfrequenz](auslauftemperatur_kompressorfrequenz.md).

### Warum kann der Lüfter trotzdem schneller drehen?

Die Silent-Begrenzung gilt **nicht uneingeschränkt für jeden Zustand**. In der untersuchten V3.5 können nachgelagerte Schutz- und Betriebsroutinen andere Lüftervorgaben schreiben. Insbesondere für einen **Abtau-Übergangszustand im kombinierten Warmwasser-/Raumbetrieb** ist das nachgewiesen. Auch ein ausgeschalteter Lüfter ist nicht automatisch ein Silent-Fehler.

Zum Prüfen eignen sich **2108** (Silent-Status), **2076** (Lüfter-Sollwert), **2074/2075** (Lüfter-Rückmeldungen) und **2071/2072** (Kompressor-Soll-/Istfrequenz). Vorher/Nachher-Werte nur bei möglichst gleichem Betriebszustand und ähnlichen Temperaturen vergleichen.

## Warum bleibt der Lüfter manchmal stehen?

Ein stehender Lüfter kann zum Beispiel während des **Abtauens** normal sein. Die Abtausteuerung darf die normale Lüftervorgabe überschreiben und die Ventilatoren zeitweise auf null setzen.

Auch bestimmte Betriebs- oder Schutzphasen können die Lüftervorgabe verändern. Entscheidend ist deshalb, **ob die Wärmepumpe den Lüfter gerade anfordert** und ob anschließend eine Rückmeldung erfolgt.

Mehr dazu: [Abtauen und Frostschutz](abtauen_frostschutz.md).

## Wie kann ich Soll- und Ist-Drehzahl vergleichen?

Bei der untersuchten FoxAir-Regelung sind folgende Modbus-Werte hilfreich:

| Register | Bedeutung |
| ---: | --- |
| **2048 / T04** | Außentemperatur |
| **2049 / T03** | Verdampfertemperatur |
| **2076** | Lüfter-Sollwert, primärer Kanal |
| **2074** | Rückmeldung Lüfter 1 |
| **2075** | Rückmeldung Lüfter 2 |
| **2019 Bit 2** | Mindestens ein Lüfter meldet eine von null verschiedene Aktivität |

**2076 ist eine Anforderung; 2074 und 2075 sind Rückmeldungen.** Die Rückmeldungen kommen über das Leistungs-/Lüftermodul, nicht als unmittelbar vom Mainboard gemessene Drehzahl.

Die genaue physikalische Einheit beziehungsweise Skalierung der Rohwerte **2074–2076** ist noch nicht für alle Hardwarevarianten geklärt. Deshalb diese Werte nicht ungeprüft als **U/min oder Prozent** interpretieren.

**Beispiel:** Ist 2076 deutlich größer als null, aber beide Istwerte bleiben auf null und auch 2019 Bit 2 bleibt aus, fordert die Steuerung einen Lüfter an, erhält jedoch keine entsprechende Rückmeldung. Während eines sehr kurzen Übergangs kann das normal sein. Bleibt der Zustand bestehen, sind Lüfter, Leistungsmodul und Kommunikation mögliche Prüfpunkte.

Bei einer Anlage mit **nur einem Ventilator** ist eine dauerhafte Rückmeldung von 0 für Lüfter 2 hingegen nicht ungewöhnlich.

## Welche Einstellungen gibt es?

Einige bekannte Parameter der Lüfterkonfiguration sind:

| Parameter | Funktion |
| --- | --- |
| **F01 / 1059** | Lüftermotor-/Treiberart |
| **F10 / 1074** | Ein oder zwei Lüfter |
| **F18 / 1081** | Mindest-Lüftervorgabe für Kühlen |
| **F19 / 1083** | Mindest-Lüftervorgabe für Heizen |
| **F23 / 1089** | Nenn-Drehzahl-/Treiberparameter |
| **F25 / 1103** | obere Lüftervorgabe Kühlen |
| **F26 / 1104** | obere Lüftervorgabe Heizen |

**F01 und F10 sind Hardwareeinstellungen.** Sie dürfen nicht beliebig verändert werden, um das Gerät leiser zu machen. Auch die übrigen Grenzwerte beeinflussen Luftdurchsatz und Betriebsbedingungen.

## Was tun, wenn der Lüfter ungewöhnlich laut ist oder nicht läuft?

Zuerst prüfen, ob gerade **Abtauen, Warmwasserbetrieb oder ein Schutzstatus** vorliegt. Danach Außentemperatur, Verdampfertemperatur sowie Soll- und Istwerte über einige Minuten beobachten.

Bei ungewöhnlichen Geräuschen zusätzlich den Luftweg und mögliche Vereisung kontrollieren. **Nicht in den laufenden Lüfter greifen und keine Abdeckungen bei angeschlossenem Gerät öffnen.** Bleibt eine erkennbare Lüfteranforderung ohne Rückmeldung bestehen, sollte die Hardware fachkundig geprüft werden.

## Für welche Firmware gilt das?

Die Grundregelung und der Soll-/Ist-Datenfluss wurden in der **Mainboard-Firmware V3.3 / 82400644** rekonstruiert und für V3.4/V3.5 weiter untersucht. **Die konkreten Silent-Kennlinien, der Acht-Stunden-Timeout und der Kompressor-Stufenpfad sind anhand V3.5 belegt**; bei anderen Firmwareständen oder Hardwarevarianten kann das Verhalten abweichen.
