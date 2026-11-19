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
- zusätzliche Angaben zur Fehlersuche

FoxAir Control zeigt bekannte Fehler in Klartext an. Bei manchen Fehlern können zusätzliche Angaben helfen, die Ursache einzugrenzen.

[FoxAir Control auf GitHub](https://github.com/dosordie/FoxAir_Control)

## Durchflussfehler E030, E032 und E035

Diese drei Fehler klingen ähnlich, haben aber unterschiedliche Ursachen:

| Fehler | Was bedeutet das? |
| --- | --- |
| **E030** | Beim Abtauen ist der Wasserdurchfluss seit ungefähr **10 Sekunden** zu gering. Die Grenze wird mit **D22** eingestellt; die Verdichterdrehzahl wird beim Abtauen auf maximal **50 Hz** begrenzt. |
| **E032** | Der mechanische **Durchflussschalter an Eingang S3** meldet eine Störung. Der Verdichter kann deshalb gestoppt werden. |
| **E035** | Der **berechnete Wasserdurchfluss** ist zu gering. Die Grenze liegt bei ungefähr **50 % von A40**. Auch dieser Fehler kann den Verdichter stoppen. |

Bei **E035** kann die Störung nach etwa **6 Sekunden** zu geringem Durchfluss auftreten, sobald die Überwachung aktiv ist. Je nach Betriebszustand kann es auch länger dauern. E035 ist **auch beim Heizen** möglich und nicht auf das Abtauen beschränkt.

**Wann ist der Fehler wieder weg?** Bei E035 muss der berechnete Durchfluss normalerweise ungefähr **10 Sekunden über 60 % von A40** liegen. E032 kann nach behobener Ursache nach ungefähr **3 Sekunden** verschwinden. Beide Angaben sind Richtwerte, keine garantierten Zeiten.

**Muss man die Wärmepumpe neu starten?** Nicht unbedingt: Nach E032 oder E035 kann der Verdichter **automatisch wieder anlaufen**, wenn die Ursache beseitigt ist, weiterhin Wärme gebraucht wird und keine andere Sperre aktiv ist. Der Start kann zusätzliche Zeit benötigen.

Bei E032 zuerst prüfen, ob wirklich genügend Wasser fließt. Ist das der Fall, kommen auch der Durchflussschalter und sein Anschluss **S3** als Fehlerursache infrage. Bei E035 zusätzlich prüfen, ob der eingestellte Pumpentyp **H31** stimmt und ob der angezeigte Durchfluss plausibel ist.

Weitere Erläuterungen und Prüfschritte stehen unter [Wasserdurchfluss und Pumpenbetriebsarten](wasserdurchfluss_pumpe.md#durchflussfehler-e030-e032-und-e035).

## Bei einer Fehleranfrage hilfreich

Wenn ein Fehler genauer untersucht werden soll, sind folgende Angaben besonders nützlich:

- angezeigter Fehlertext bzw. Fehlercode
- Mainboard-Firmwareversion
- aktueller Betriebsmodus
- Temperaturen zum Fehlerzeitpunkt
- betroffene Ein-/Ausgänge, falls auffällig
- bei FoxAir Control zusätzlich die Fehlerregister bzw. Rohwerte
- Zeitpunkt und Situation beim Auftreten
