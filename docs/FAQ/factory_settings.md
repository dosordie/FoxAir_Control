# Factory Settings – Codes 22 und 66

Das mitgelieferte Touch-Display besitzt mehrere Ebenen für Diagnose und Einstellungen.

Für Endanwender sind vor allem die beiden Codes **22** und **66** interessant.

## Code 22 – Status und Diagnose

Mit **Code 22** gelangt man in einen Diagnose-/Factory-Bereich, in dem sich viele aktuelle Zustände der Wärmepumpe ansehen lassen.

Dort sind unter anderem sichtbar:

- Temperaturen
- digitale Eingänge
- digitale Ausgänge
- Pumpenstatus
- Kompressorstatus
- weitere interne Betriebswerte

Für die normale Fehlersuche ist **Code 22** deshalb meist der sinnvollste erste Weg.

Typisches Beispiel:

```text
Factory Settings
→ Code 22
→ Temperaturen / Ein- und Ausgänge kontrollieren
```

Viele Werte können dort einfach angesehen werden, ohne gleich Parameter zu verändern.

## Code 66 – erweiterte Parameter

Mit **Code 66** wird ein deutlich umfangreicheres Parameter-Menü geöffnet.

Dort befinden sich unter anderem Parametergruppen wie:

- **H** – Grundkonfiguration / Hardware
- **R** – Sollwerte und Regelparameter
- **P** – Pumpenparameter
- **D** – Abtauparameter
- **E** – Expansionsventil
- weitere gerätespezifische Einstellungen

Beispiele für Parameter, die dort häufig benötigt werden:

- **H25** – verwendete Regeltemperatur
- **H31** – Typ der Umwälzpumpe
- **P01** – Betriebsmodus der Hauptumwälzpumpe
- **P10** – Pumpendrehzahl
- SG-Ready-Parameter
- Heizkurven-/AT-Einstellungen

> **Achtung:** Mit Code 66 können Einstellungen verändert werden, die für Schutzfunktionen, Kältekreis, Abtauung oder Hardwarekonfiguration wichtig sind. Werte nicht auf Verdacht ändern.

Vor Änderungen am besten den bisherigen Wert notieren oder fotografieren.

## Warum sieht die WarmLink-App manchmal andere Menüs?

Die WarmLink-App verwendet ebenfalls Parameterseiten, deren Umfang von App-Version und Gerätefirmware abhängt.

Deshalb kann es vorkommen, dass:

- ein Parameter am Display sichtbar ist, aber nicht in der App,
- die App nach einem Update Menüpunkte anders darstellt,
- oder Code 66 in einer bestimmten App-Version nicht akzeptiert wird.

Das Touch-Display ist für diese Einstellungen deshalb die verlässlichere Referenz.

## Fehlerspeicher löschen

Der Fehlerspeicher wird nicht mit Code 22 oder 66 gelöscht.

Dafür wird beim entsprechenden Löschdialog der **aktuelle Kalendertag** als Code verwendet.

Beispiel:

```text
Datum: 26.09.2026
Code: 26
```

Mehr dazu:

[Fehler und Betriebszustände anzeigen](fehler_und_status.md)

## Für normale Anwender

Als einfache Faustregel:

- **22** → ansehen und diagnostizieren
- **66** → Einstellungen verändern

Wenn nur geprüft werden soll, warum die Wärmepumpe nicht startet oder welcher Sensor welchen Wert liefert, zuerst **Code 22** verwenden.
