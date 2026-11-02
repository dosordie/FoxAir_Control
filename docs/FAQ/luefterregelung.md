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

Die Lüfterkennlinien und der Soll-/Ist-Datenfluss wurden vor allem in der **Mainboard-Firmware V3.3 / 82400644** rekonstruiert. Der zentrale Lüfter-Regelblock ist in **V3.4 und V3.5** weiterhin vorhanden und im untersuchten Kern unverändert. Einzelheiten können je nach Lüftermotor, Leistungsmodul und Gerätevariante abweichen.
