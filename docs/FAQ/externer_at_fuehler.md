# Externer Außentemperaturfühler

Mit Mainboard-Firmware **V3.4** wurde ein zusätzlicher externer Außentemperaturfühler gefunden.

Damit kann die Wärmepumpe statt des normalen T04-Außentemperaturfühlers einen zweiten Fühler verwenden.

## Aktivieren

Register **1463** wählt den verwendeten Fühler:

- **0** = normaler T04-Außentemperaturfühler
- **1** = externer Außentemperaturfühler

## Verhalten bei fehlendem Fühler

Wird der externe Fühler aktiviert, ist aber nicht angeschlossen oder liefert einen ungültigen Wert:

- die Wärmepumpe läuft weiter
- es wird auf den normalen T04-Fühler zurückgefallen
- Fehlerregister **2088 Bit 7** wird gesetzt

Bei einem Test mit offenem Eingang wurde in Register **2033** der Wert **409,1** beobachtet.

## Anschluss

Die physische Klemmenbelegung ist noch nicht abschließend bestätigt.

Aktuelle Reverse-Engineering-Vermutung:

- **Klemme 4**: Signal
- **Klemme 3**: GND
- möglicher Hardwarepfad über **DIN2 / Remote Heat-Cool**

> Diese Klemmenzuordnung ist derzeit **nicht praktisch bestätigt** und darf noch nicht als endgültiger Anschlussplan verstanden werden.
