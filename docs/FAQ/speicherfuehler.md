# Externe Speicherfühler: Warmwasser (TT) und Puffer (BT)

Die FoxAir kann die Temperaturen von **Warmwasserspeicher** und **Heizungs-Pufferspeicher** mit separaten Fühlern erfassen.

## Funktion und Aktivierung

| Fühler | Funktion | Einstellung |
| --- | --- | --- |
| **TT (DHW / Warmwasser)** | Misst die Speichertemperatur und steuert damit die Warmwasserbereitung. | **H28 = 1** (Heizen/Kühlen + Warmwasser) oder **H28 = 2** (nur Warmwasser). Falls **H37** vorhanden: **H37 = 0** für den angeschlossenen Fühler statt Modbus. |
| **BT (Buffer Tank / Puffer)** | Misst die Puffertemperatur. Die Wärmepumpe regelt den Heizbetrieb dann nach dem Puffer statt nach Vor- oder Rücklauf. | **H25 = 2** (*Buffer Tank Temp.*). |

Die Parameter findest du am Display unter **Einstellungen → Factory Settings (H-Parameter)**; je nach Firmware auch über **WarmLink** oder **FoxAir Control**.

## BT/RT als Raumfühler (H25 = 1)

Bei **H25 = 1 (Room Temp.)** verwendet die Hauptregelung eine **Raumtemperatur**, um mit **R70 (Raumsolltemperatur)** und **R71/R72 (Heiz-Hysterese)** eine Heizanforderung ein- oder auszuschalten. **R73/R74** übernehmen diese Aufgabe beim Kühlen.

Beispiel: **R70 = 21 °C, R71 = R72 = 0,5 K** → Heizbedarf bei **≤ 20,5 °C** anfordern, ab **≥ 21,5 °C** zurücknehmen. Die tatsächliche Verdichterreaktion hängt zusätzlich von Wasser-, Zeit-, Betriebs- und Schutzbedingungen ab. **Die Verdichterleistung wird weiterhin nach T02 (Vorlauf) geregelt** – eine proportionale Vorlaufsollwert-Anhebung durch die Raumabweichung ist in der V3.5-Firmwareanalyse nicht belegt.

**Anschluss:** In Forumspraxis wird derselbe **BT/RT-Eingang** wahlweise für den Raumfühler (**H25 = 1**) oder den Pufferfühler (**H25 = 2**) beschrieben. Die **V3.5-Firmwareanalyse bestätigt die Raumregelungsfunktion**, kann die **physische Zuordnung BT/T09 für jede Mainboardvariante aber noch nicht abschließend bestätigen**. Die Raumfühler der separaten **Zonenregelung (Z01, AI/DI07 und AI17)** sind davon zu unterscheiden.

## Fühlertyp und Anschluss

- Für **beide Eingänge** wird ein **NTC-Temperaturfühler mit 10 kΩ bei 25 °C (NTC 10k)** verwendet.
- **Ein 10-kΩ-Fühler ist im Lieferumfang enthalten**, ursprünglich für TT/Warmwasser. Werden Warmwasser **und** Puffer über Fühler geregelt, ist ein zweiter erforderlich.
- Den Fühler in einer passenden **Tauchhülse des jeweiligen Speichers** montieren und am zugehörigen **TT-/DHW-** beziehungsweise **BT-/RT-BT-Eingang** anschließen.
- Einen eventuell ab Werk angeschlossenen **Ersatzwiderstand** vor dem Anschluss des Fühlers entfernen. Er kann sonst eine scheinbar plausible, aber feste Temperatur (oft etwa 35–36 °C) vortäuschen.

> **Wichtig:** Klemmennummern und -bezeichnungen können sich je nach Herstellungsmonat und Mainboardversion unterscheiden. Maßgeblich sind die Beschriftung und der Schaltplan **der eigenen Wärmepumpe**, nicht pauschale Klemmennummern aus Forenbeiträgen.

Mehr dazu: [Warmwasser](warmwasser.md) · [Heizungsregelung und Heizkurve](regelung_heizkurve.md).
