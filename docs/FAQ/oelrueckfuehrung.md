# Ölrückführung (Oil Return) – warum der Kompressor kurz höher dreht

Manchmal erhöht die FoxAir die Kompressorfrequenz für einige Minuten, obwohl sich an der Heizanforderung nichts geändert hat. Eine mögliche Ursache dafür ist die **Ölrückführung**, auch **Oil Return** genannt.

Dieser Vorgang ist normalerweise **keine Störung**, sondern eine automatische Schutzfunktion des Kältekreises.

## Warum ist eine Ölrückführung nötig?

Das Öl schmiert den Verdichter. Ein Teil davon wird im Betrieb zusammen mit dem Kältemittel durch den Kältekreis transportiert.

Wenn der Kompressor längere Zeit mit niedriger Drehzahl läuft, kann sich Öl an anderen Stellen des Kältekreises sammeln. Die Wärmepumpe erhöht deshalb bei Bedarf vorübergehend die Verdichterfrequenz, damit Öl zuverlässig zum Verdichter zurücktransportiert wird.

## Wann startet Oil Return?

Im normalen Betrieb mit **H34 = 0** ist in den untersuchten Mainboard-Firmwares folgende Logik vorhanden:

- Der Kompressor läuft **120 Minuten ununterbrochen mit 1 bis 35 Hz**.
- Danach startet die automatische Ölrückführung.
- Die Steuerung fordert für etwa **3 Minuten nominal 60 Hz** an.
- Anschließend übernimmt wieder die normale Leistungsregelung.

Wichtig: Die **120 Minuten gelten nicht für die gesamte Verdichterlaufzeit**, sondern nur für eine durchgehende Phase mit niedriger Frequenz.

Sobald der Kompressor stoppt (**0 Hz**) oder mindestens **36 Hz** erreicht, beginnt die Zählung wieder bei null.

Beispiel:

```text
119 Minuten bei 32 Hz
→ kurzzeitig 40 Hz
→ Zähler wird zurückgesetzt
→ erst nach weiteren 120 Minuten bei 1–35 Hz
  ist die nächste Ölrückführung möglich
```

## Was bemerkt man davon?

Typische Beobachtungen können sein:

- die Kompressorfrequenz steigt ohne erkennbare Änderung des Heizsollwerts;
- die Wärmepumpe benötigt kurzzeitig mehr elektrische Leistung;
- der Verdichter ist möglicherweise etwas deutlicher zu hören;
- nach ungefähr drei Minuten sinkt die Frequenz wieder auf den Bedarf der normalen Regelung.

**60 Hz ist ein Sollwert der Ölrückführungsfunktion.** Abhängig von Schutzfunktionen und Frequenzbegrenzungen kann die tatsächliche Frequenz geringer ausfallen.

## Kann ich Oil Return am Display oder über Modbus erkennen?

Einen eigenen, direkt veröffentlichten **Oil-Return-Status** gibt es in der untersuchten Firmware nicht.

Über FoxAir Control bzw. Modbus lassen sich aber die Kompressorfrequenzen beobachten:

| Register | Bedeutung |
| ---: | --- |
| **2071** | angeforderte Kompressorfrequenz (Soll) |
| **2072** | tatsächlich gemessene Kompressorfrequenz (Ist) |

Steigt **2071** nach einer langen Niedriglastphase für etwa drei Minuten auf ungefähr **60 Hz**, passt das zur Ölrückführung.

Es ist aber **kein eindeutiger Nachweis**: Die Wärmepumpe kann auch bei normalem Heizbedarf mit 60 Hz laufen. Eine externe Steuerung kann die 120-Minuten-Zeit aus 2072 nur näherungsweise mitverfolgen.

## Ist Oil Return dasselbe wie Abtauen?

**Nein.** Beide Vorgänge können die Verdichterfrequenz verändern, erfüllen aber unterschiedliche Aufgaben:

| Ölrückführung | Abtauen |
| --- | --- |
| Soll die Schmierung des Verdichters sicherstellen | Entfernt Eis vom Verdampfer |
| Wird durch längeren Betrieb bei niedriger Frequenz ausgelöst | Hängt von Vereisung und weiteren Betriebsbedingungen ab |
| Fordert vorübergehend eine höhere Kompressorfrequenz an | Verändert den Kältekreisbetrieb, um den Verdampfer zu erwärmen |

Mehr zum [Abtauen und Frostschutz](abtauen_frostschutz.md).

## Sollte man die Funktion ausschalten?

**Nein, die normale Ölrückführung sollte nicht deaktiviert werden.** Sie dient dem Schutz und der zuverlässigen Schmierung des Verdichters.

Der Parameter **H34 (Register 1020)** heißt **ERP-Testmodus**. In der untersuchten Firmware beeinflussen dessen Testmodi auch die Ölrückführung. Er ist **kein gewöhnlicher Schalter zum Abschalten von Oil Return** und sollte im normalen Anlagenbetrieb auf **0** bleiben.

## Ab welcher Firmware ist das bekannt?

Die beschriebene Logik ist für die Mainboard-Firmware **V3.3 (Softwarecode 82400644)** durch Reverse Engineering nachgewiesen. Die zugehörigen Zeitkonstanten und Regelpfade sind auch in den untersuchten Versionen **V3.4 und V3.5** erkennbar.

Für noch ältere Firmwareversionen oder andere Softwarecode-Familien ist damit keine identische Funktion nachgewiesen.

## Wann sollte man genauer hinschauen?

Ein gelegentlicher kurzer Frequenzanstieg nach langem Niedriglastbetrieb ist normal. Wenn der Kompressor dagegen ständig unerwartet hochdreht, ungewöhnliche Geräusche auftreten oder die Anlage Fehler meldet, sollte man nicht automatisch von Oil Return ausgehen.

Hilfreich sind dann ein Verlauf der **Register 2071 und 2072**, die aktuelle Betriebsart und mögliche Fehlermeldungen. Auch andere Regel- und Schutzfunktionen können die Verdichterfrequenz beeinflussen.
