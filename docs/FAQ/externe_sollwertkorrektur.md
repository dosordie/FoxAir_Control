# Solltemperaturen von außen korrigieren – Register 8802–8808

Mit einer Hausautomation, einem Raumregler oder einer PV-Steuerung kann man die Solltemperaturen der FoxAir **vorübergehend korrigieren**, ohne ständig die eigentlichen Temperatureinstellungen zu verändern.

Das ist beispielsweise interessant, wenn ein externer Regler die Heizwassertemperatur alle paar Minuten leicht anheben oder wieder absenken möchte. Die Wärmepumpe übernimmt weiterhin ihre normale Temperaturregelung; die externe Steuerung liefert nur eine zusätzliche Korrektur.

**Verfügbar:** In der untersuchten Mainboard-Firmware **V3.5 (Softwarecode 82400644)** ist diese Funktion nachgewiesen. Es geht um die **Mainboard-Firmware**, nicht um die Version des Displays.

## Welche Register werden verwendet?

| Register | Bedeutung | Praktische Nutzung |
| ---: | --- | --- |
| **8802** | Warmwasser-Sollwertkorrektur (wird addiert) | Warmwasserziel vorübergehend anpassen |
| **8803** | Heizsollwertkorrektur (wird addiert) | Heiztemperatur vorübergehend beeinflussen |
| **8804** | Kühlsollwertkorrektur (wird abgezogen) | Kühltemperatur vorübergehend beeinflussen |
| **8805** | Zonen-Korrektur A | Zonenwertkorrektur (wird addiert) | Zonentemperatur vorübergehend beeinflussent|
| **8806** | Zonen-Korrektur B |  Zonenwertkorrektur (wird addiert) | Zonentemperatur vorübergehend beeinflussent|


## Beispiel: Heiztemperatur mit einem Raumregler nachführen

Angenommen, die Wärmepumpe nutzt bereits ihre eigene Heizkurve. Eine externe Raumregelung stellt fest, dass es im Haus etwas zu kühl ist.

Statt den eigentlichen Heizsollwert immer wieder neu zu speichern, kann die Steuerung eine kleine Korrektur über **8803** vorgeben. Sobald weniger zusätzliche Wärme gebraucht wird, nimmt sie diese Korrektur wieder zurück.

So kann man beispielsweise alle **10 Minuten** eine kleine Anpassung vornehmen, ohne dauerhaft gespeicherte Grundeinstellungen ständig umzuschreiben. Die genauen Modbus-Rohwerte bitte erst nach Prüfung der Skalierung am eigenen Gerät verwenden.

## Warum ist das speicherschonender?

Die Register **8802–8808** liegen im Arbeitsspeicher (**RAM**). In der untersuchten V3.5-Firmware schreibt der direkte Engineering-Modbus-Pfad diese Werte in den RAM; dabei wurde **kein Flash-/EEPROM-Schreibaufruf** gefunden.

Das ist ein Vorteil gegenüber dem häufigen Ändern von Parametern, die dauerhaft gespeichert werden könnten. Es ist aber **keine Garantie**, dass andere Firmwarepfade niemals einen Speichervorgang auslösen.

Weil es sich um Laufzeitwerte handelt, sollte eine externe Steuerung nach einem Neustart die gewünschten Korrekturen erneut setzen und nicht darauf vertrauen, dass alte Werte erhalten bleiben.

## Wann funktioniert die Korrektur nicht?

Die Firmware unterscheidet zwischen der normalen Engineering-Korrektur, SG Ready und der Remote-/AI-Steuerung.

| Einstellung | Wirkung auf 8802–8808 |
| --- | --- |
| **1334 = 0** und **1540 = 0** | Normaler Engineering-Korrekturpfad wird verwendet |
| **1334 = 1, 2, 3, 5, 6 oder 7** | SG-Ready-/PV-Korrekturen haben Vorrang; 8802–8808 werden nicht berücksichtigt |
| **1334 = 4** | Eigener AI-Saving-/Remote-Korrekturpfad; 8802–8808 werden nicht berücksichtigt |
| **1334 = 0**, aber **1540 ≠ 0** | Remote-/WarmLink-Korrekturen ersetzen 8802–8806; 8807/8808 werden intern weiterhin addiert, ihre Wirkung ist aber ungeklärt |

**Wichtig:** Wenn **1334 = 7** für die virtuelle SG-/PV-Steuerung eingestellt ist, funktioniert **8803 auch bei 8801 = 2 (Neutral)** nicht. Entscheidend ist die eingestellte SG-Steuerungsart, nicht nur der momentan angeforderte SG-Zustand.

Wer die normale externe Heizkorrektur nutzen möchte, benötigt daher nach dem untersuchten V3.5-Regelpfad **1334 = 0 und 1540 = 0**. Damit wird die SG-Steuerung über diese Betriebsart allerdings deaktiviert. Eine gleichzeitige Nutzung der virtuellen SG-Steuerung über **8801** und der Heizkorrektur über **8803** ist in diesem Pfad nicht möglich.

## Welcher Anschluss und welche Firmware?

Für die untersuchten Register den **direkten Benutzer-Modbus am Mainboard** verwenden (in FoxAir Control: **„Modbus Standard“**). Den Display-Bus oder den Warmlink-/LTE-Bus nicht einfach als gleichwertig voraussetzen.

- **V3.5 / 82400644:**Korrekturpfad per Firmwareanalyse bestätigt, Livevalidierung von 8802 erfolgreich.
- **V3.4 / 82400644:** Im untersuchten Korrekturselektor fehlt dieser normale Zweig. Die hier beschriebene Nutzung ist daher **nicht für V3.4 belegt**.
- **V3.3 und älter:** Nicht als funktionsfähig nachgewiesen.


## Weitere Informationen

- [Modbus-Anschluss am Klemmfeld](modbus.md)
- [Heizungsregelung, H25 und Heizkurve](regelung_heizkurve.md)
- [SG Ready und PV-Überschusssteuerung](sg_ready.md)
