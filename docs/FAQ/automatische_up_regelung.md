# Automatische Regelung der Umwälzpumpe

Ab Mainboard-Firmware **V3.3** kann die FoxAir die Drehzahl der Hauptumwälzpumpe automatisch anpassen.

Ziel ist, die Pumpe nicht dauerhaft mit unnötig hoher Drehzahl laufen zu lassen.

## Voraussetzungen

- passende Mainboard-Firmware, mindestens V3.3
- Umwälzpumpe muss am dafür vorgesehenen Mainboard-Ausgang angeschlossen sein
- **H31 – Pump Type** muss zum eingebauten Pumpentyp passen
- **P10 – Speed of Circulation Pump** muss auf **0 %** stehen

Ein fester Wert bei P10 deaktiviert die automatische Drehzahlregelung.

## Wann beginnt die Regelung?

Nach dem Kompressorstart läuft die Pumpe zunächst mit hoher Drehzahl.

Die automatische Abregelung wird erst aktiv, wenn der Wasserdurchfluss für etwa 10 Minuten ausreichend hoch war.

Wichtige Werte:

- **A40** = Nenn-Wasserdurchfluss
- für die Freigabe muss der Ist-Durchfluss ungefähr über **A40 × 1,2** liegen
- **D22** bestimmt den Mindestdurchfluss
- bei **D22 = 0** verwendet die Regelung ungefähr **A40 × 0,8** als Untergrenze

Beim Abtauen kann die Pumpe wieder mit hoher bzw. voller Leistung laufen.

## P12

**P12 – Pump Speed Adjust Range for Each Period** beeinflusst, wie stark die Pumpendrehzahl pro Regelschritt verändert wird.

Für die normale Inbetriebnahme sollte dieser Wert zunächst nicht unnötig verändert werden.

## Wenn die Pumpe nicht regelt

Als Erstes prüfen:

1. Ist die Pumpe richtig am Mainboard angeschlossen?
2. Ist H31 passend eingestellt?
3. Steht P10 wirklich auf 0 %?
4. Ist genügend Wasserdurchfluss vorhanden?

Siehe auch: [Umwälzpumpe am Mainboard umklemmen](up_umklemmen.md)
