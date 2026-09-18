# Fehler und Betriebszustände anzeigen

FoxAir Control kann neben Temperaturen und Parametern auch Betriebszustände und Fehlerregister anzeigen.

## Typische Informationen

Dazu gehören unter anderem:

- aktueller Betriebsmodus
- Kompressorstatus
- Ein- und Austrittstemperatur
- Außentemperatur
- Wasserdurchfluss
- Pumpenstatus
- aktive Fehlerbits

## Fehler

Viele Fehler der FoxAir liegen nicht als einzelner Fehlercode vor, sondern als Bit in einem Fehlerregister.

FoxAir Control decodiert bekannte Bits automatisch in Klartext.

Bei noch nicht vollständig erforschten Fehlerbits wird der Rohwert weiterhin angezeigt. Dieser ist bei der Fehlersuche wichtig und sollte bei einer Anfrage immer mit angegeben werden.

Hilfreich sind außerdem:

- Mainboard-Softwarecode und Firmwareversion
- aktueller Betriebsmodus
- betroffene Fehlerregister
- Zeitpunkt bzw. Betriebszustand beim Auftreten
