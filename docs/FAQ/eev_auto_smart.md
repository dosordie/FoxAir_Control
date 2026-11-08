# EEV Auto oder Smart – welcher Modus ist effizienter?

Die FoxAir bietet für das **elektronische Expansionsventil (EEV)** unterschiedliche Regelungsarten. Besonders interessant sind **Auto** und **Smart**. Beide passen die Kältemittelzufuhr an, unterscheiden sich aber darin, wie frei die Ventilöffnung geregelt werden darf.

Nach unseren bisherigen Tests gibt es eine erste Tendenz: **Smart könnte bei den bisher untersuchten Außentemperaturen einen leichten COP-Vorteil haben.** Ob das auch bei stärkerem Frost über eine ganze Heizsaison gilt, wissen wir noch nicht.

## Was macht das EEV?

Das EEV dosiert das Kältemittel im Kältekreis. Die Ventilöffnung wird in **Schritten** angegeben: Mehr Schritte bedeuten eine größere Öffnung, weniger Schritte eine kleinere.

Wichtig ist die **Saugüberhitzung**. Sie beschreibt die Temperaturdifferenz zwischen dem Sauggas am Verdichter und der zur Niederdruckseite gehörenden Verdampfungstemperatur. Die Wärmepumpe muss den Verdampfer gut ausnutzen, gleichzeitig aber ausreichend Abstand zu einem möglichen Flüssigkeitsrücklauf zum Verdichter halten.

Deshalb gilt: **Ein möglichst weit geöffnetes Ventil oder eine möglichst kleine Überhitzung ist nicht automatisch effizienter oder besser.**

## Was unterscheidet EEV Auto und EEV Smart?

### Auto – Regelung nach Überhitzung

Im Modus **Auto (E01 = 1)** wird die Ventilöffnung anhand der gemessenen Überhitzung nachgeregelt. Im Heizbetrieb ist dafür **E02** der Sollwert, beispielsweise 3,0 K.

- Ist die Überhitzung zu hoch, kann die Regelung das EEV weiter öffnen.
- Ist sie zu niedrig, kann die Regelung es weiter schließen.
- Zusätzlich berücksichtigt die Firmware Schutz- und Temperaturzustände, unter anderem die Heißgastemperatur.

Auto ist damit **keine einfache starre Ein-Aus-Regelung**, sondern eine laufende, zustandsabhängige Regelung. Das EEV kann seine Öffnung innerhalb der allgemeinen Sicherheitsgrenzen vergleichsweise frei anpassen.

### Smart – Auto-Regelung mit zusätzlichem Kennfeld

Im Modus **Smart (E01 = 2)** bleibt die normale Überhitzungsregelung aktiv. Zusätzlich berechnet die Firmware einen sinnvollen Arbeitspunkt aus:

- **Außentemperatur (T04)**
- **angeforderter Kompressorfrequenz**
- **Einlasswassertemperatur (T01)**

Dazu verwendet sie ein festes Kennfeld aus Kompressorfrequenz und Außentemperatur, das anschließend anhand der Einlasswassertemperatur korrigiert wird.

Die normale Auto-Regelung darf die Ventilöffnung dann nur innerhalb eines bestimmten Fensters um diesen berechneten Arbeitspunkt verändern. Dieses Fenster legt **E19** fest.

Bei **E19 = 20 %** bedeutet das **±20 %** um den berechneten Mittelpunkt – nicht insgesamt 20 %.

**Beispiel:** Ergibt das Kennfeld einen Mittelpunkt von 100 Schritten, darf die normale Regelung im Smart-Modus zunächst zwischen ungefähr 80 und 120 Schritten korrigieren. Nachgelagerte Mindestöffnungen und Schutzfunktionen können diese Grenzen allerdings noch übersteuern.

Smart ist also **keine feste Ventilstellung**, sondern eine Überhitzungsregelung mit zusätzlicher kennfeldabhängiger Begrenzung.

## Wie verhält sich das in der Praxis?

Wir haben beide Betriebsarten an einer FoxAir GL9 verglichen. Dabei zeigte sich, dass Smart häufig eine andere Ventilöffnung verwendet als Auto, obwohl die Wärmepumpe unter ähnlichen Bedingungen läuft.

Ein direkter Kurzvergleich bei ungefähr **15 °C Außentemperatur und 29 Hz Kompressorfrequenz** ergab:

| Messwert | EEV Smart | EEV Auto |
| --- | ---: | ---: |
| EEV-Öffnung | ca. 108 Schritte | ca. 119 Schritte |
| Saugüberhitzung | ca. 4,76 K | ca. 4,67 K |
| Elektrische Aufnahme | ca. 588 W | ca. 594 W |
| Heizleistung | ca. 3,63 kW | ca. 3,59 kW |
| COP | **6,16** | **6,04** |

In diesem Vergleich lag Smart beim COP um ungefähr **2 %** vorn.

Die Ventilöffnung war dabei etwas kleiner, die Saugüberhitzung jedoch in beiden Fällen ähnlich. Das zeigt auch, dass man aus der Ventilposition allein **nicht direkt auf den COP schließen kann**.

**Wichtig:** Das war ein kurzer Vergleich bei nahezu gleichen Bedingungen, keine langfristige A/B-Messung. Schon kleine Änderungen bei Temperaturen, Leistungsregelung oder Messauflösung können das Ergebnis beeinflussen.

