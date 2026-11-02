# Lüfterregelung – warum dreht der Ventilator schneller oder langsamer?

Die FoxAir verändert die Lüfterdrehzahl abhängig von Verdampfertemperatur, Außentemperatur und Betriebszustand. Deshalb ist eine wechselnde Drehzahl zunächst normal.

## Wovon hängt die Drehzahl ab?

Die Hauptkennlinie richtet sich nach der Verdampfertemperatur (T03 / Register 2049). Die Außentemperatur (T04 / 2048) kann die Drehzahl zusätzlich begrenzen. Auch Kompressorzustand, Schutzfunktionen und Abtauung beeinflussen die Vorgabe.

## Silent-Modus – wie wird die FoxAir leiser?

Der Silent-Modus begrenzt in der Mainboard-Firmware **V3.5 (82400644)** die Lüftervorgabe abhängig von Betriebsart und lokaler Außentemperatur.

| Betriebsart | Außentemperatur T04 | Silent-Obergrenze |
| --- | --- | --- |
| Heizen | unter −14 °C | 80 % von F26 |
| Heizen | −14 bis unter 22 °C | 60 % von F26 |
| Heizen | ab 22 °C | F19 (Minimum Heizen) |
| Kühlen | unter 30 °C | F18 (Minimum Kühlen) |
| Kühlen | 30 bis unter 46 °C | 60 % von F25 |
| Kühlen | ab 46 °C | 80 % von F25 |

F26 (1104) und F25 (1103) sind die Maximalvorgaben, F19 (1083) und F18 (1081) die jeweiligen Mindestvorgaben. Bei einem erkannten Fehler des lokalen Außentemperaturfühlers verwendet der untersuchte Code alternativ 80 % des jeweiligen Maximums.

**Wichtig:** Das sind Obergrenzen für bestimmte normale Regelzweige, keine festen Lüfterdrehzahlen. Die tatsächliche Lüftervorgabe darf darunter liegen. Schutz- und Abtauzustände können sie übersteuern.

### Einschalten, Status und Silent-Timer

| Register | Bedeutung |
| --- | --- |
| **H22 / 1030** | Grundfreigabe der Silent-Funktion |
| **1016 Bit 1** | Manuelle Silent-Anforderung |
| **2108** | Gebildeter Silent-/Fan-Mute-Status |
| **1244–1246** | Zeitplan: Start aktivieren, Stunde, Minute |
| **1247–1249** | Zeitplan: Ende aktivieren, Stunde, Minute |

H22 = 1 allein aktiviert Silent noch nicht: Eine manuelle, zeitgesteuerte oder interne Anforderung muss hinzukommen. H22 = 0 sperrt den Silent-Status 2108.

Die manuelle Anforderung über **1016 Bit 1** läuft in V3.5 nach **ungefähr acht Stunden** automatisch ab. Der separate Silent-Timer bleibt davon unabhängig. Beim direkten Schreiben von 1016 müssen die übrigen Bits unverändert bleiben.

Der Zeitplan reagiert auf die jeweils eingestellte **Start- und Endminute**, statt die aktuelle Uhrzeit fortlaufend mit einem Intervall zu vergleichen. Bei gleichen Start- und Endzeiten wird die Umschaltlogik übersprungen. Nach einem Neustart sollte kontrolliert werden, ob die gewünschte Silent-Anforderung aktiv ist.

Die Timer lassen sich auch über [FoxAir Control](foxair_control_funktionen.md) einstellen.

### Begrenzt Silent auch den Kompressor?

**Ja.** Die V3.5 nutzt Silent-Anforderungen zusätzlich in einer temperaturabhängigen Stufenregelung, deren Ergebnis bis zur Kompressor-Sollfrequenz und zum Inverter-Sendewert verfolgt wurde.

Eine feste Grenze wie **„Silent = maximal 50 Hz“** wurde nicht nachgewiesen. Die Frequenz bleibt auch vom Wärmebedarf, Betriebszustand und den normalen Schutz- und Frequenzgrenzen abhängig. Siehe [Auslauftemperatur und Kompressorfrequenz](auslauftemperatur_kompressorfrequenz.md).

## Warum bleibt der Lüfter manchmal stehen?

Bei einer Abtauung oder in besonderen Schutz-/Übergangszuständen kann die Firmware den normalen Lüfterregler übersteuern und einen oder beide Lüfter anhalten. Das ist nicht automatisch ein Defekt. Weitere Informationen: [Abtauen und Frostschutz](abtauen_frostschutz.md).

## Wie kann ich Soll- und Istwerte vergleichen?

| Register | Bedeutung |
| --- | --- |
| **2048 / T04** | Außentemperatur |
| **2049 / T03** | Verdampfertemperatur |
| **2076** | Lüfter-Sollwert (Kanal 1) |
| **2074 / 2075** | Lüfter-Rückmeldungen |
| **2019 Bit 2** | Mindestens ein Lüfter meldet Aktivität |
| **2108** | Silent-Status |

2076 ist eine Anforderung, 2074/2075 sind Rückmeldungen des Leistungs-/Lüftermoduls. Die Rohwerte nicht ohne Hardwareprüfung als U/min oder Prozent verstehen.

Zum Prüfen der Silent-Wirkung Werte bei möglichst ähnlicher Außentemperatur, Verdampfertemperatur und Betriebsart vor und nach dem Umschalten vergleichen. Für den Kompressor zusätzlich **2071 (Sollfrequenz)** und **2072 (Istfrequenz)** beobachten.

## Welche Lüfterparameter sind bekannt?

| Parameter | Funktion |
| --- | --- |
| **F01 / 1059** | Motor-/Treiberart |
| **F10 / 1074** | Ein oder zwei Lüfter |
| **F18 / 1081** | Minimum Kühlen |
| **F19 / 1083** | Minimum Heizen |
| **F23 / 1089** | Nenn-Drehzahl-/Treiberparameter |
| **F25 / 1103** | Maximum Kühlen |
| **F26 / 1104** | Maximum Heizen |

**F01 und F10 sind Hardwareeinstellungen** und dürfen nicht zum Experimentieren verändert werden. Auch die Lüftergrenzen beeinflussen den Wärmeübergang und die Betriebsbedingungen.

## Was tun bei ungewöhnlichen Geräuschen?

Zuerst Abtauung, Betriebszustand, Vereisung sowie Soll- und Istwerte prüfen. Nicht in den laufenden Lüfter greifen. Bei ausbleibender Rückmeldung trotz dauerhafter Lüfteranforderung Lüfter, Leistungsmodul und Kommunikation fachkundig prüfen.

## Für welche Firmware gilt das?

Der allgemeine Lüfter-Soll-/Ist-Pfad wurde in V3.3 untersucht und in V3.4/V3.5 bestätigt. **Die konkreten Silent-Kennlinien, der Acht-Stunden-Timeout und der Kompressor-Stufenpfad gelten für die untersuchte Mainboard-Firmware V3.5.**
