# Außentemperaturkompensation / Heizkurve

Die in GL9 V3.4 und V3.5 bestätigte Regelung wählt mit **H36 (Register 1236)** einen von drei Modi für die
Außentemperaturkompensation der Heizung:

| H36 | Modus |
| ---: | --- |
| 0 | Aus |
| 1 | Lineare Kennlinie |
| 2 | 7-Punkt-Kennlinie |

## Lineare Kennlinie

Im Modus 1 bestimmen **Register 1234** (Steigung) und **Register 1235**
(Offset beziehungsweise Mittelpunkt) die bekannte lineare Heizkurve. Die
Anzeige in FoxAir Control verwendet dafür dieselbe Skalierung wie bisher.

## 7-Punkt-Kennlinie

Im Modus 2 werden Heiz-Solltemperaturen an sieben festen
Außentemperatur-Stützstellen vorgegeben:

| Außentemperatur | Register des Heiz-Sollwerts |
| ---: | ---: |
| -20 °C | 1250 |
| -10 °C | 1251 |
| -5 °C | 1252 |
| 0 °C | 1235 |
| +5 °C | 1253 |
| +10 °C | 1254 |
| +20 °C | 1255 |

Zwischen benachbarten Punkten interpoliert die Regelung linear. Für die
Kurvenberechnung wird die Außentemperatur auf **-20 bis +20 °C** begrenzt.
Register 1234 spielt in diesem Modus keine Rolle. Register 1235 hat daher eine
Doppelrolle: linearer Offset in Modus 1 und 0-°C-Sollwert in Modus 2.

## Gemeinsame Grenzen und aktuelle Werte

Nach der Kurvenberechnung begrenzt die Regelung das Ergebnis mit **R10
(Register 1164, minimale Heiz-Solltemperatur)** und **R11 (Register 1165,
maximale Heiz-Solltemperatur)**. Diese realen Gerätegrenzen werden auch in der
lokalen Vorschau verwendet.

Die aktuell verwendete Außentemperatur steht in Register 2048, die daraus
resultierende kompensierte Solltemperatur in Register 2014. Beide Werte sind im
Dialog reine Laufzeitanzeigen und werden dort nicht geschrieben.
