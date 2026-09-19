# Relaisausgänge RO01–RO15 am Mainboard

Auf dem Mainboard der FoxAir-/PHNIX-Wärmepumpe befinden sich mehrere Relaisausgänge mit den Bezeichnungen **RO01 bis RO15**.

Nicht jeder dieser Ausgänge wird bei jeder Anlage verwendet. Wenn einzelne Relais oder Anschlussklemmen nicht belegt sind, ist das daher nicht automatisch ein Fehler. Viele Ausgänge sind für optionale Funktionen wie zusätzliche Heizkreise, Mischventile, Zonenpumpen oder eine externe Störmeldung vorgesehen.

Die folgende Zuordnung wurde für das in der FoxAir GL9 verwendete Mainboard anhand der Firmware und der bekannten Boardbelegung nachvollzogen.

## Belegung der Relaisausgänge

| Relais | Funktion | Modbus-Rückmeldung |
|---|---|---|
| **RO01** | **Alarm / Sammelstörung** | **2019 Bit 10 / O011** |
| **RO02** | Mischventil Zone 2 – Richtung 1 | – |
| **RO03** | Mischventil Zone 2 – Richtung 2 | – |
| RO04 | Haupt-/Wasserumwälzpumpe | 2019 Bit 4 / O005 |
| RO05 | Warmwasserpumpe | 2019 Bit 5 / O006 |
| RO06 | 4-Wege-Ventil | 2019 Bit 6 / O007 |
| RO07 | Elektroheizung Stufe 1 | 2019 Bit 7 / O008 |
| RO08 | Elektroheizung Stufe 2 | 2019 Bit 8 / O009 |
| RO09 | 3-Wege-Ventil Warmwasser | 2019 Bit 9 / O010 |
| RO10 | Kurbelgehäuse-/Kompressorheizung | 2019 Bit 11 / O012 |
| RO11 | Kondensatwannenheizung | 2019 Bit 12 / O013 |
| RO12 | 3-Wege-Ventil Kühlung | 2018 Bit 10 |
| RO13 | Elektroheizer Warmwasserspeicher | 2018 Bit 0 / O025 |
| **RO14** | **Pumpe Zone 1** | **2018 Bit 8** |
| **RO15** | **Pumpe Zone 2** | **2018 Bit 9** |

## Warum sind manche Relais nicht angeschlossen?

Das Mainboard wird für unterschiedliche Geräte- und Anlagenvarianten verwendet. Deshalb sind mehr Ein- und Ausgänge vorhanden, als bei einer typischen FoxAir GL9 tatsächlich benötigt werden.

Beispiele:

- **RO01** wird nur benötigt, wenn eine externe Sammelstörmeldung angeschlossen werden soll.
- **RO02 und RO03** werden für einen vom Mainboard gesteuerten **3-Punkt-Mischer der Zone 2** verwendet. Die beiden Ausgänge schalten die zwei Laufrichtungen des Mischventils.
- **RO14 und RO15** sind für zusätzliche **Zonenpumpen** vorgesehen.
- Heizstäbe, Kühlventile oder weitere Pumpen können je nach Anlagenaufbau ebenfalls unbenutzt bleiben.

Sind diese Funktionen in der Anlage nicht vorhanden, können die zugehörigen Relaisausgänge ganz normal unbelegt sein.

## RO-Nummer und O-Nummer nicht verwechseln

Die Beschriftung **RO01, RO02 usw.** bezeichnet den **physischen Relaisausgang auf dem Mainboard**.

Bezeichnungen wie **O005, O011 oder O013** sind dagegen interne bzw. logische Ausgangsnummern der Steuerung.

Deshalb gilt zum Beispiel:

```text
RO01 = physischer Relaisausgang 1
O011 = logischer Alarmausgang

RO01 entspricht O011.
```

**RO11** ist dagegen die Kondensatwannenheizung und nicht der Alarmausgang.

## RO01 als Sammelstörung

RO01 ist der Ausgang für eine externe **Alarm- bzw. Sammelstörmeldung**.

Die Firmware schaltet diesen Ausgang, wenn eine der überwachten Stör- oder Schutzbedingungen aktiv ist. Dadurch kann beispielsweise eine externe Gebäudeleittechnik, Meldeleuchte oder andere Störmeldeeinrichtung angebunden werden.

## RO02 und RO03 als Mischventil-Ausgänge

RO02 und RO03 gehören zusammen. Sie bilden die beiden Richtungen eines **3-Punkt-Mischventils für Zone 2**.

Die Steuerung verriegelt die beiden Ausgänge gegeneinander, sodass nicht beide Richtungen gleichzeitig angesteuert werden.

Welche Klemme in einer konkreten Verdrahtung als **AUF** bzw. **ZU** verwendet wird, hängt von der Anschlussrichtung des Ventilantriebs ab.

## Hinweis zu anderen Geräten

Die Tabelle bezieht sich auf die untersuchte FoxAir-GL9-/PHNIX-Mainboard-Konfiguration. Bei anderen PHNIX-Geräten oder anderen Mainboardvarianten kann die tatsächliche Nutzung einzelner Relais abweichen.

> **Achtung:** Im Elektronikbereich der Wärmepumpe können netzspannungsführende Teile vorhanden sein. Arbeiten an Relaisklemmen und Verdrahtung nur spannungsfrei und durch entsprechend fachkundige Personen durchführen.
