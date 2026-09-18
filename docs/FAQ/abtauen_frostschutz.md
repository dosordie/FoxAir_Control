# Abtauen, Kondensat und Frostschutz

Bei niedriger Außentemperatur und feuchter Luft bildet sich am Verdampfer einer Luft/Wasser-Wärmepumpe Eis.

Das ist zunächst normal. Die FoxAir erkennt die Vereisung und führt bei Bedarf automatisch einen **Abtauvorgang** durch.

Abtauen und Frostschutz sind dabei zwei unterschiedliche Themen.

## Was passiert beim Abtauen?

Während des Abtauens wird der Kältekreis kurzzeitig umgekehrt. Wärme aus dem Heizwasser wird genutzt, um Eis am Verdampfer abzuschmelzen.

Typische Beobachtungen:

- der Lüfter steht zeitweise
- der Kompressorbetrieb verändert sich
- Vorlauf-/Wassertemperaturen können vorübergehend deutlich absinken
- aus der Wärmepumpe läuft viel Wasser
- es kann Dampf bzw. Nebel entstehen
- anschließend startet der normale Heizbetrieb wieder

Ein Abtauvorgang ist daher nicht automatisch eine Störung.

## Wann wird abgetaut?

Die FoxAir entscheidet anhand mehrerer Temperaturen, Drücke, Laufzeiten und Betriebszustände, wann eine Abtauung notwendig ist.

Dafür existieren zahlreiche Parameter aus der **D-Gruppe**, unter anderem für:

- Beginn der Abtauung
- Mindest-Heizzeit vor einer Abtauung
- Abtauzyklus
- Verdampfer-/Rohrtemperaturen
- maximale Abtauzeit
- Kompressorfrequenz während des Abtauens

Diese Werte sollten nicht ohne konkreten Grund verändert werden. Eine Änderung kann dazu führen, dass zu früh, zu spät oder unnötig lange abgetaut wird.

## Eis am Verdampfer

Eine gleichmäßige Reif- oder Eisschicht vor dem Abtauvorgang ist bei kalter, feuchter Witterung normal.

Auffällig ist dagegen beispielsweise:

- der Verdampfer bleibt nach dem Abtauen großflächig vereist
- die Eisschicht wächst von Zyklus zu Zyklus weiter
- der Luftweg wird stark blockiert
- Abtauungen brechen ständig ab
- die WP verliert ungewöhnlich stark Leistung

Dann sollten Sensorwerte, Luftweg, Wasserdurchfluss und die Abtauparameter geprüft werden.

## Kondensatablauf

Beim Abtauen entsteht erheblich mehr Wasser als im normalen Heizbetrieb.

Bei der GL9 wurden **zwei Ablauföffnungen** in der Bodenwanne beobachtet – eine links und eine rechts.

Im Forum wurde außerdem berichtet, dass die kleinen aufgesteckten Ablaufstutzen bei starkem Frost zufrieren können. Wenn dadurch Wasser in der Wanne stehen bleibt und erneut gefriert, kann sich dort immer mehr Eis aufbauen.

Deshalb wichtig:

- beide Abläufe frei halten
- Wasser sicher vom Gerät wegführen
- Ablauf so ausführen, dass er auch bei Frost nicht zufriert
- bei Kiesbett bzw. freiem Ablauf genügend Versickerungsmöglichkeit vorsehen

## Wannenheizung

Die GL9 besitzt je nach Ausführung eine Heizung im Bereich der Bodenwanne.

Sie soll verhindern, dass sich das beim Abtauen entstehende Wasser in der Wanne festfriert.

Ob und wann die Wannenheizung aktiv ist, hängt von Außentemperatur und Steuerung ab. Die Wannenheizung ersetzt trotzdem keinen funktionierenden Kondensatablauf.

## Frostschutz des Wasserkreises

Der **Frostschutz** soll verhindern, dass Wasser im Wärmetauscher und in den Außenleitungen gefriert.

Die Firmware besitzt dafür eigene Frostschutztemperaturen und Schutzstufen.

Wichtig ist aber:

> Der interne Frostschutz funktioniert nur, solange die Wärmepumpe elektrisch versorgt ist und die benötigte Pumpen-/Steuerfunktion noch arbeiten kann.

Bei einem längeren **Stromausfall** kann die Wärmepumpe weder Umwälzpumpe noch interne Schutzlogik aktiv betreiben.

Deshalb ist der Frostschutz einer Monoblock-Anlage nicht allein durch eine Softwareeinstellung gelöst.

## Wärmepumpe am Display ausgeschaltet

Im Forum wird davon ausgegangen, dass die Frostschutzfunktionen bei weiterhin vorhandener Netzversorgung auch dann grundsätzlich zur Verfügung stehen, wenn die WP nur über Display/App ausgeschaltet wurde.

Dieser Punkt ist dort jedoch nicht so eindeutig praktisch dokumentiert wie die normale Frostschutz- und Abtaulogik.

Wer sich auf den Frostschutz verlassen muss, sollte deshalb nicht mit einem vollständigen Stromabschalten gleichsetzen:

```text
WP über Bedienung AUS
≠
WP elektrisch spannungslos
```

## Zusätzlicher Schutz bei Stromausfall

Bei einem wassergefüllten Monoblock können je nach Anlagenkonzept zusätzliche Maßnahmen sinnvoll sein, zum Beispiel:

- Frostschutzventile
- Glykol in einem getrennten Außenkreis
- Notstrom/USV für Pumpen und Steuerung
- zusätzlicher Wärmeeintrag in den Außenkreis
- FoxAir **Hot Bypass** bzw. vergleichbare hydraulische Lösung

Welche Lösung sinnvoll ist, hängt stark von Hydraulik, Rohrführung und Standort ab.

Der im Forum diskutierte **Hot Bypass** nutzt einen warmen Wasserkreislauf bzw. gespeicherte Energie, um Außenleitungen und Wärmetauscher bei Ausfall zusätzlich vor Frost zu schützen. Er ist damit eine zusätzliche Sicherheitsmaßnahme und kein Ersatz für eine korrekt aufgebaute Anlage.

## Nicht einfach Eis mechanisch entfernen

Den Verdampfer nicht mit harten Gegenständen, Schraubendreher oder ähnlichem enteisen.

Die Lamellen und die darin liegenden Kältemittelleitungen können leicht beschädigt werden.

Wenn regelmäßig ungewöhnlich viel Eis zurückbleibt, besser die Ursache der unvollständigen Abtauung suchen.

## Bei Problemen zuerst prüfen

- Sind beide Kondensatabläufe frei?
- Friert Wasser in der Bodenwanne fest?
- Läuft die Umwälzpumpe während der nötigen Betriebsphasen?
- Ist ausreichend Wasserdurchfluss vorhanden?
- Sind Außen- und Verdampfertemperaturen plausibel?
- Wird ein echter Abtaumodus angezeigt?
- Bleibt nach dem Abtauen noch ungewöhnlich viel Eis stehen?

Erst danach sollten die eigentlichen Abtauparameter verändert werden.
