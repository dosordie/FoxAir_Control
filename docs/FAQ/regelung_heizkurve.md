# Heizungsregelung, H25 und Heizkurve

Die FoxAir kann auf unterschiedliche Arten regeln. Viele Startprobleme oder scheinbar unlogische Sollwerte entstehen dadurch, dass **H25**, die eingestellte Solltemperatur und die **AT-Entschädigung / Heizkurve** nicht zueinander passen.

## H25 – welche Temperatur soll geregelt werden?

Parameter **H25** legt fest, welche Temperatur die Wärmepumpe als Regelgröße verwendet.

| H25 | Regelung nach |
| ---: | --- |
| **0** | Auslasswassertemperatur / Vorlauf |
| **1** | Raumtemperatur |
| **2** | Puffertanktemperatur |
| **3** | Einlasswassertemperatur / Rücklauf |

Für viele einfache Anlagen ist **Outlet Water Temp. / Auslasswassertemperatur** der leicht verständliche Ausgangspunkt.

## Regelung nach Auslasswassertemperatur

Bei **H25 = Outlet Water Temp.** versucht die Wärmepumpe, die eingestellte Wassertemperatur zu erreichen.

Das ist beispielsweise sinnvoll, wenn:

- die Wärmepumpe direkt einen Heizkreis versorgt,
- die gewünschte Vorlauftemperatur fest vorgegeben werden soll,
- oder eine externe Steuerung die Wärmepumpe nur ein- und ausschaltet.

Wenn eine feste Vorlauftemperatur gefahren werden soll, darf eine zusätzlich aktive **AT-Entschädigung** den Sollwert nicht unerwartet verändern. Bei der Fehlersuche deshalb immer prüfen, ob die AT-Entschädigung aktiviert ist.

## Regelung nach Raumtemperatur

Bei **H25 = Room Temp.** benötigt die Wärmepumpe einen passenden Raumtemperaturfühler.

Ohne angeschlossenen Sensor kann die Regelung keine sinnvolle reale Raumtemperatur erfassen.

Der Fühler wird am dafür vorgesehenen **RT/BT- bzw. Raum-/Puffersensor-Eingang** angeschlossen. Die genaue Klemmennummer kann je nach Mainboard-/Gerätevariante unterschiedlich sein – deshalb den Schaltplan bzw. die Beschriftung der eigenen Wärmepumpe verwenden.

## Regelung nach Puffertemperatur

Bei **H25 = Buffer Tank Temp.** wird ein Temperaturfühler im Pufferspeicher benötigt.

Diese Betriebsart ist sinnvoll, wenn die Wärmepumpe in erster Linie einen Pufferspeicher auf Temperatur halten soll.

Auch hier gilt: Ohne passenden Fühler am vorgesehenen Eingang kennt die Wärmepumpe die reale Puffertemperatur nicht.

## Regelung nach Einlasswassertemperatur

Bei **H25 = Inlet Water Temp.** wird nach der Rücklauf-/Einlasstemperatur geregelt.

Diese Variante wird deutlich seltener verwendet als die Regelung nach Auslasswassertemperatur.

## Was macht die AT-Entschädigung / Heizkurve?

Die **AT-Entschädigung** passt die benötigte Heizwassertemperatur abhängig von der Außentemperatur an.

Grundidee:

- draußen mild → niedrigere Heizwassertemperatur
- draußen kalt → höhere Heizwassertemperatur

Damit muss nicht für jede Wetterlage manuell eine neue Vorlauftemperatur eingestellt werden.

Bei Firmware **V3.4** kann die Heizkurve außerdem zusammen mit den Leistungstimern verwendet werden.

## Warum startet die Wärmepumpe manchmal nicht?

Wenn die WP trotz vermeintlicher Heizanforderung nicht startet, zuerst prüfen:

1. Welcher Wert ist bei **H25** eingestellt?
2. Ist der dafür benötigte Temperaturfühler tatsächlich vorhanden?
3. Ist die **AT-Entschädigung** aktiv?
4. Welche Solltemperatur ergibt sich dadurch aktuell?
5. Liegt die gemessene Temperatur bereits innerhalb der Ein-/Ausschalthysterese?
6. Ist überhaupt **Heizen** als Betriebsart aktiviert?
7. Liegt ein Durchfluss- oder anderer Fehler vor?

Gerade eine Kombination aus falscher H25-Auswahl und fehlendem Raum-/Pufferfühler kann zu schwer nachvollziehbarem Verhalten führen.

## Remote On/Off ist keine Temperaturregelung

Ein externes Raumthermostat kann die Wärmepumpe über **Remote On/Off** freigeben oder sperren.

Das bedeutet aber nur:

```text
Heizanforderung EIN / AUS
```

Das externe Thermostat überträgt dadurch **keine Raumtemperatur** an die Wärmepumpe.

Soll die FoxAir selbst nach Raumtemperatur regeln, benötigt sie einen eigenen angeschlossenen Raumfühler und die passende H25-Einstellung.

## Empfehlung bei der Fehlersuche

Für einen möglichst einfachen Testbetrieb:

- **H25 = Outlet Water Temp.**
- eine sinnvolle feste Heizwassertemperatur einstellen
- AT-Entschädigung zunächst deaktivieren
- prüfen, ob die WP sauber startet und die Solltemperatur erreicht

Erst danach Heizkurve, Raumregelung oder externe Steuerung Schritt für Schritt ergänzen.

Die genaue optimale Heizkurve hängt stark von Gebäude, Heizflächen und gewünschter Raumtemperatur ab und kann deshalb nicht allgemein vorgegeben werden.
