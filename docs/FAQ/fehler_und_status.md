# Fehler und Betriebszustände anzeigen

Für die normale Fehlersuche reicht in vielen Fällen bereits das **Touch-Display der Wärmepumpe** aus.

FoxAir Control ist eher die **erweiterte Diagnoseoption**, wenn man zusätzliche Register, Rohwerte oder unbekannte Fehlerbits genauer untersuchen möchte.

## Status direkt am Touch-Display anzeigen

Am Touch-Display können unter **Factory Settings** verschiedene interne Statuswerte angezeigt werden.

Der Zugang erfolgt mit:

- **Code 22**

Dort lassen sich unter anderem kontrollieren:

- Temperaturen
- digitale Ein- und Ausgänge
- Pumpen- und Kompressorstatus
- Betriebszustände
- weitere interne Statuswerte

Das ist für die normale Fehlersuche meist der erste und einfachste Weg.

## Fehlerspeicher am Display löschen

Der Fehlerspeicher kann ebenfalls über das Touch-Display gelöscht werden.

Als Code wird der **aktuelle Kalendertag** verwendet.

Beispiel:

```text
Datum: 26.09.2026
Code:  26
```

Am nächsten Tag wäre entsprechend der neue Tageswert zu verwenden.

> Das Löschen des Fehlerspeichers beseitigt nicht die Ursache eines noch aktiven Fehlers. Besteht die Störung weiterhin, wird sie erneut angezeigt.

## Erweiterte Diagnose mit FoxAir Control

Für eine detailliertere Analyse kann **FoxAir Control** verwendet werden.

Damit lassen sich zusätzlich unter anderem anzeigen:

- aktueller Betriebsmodus
- Kompressorstatus
- Ein- und Austrittstemperaturen
- Außentemperatur
- Wasserdurchfluss
- Pumpenstatus
- Fehlerregister und einzelne Fehlerbits
- Rohwerte noch nicht vollständig erforschter Fehler

Viele Fehler der FoxAir liegen intern nicht als einzelner Fehlercode vor, sondern als Bit in einem Fehlerregister.

FoxAir Control decodiert bekannte Fehlerbits automatisch in Klartext. Bei noch unbekannten Bits bleibt der Rohwert sichtbar, was bei der weiteren Analyse hilfreich ist.

[FoxAir Control auf GitHub](https://github.com/dosordie/FoxAir_Control)

## Bei einer Fehleranfrage hilfreich

Wenn ein Fehler genauer untersucht werden soll, sind folgende Angaben besonders nützlich:

- angezeigter Fehlertext bzw. Fehlercode
- Mainboard-Firmwareversion
- aktueller Betriebsmodus
- Temperaturen zum Fehlerzeitpunkt
- betroffene Ein-/Ausgänge, falls auffällig
- bei FoxAir Control zusätzlich die Fehlerregister bzw. Rohwerte
- Zeitpunkt und Situation beim Auftreten