Smart lieferte zudem eine minimal höhere Heizleistung. Falls das an der Leistungsuntergrenze zu häufigeren Verdichterstarts führt, könnte ein möglicher Vorteil im Dauerbetrieb teilweise wieder verloren gehen.

## Was passiert bei kühleren Außentemperaturen und Vereisung?

Auch bei kühleren Außentemperaturen haben wir Smart beobachtet. Beispielsweise lief die Anlage bei etwa **13,6 °C Außentemperatur und 28 Hz** mit ungefähr 108 EEV-Schritten und einem COP um 5,36. Für diesen Betriebspunkt gibt es allerdings keinen unmittelbar vergleichbaren Auto-Messwert.

Interessant war außerdem das Verhalten bei etwa **1,6 bis 1,8 °C Außentemperatur**, als der Verdampfer zunehmend vereiste:

- Der Niederdruck sank im Verlauf der Vereisung.
- Bei ungefähr **46 Hz** vergrößerte Smart die Ventilöffnung zeitweise von etwa **64 auf 103 Schritte**.
- Später wurde eine sehr geringe Saugüberhitzung um **1,1 K** beobachtet.

Smart reagiert also durchaus dynamisch auf wechselnde Betriebsbedingungen. Ein anderer EEV-Arbeitspunkt kann den Verdampfungsdruck beeinflussen und damit auch die Effizienz.

Die sehr geringe Überhitzung zeigt aber zugleich, dass die Sicherheitsreserve klein werden kann. Aus dieser einzelnen Beobachtung lässt sich **kein Sicherheits- oder Effizienzvorteil** ableiten. Außerdem fehlt für genau diesen Vereisungsverlauf ein direkter Auto-Gegenversuch.

Ob Smart bei häufigen Abtauungen oder deutlich niedrigeren Temperaturen besser abschneidet, ist deshalb weiterhin offen.

## Welche Einstellungen und Messwerte sind wichtig?

| Parameter / Register | Bedeutung |
| --- | --- |
| **E01 / 1131** | EEV-Regelmodus: 0 = Manuell, 1 = Auto, 2 = Smart |
| **E02 / 1132** | Ziel-Saugüberhitzung beim Heizen |
| **E07 / 1137** | EEV-Mindestöffnung im betreffenden Betriebsbereich |
| **E18 / 1148** | Ziel-Saugüberhitzung beim Kühlen |
| **E19 / 1149** | Smart-Korrekturfenster in ± Prozent |
| **2020** | Aktuelle EEV-Position in Schritten |
| **2065** | Aus dem Niederdruck berechnete Verdampfungstemperatur |
| **2067** | Gemessene Saugüberhitzung |
| **2071 / 2072** | Kompressor-Soll- und Istfrequenz |

Mit [FoxAir Control](foxair_control_ueberblick.md) lassen sich viele dieser Werte beobachten. Sinnvoll ist, zusätzlich Außentemperatur, Wassereintritts- und Austrittstemperatur, Druckwerte und elektrische Leistungsaufnahme zu vergleichen.

Wichtig für den COP-Vergleich: **Heizleistung und Stromaufnahme müssen möglichst gleichzeitig und mit ausreichender Messauflösung erfasst werden.** Ein einzelner Momentanwert oder eine ganze Tagesbilanz mit unterschiedlichen Abtauungen reicht nicht für einen zuverlässigen Vergleich.

## Sollte man E02 oder E19 verändern?

Für den normalen Betrieb empfehlen wir zunächst, die vorhandenen Einstellungen beizubehalten.

**E02** bestimmt den Überhitzungs-Sollwert. Ein besonders niedriger Wert ist nicht automatisch effizienter und kann die Reserve gegenüber flüssigem Kältemittel verringern.

**E19** bestimmt nur, wie weit Smart vom berechneten Kennfeldwert abweichen darf:

- Kleineres E19: stärkere Bindung an das Smart-Kennfeld.
- Größeres E19: mehr Freiheit für die normale Überhitzungsregelung.

Auch wenn man damit das Verhalten beeinflussen kann, sollte man diese Parameter **nicht ohne Messungen und Verständnis der Schutzgrenzen auf Verdacht ändern**.

## Welchen Modus empfehlen wir aktuell?

**Für den normalen Heizbetrieb würden wir derzeit leicht zu EEV Smart tendieren.**

Unser direkter Kurzvergleich bei rund 15 °C Außentemperatur zeigte einen kleinen COP-Vorteil von etwa 2 %. Die weiteren Beobachtungen bis in den niedrigen einstelligen Außentemperaturbereich sprechen bislang nicht eindeutig gegen Smart, sind aber **kein kontrollierter Effizienznachweis gegenüber Auto**.

Auto bleibt eine sinnvolle Alternative: Es besitzt mehr Freiheit bei der Überhitzungsregelung und könnte unter bestimmten Betriebsbedingungen günstiger sein.

**Unser vorläufiges Fazit:** Bis zu den bisher beobachteten Außentemperaturen scheint **EEV Smart möglicherweise etwas effizienter** zu sein. Ob dieser Vorsprung bei Frost, häufigem Abtauen und über eine gesamte Heizsaison bestehen bleibt, müssen weitere Messungen zeigen.

---

*Stand: Oktober 2026. Grundlage sind eigene Messungen und das Reverse Engineering der FoxAir GL9 mit Mainboard-Firmware V3.3 bis V3.5. Die Auto-/Smart-Regelpfade wurden in V3.4 untersucht und für V3.5 als unverändert bestätigt. Andere Gerätemodelle und Firmwarefamilien können sich unterscheiden.*
