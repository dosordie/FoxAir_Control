# Warmwasser mit der FoxAir

Die FoxAir kann neben dem Heizbetrieb auch einen Warmwasserspeicher laden.

Dafür benötigt die Wärmepumpe normalerweise:

- einen **Warmwasser-/Speicherfühler**
- eine hydraulische Umschaltung zwischen Heizung und Warmwasserspeicher, meist über ein **3-Wege-Ventil**
- die passende Warmwasser-Konfiguration in der Steuerung

## Warmwasserfunktion aktivieren

Parameter **H28** bestimmt, ob Warmwasser verwendet wird:

| H28 | Funktion |
| ---: | --- |
| **0** | keine Warmwasserfunktion |
| **1** | Heizen/Kühlen und Warmwasser |
| **2** | nur Warmwasser |

Für eine normale Anlage mit Raumheizung und Warmwasser wird daher üblicherweise die kombinierte Betriebsart verwendet.

## Warmwasserfühler

Die Wärmepumpe muss die tatsächliche Temperatur des Warmwasserspeichers kennen.

Dafür wird ein Temperaturfühler in der vorgesehenen Tauchhülse des Speichers montiert und am **TT-/DHW-Sensoreingang** der Wärmepumpe angeschlossen.

> Die genaue Klemmennummer unterscheidet sich bei verschiedenen FoxAir-/Mainboardvarianten. Deshalb die Beschriftung bzw. den Schaltplan der eigenen Anlage verwenden.

Ist kein realer Speicherfühler angeschlossen und befindet sich noch ein Widerstand am Eingang, kann die Wärmepumpe eine scheinbar plausible feste Temperatur anzeigen – im Forum wurden beispielsweise Werte um **35–36 °C** beobachtet. Das ist dann nicht die tatsächliche Speichertemperatur.

## Temperatur auch über Modbus vorgeben

Bei neueren bzw. entsprechend ausgestatteten Firmwareständen kann die Quelle der Warmwassertemperatur über **H37 / Register 1046** gewählt werden:

| H37 | Temperaturquelle |
| ---: | --- |
| **0** | angeschlossener Warmwasser-/Speicherfühler |
| **1** | Temperatur über Modbus / externe Zentralregelung |

Damit kann beispielsweise eine Gebäudeautomation die bereits vorhandene Speichertemperatur an die FoxAir übergeben.

## 3-Wege-Ventil

Für die automatische Umschaltung zwischen Heizkreis und Warmwasserspeicher wird normalerweise ein **3-Wege-Umschaltventil** verwendet.

Im Forum werden dafür unter anderem 230-V-Ventile eingesetzt. Entscheidend ist, dass Ventiltyp, Schaltlogik und Ausgang der eigenen FoxAir zueinander passen.

Beim Anschluss unbedingt den Schaltplan der konkreten Geräteversion beachten – insbesondere bevor 230 V auf einen Ausgang oder Ventilantrieb gelegt werden.

## Was passiert bei Warmwasseranforderung?

Vereinfacht läuft der Vorgang so ab:

1. Speichertemperatur fällt unter die eingestellte Einschaltgrenze.
2. Die Wärmepumpe schaltet auf Warmwasserbetrieb.
3. Das 3-Wege-Ventil leitet den Heizwasserstrom durch den Warmwasserspeicher.
4. Die WP erhöht die Wassertemperatur bis zum Warmwasser-Sollwert.
5. Nach Erreichen des Sollwertes wird wieder auf Heizbetrieb zurückgeschaltet.

Während einer längeren Warmwasserbereitung steht dadurch – abhängig von der Hydraulik – weniger oder zeitweise keine Heizleistung für die Räume zur Verfügung.

## Warmwasser-Solltemperatur

Die mögliche Warmwasser-Solltemperatur wird durch mehrere Parameter und die Betriebsbedingungen begrenzt.

Bekannte Register sind unter anderem:

- **R36 / Register 1176** = minimale Warmwasser-Solltemperatur
- **R37 / Register 1177** = maximale Warmwasser-Solltemperatur

Eine sehr hohe Warmwassertemperatur verschlechtert normalerweise die Effizienz und kann bei niedrigen Außentemperaturen nur schwer erreichbar sein.

Deshalb sollte die Temperatur nicht unnötig hoch eingestellt werden.

## Legionellenfunktion

In den Service-/Factory-Einstellungen der FoxAir existieren auch Einstellungen für eine zyklische Warmwassererhöhung bzw. Legionellenfunktion.

Im Forum wird diese Funktion genutzt, die genaue sinnvolle Temperatur und Häufigkeit hängt aber von Speicherart, Trinkwassersystem und Anlagenkonzept ab.

Die FoxAir GL9 besitzt in der üblichen Ausführung **keinen integrierten elektrischen Heizstab**, der unabhängig vom Kältekreis beliebig hohe Warmwassertemperaturen garantiert. Bei Anlagen, die regelmäßig sehr hohe Temperaturen benötigen, muss deshalb das Gesamtsystem entsprechend geplant sein.

## Wenn Warmwasser nicht funktioniert

Typische Prüfpunkte:

- Ist Warmwasser über **H28** aktiviert?
- Wird am Display eine plausible Speichertemperatur angezeigt?
- Ist der TT-/DHW-Fühler wirklich im Speicher montiert?
- Ist bei H37 die richtige Temperaturquelle gewählt?
- Schaltet das 3-Wege-Ventil tatsächlich auf den Speicher um?
- Ist die gewünschte Warmwassertemperatur erreichbar?
- Ist ein Fehler oder zu geringer Wasserdurchfluss aktiv?

Gerade ein fehlender Speicherfühler ist leicht zu übersehen, weil am Display trotzdem ein scheinbar sinnvoller Temperaturwert stehen kann.
