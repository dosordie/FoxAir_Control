# PWM-Rückmeldung und Durchflusskennlinien

Bei FoxAir-Wärmepumpen wird der Wasserdurchfluss (Register **2077 / T39**) je nach H31-Pumpentyp aus der **PWM-Rückmeldung** (Register **2116**) berechnet. Er stammt dabei nicht von einem separaten Durchflussmesser. Die Pumpenansteuerung (Register 2115) ist nicht mit der Rückmeldung gleichzusetzen.

Die folgenden Formeln sind aus der **Mainboard-Firmware V3.3** rekonstruiert. **P** ist PWM-Rückmeldung in %, **Q** ist berechneter Durchfluss in l/h.

| H31 | Pumpentyp | Q in l/h | Veränderung je PWM-Prozentpunkt | Max. berechneter Durchfluss |
| ---: | --- | --- | ---: | ---: |
| 1 | Grundfos 25-75 | P × 30 | 30 l/h | 2.100 l/h |
| 2 | Grundfos 25-105 | P × 57 | 57 l/h | 4.000 l/h |
| 3 | Grundfos 25-125 | P × 57 | 57 l/h | 4.000 l/h |
| 4 | Shimge APM25 9-130 | max(0, P − 5) × 64,6 | 64,6 l/h | 4.500 l/h |
| 5 | Shimge APM25 12-130 | P × 57 | 57 l/h | 4.000 l/h |

**Grenzen:** Bei H31 = 4 wird bis 5 % Rückmeldung 0 l/h berechnet. Ab 85 % PWM-Rückmeldung wird das Signal in der analysierten Firmware als ungültig behandelt und der Durchfluss auf 0 gesetzt. Die oberen Begrenzungen der berechneten Durchflusswerte stehen in der Tabelle. Das sind **Grenzen der Firmwareberechnung**, nicht zwingend die hydraulisch erreichbaren Maximalwerte einer eingebauten Pumpe.

**Genauigkeit:** Die Anzeige in Register 2077 hat eine Auflösung von 0,01 m³/h (10 l/h). Die Berechnung ersetzt keine unabhängige Messung; Signal- und Rundungsschwankungen sowie ein möglicher Korrekturwert in Register 1022 können eine Rolle spielen. Kleine Schwankungen beweisen weder einen Defekt noch eine konkrete Messungenauigkeit.
