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

## Bedeutung für die Durchflussfehler (V3.5)

Die V3.5-Mainboard-Firmware verwendet den aus **2116**, **H31** und gegebenenfalls der Korrektur **MAIN:1022** berechneten *wirksamen Durchfluss* auch für ihre Software-Durchflussüberwachung. Dies gilt bei der **GL9 ohne Hydraulikmodul** mit gültiger H31-Konfiguration; ein externer Volumenstromsensor ist für diesen Pfad nicht zwingend erforderlich.

- **E030 (MAIN:2085 Bit 7)** prüft in einem Betriebszustandszweig gegen **D22 (MAIN:1127)**, wenn D22 nicht 0 ist.
- **E035 (MAIN:2085 Bit 13)** prüft in einem gesonderten, zeitqualifizierten Schutzpfad gegen **50 % von A40 (MAIN:1344)** und verwendet außerdem einen Vergleich bei **60 % von A40**.
- **E032 (MAIN:2085 Bit 8)** besitzt eine eigenständige Durchflussschalter-/Statusauswertung; die alleinige physische Anbindung an S3/S03 ist noch nicht lückenlos belegt.

Die **80 % / 120 % von A40** aus der *automatischen Pumpenregelung* sind **nicht** die E035-Fehlerschwellen. Auch **D22 = 0 deaktiviert E035 nicht**. MAIN:2077 zeigt normalerweise den intern geprüften Durchfluss, kann in einem speziellen Anzeigestatus aber 0 liefern, obwohl der interne Wert nicht 0 ist. Für Sicherheits- und Diagnoseentscheidungen einen unabhängigen hydraulischen Messwert vorziehen.

Ausführliche Bedingungen und Zeitverhalten: [Wasserdurchfluss und Pumpenbetriebsarten – E030/E032/E035](wasserdurchfluss_pumpe.md#durchflussfehler-e030-e032-und-e035-mainboard-firmware-v35).
