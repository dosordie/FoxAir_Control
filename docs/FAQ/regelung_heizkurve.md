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

Der Fühler wird am dafür vorgesehenen **RT/BT- bzw. Raum-/Puffersensor-Eingang** angeschlossen.

## Regelung nach Puffertemperatur

Bei **H25 = Buffer Tank Temp.** wird ein Temperaturfühler im Pufferspeicher benötigt.

Diese Betriebsart ist sinnvoll, wenn die Wärmepumpe in erster Linie einen Pufferspeicher auf Temperatur halten soll.

Auch hier gilt: Ohne passenden Fühler am vorgesehenen Eingang kennt die Wärmepumpe die reale Puffertemperatur nicht. Soweit bekannt dann der mitgelieferte Sensor verwendet werden.

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

### H36 – Art der Außentemperaturkompensation

In den untersuchten GL9-Firmwares **V3.4 und V3.5** wählt **H36 (Register 1236)** die Art der Heizkurve:

| H36 | Modus |
| ---: | --- |
| **0** | Aus |
| **1** | Lineare Kennlinie |
| **2** | 7-Punkt-Kennlinie |

#### Lineare Kennlinie

Im Modus **H36 = 1** bestimmen **Register 1234** (Steigung) und **Register 1235** (Offset bzw. Mittelpunkt) die lineare Heizkurve.

#### 7-Punkt-Kennlinie

Im Modus **H36 = 2** werden Heiz-Solltemperaturen an sieben festen Außentemperatur-Stützstellen vorgegeben:

| Außentemperatur | Register des Heiz-Sollwerts |
| ---: | ---: |
| **-20 °C** | **1250** |
| **-10 °C** | **1251** |
| **-5 °C** | **1252** |
| **0 °C** | **1235** |
| **+5 °C** | **1253** |
| **+10 °C** | **1254** |
| **+20 °C** | **1255** |

Zwischen benachbarten Punkten interpoliert die Regelung linear. Für die Kurvenberechnung wird die verwendete Außentemperatur auf **-20 bis +20 °C** begrenzt.

**Register 1234** spielt im 7-Punkt-Modus keine Rolle. **Register 1235** hat damit eine Doppelrolle: linearer Offset/Mittelpunkt in Modus 1 und 0-°C-Sollwert in Modus 2.

#### Grenzen und aktuelle Werte

Nach der Kurvenberechnung wird das Ergebnis durch **R10 (Register 1164, minimale Heiz-Solltemperatur)** und **R11 (Register 1165, maximale Heiz-Solltemperatur)** begrenzt.

Die aktuell für die Kurve verwendete Außentemperatur steht in **Register 2048**, die daraus resultierende kompensierte Solltemperatur in **Register 2014**. Diese beiden Werte sind Laufzeitwerte und werden in FoxAir Control nur angezeigt, nicht als Kurvenparameter geschrieben.

### WarmLink 3.0.5: 7-Punkt-Kurve über Cloud lesen

Die WarmLink-Android-App **3.0.5 / Family 416, Softwarecode 644** bestätigt
dieselben festen Stützstellen wie die GL9-Mainboard-Firmware:
**-20 / -10 / -5 / 0 / +5 / +10 / +20 °C**.

| AT | Zone-1-Cloudcode | MAIN-Register |
| ---: | --- | ---: |
| -20 °C | `CP1-1` | 1250 |
| -10 °C | `CP1-2` | 1251 |
| -5 °C | `CP1-3` | 1252 |
| 0 °C | `compensate_offset` | 1235 |
| +5 °C | `CP1-5` | 1253 |
| +10 °C | `CP1-6` | 1254 |
| +20 °C | `CP1-7` | 1255 |

**`CP1-4` wird von der App abgefragt, aber nicht als 0-°C-Punkt verwendet.**
Es erhält keine lokale Projektion auf 1235 oder ein anderes Register. Für Zone 2
fragt die App analog `CP2-1`…`CP2-7` ab; der tatsächliche Mittelpunkt stammt
aus **`Zone 2 Curve Offset`**, ebenfalls nicht aus `CP2-4`. Alle CP-Codes stehen
im Cloudkatalog und sind read-only verfügbar. Die lokalen Zone-2-Register bleiben
unbestätigt und werden nicht geraten.

Ab FoxAir Control **0.3.3** funktioniert **AT-Kompensation → von WP lesen**
auch Cloud-only. Der vorhandene Worker liest gezielt H36, Steigung/Offset,
die sechs CP1-Stützwerte, R10/R11, T04, 2014 und 2146 über
`app/device/getDataByCode` (`protocalCodes`), ohne Fullscan. Die Abfrage wird
mit normalem Polling und CSV seriell ausgeführt. Bereits gelesene Cloudwerte
erscheinen sofort im offenen Dialog; Engineering-Werte werden nicht erneut
als Modbus skaliert. Lokale Werte haben bei aktivem lokalem Transport Vorrang
und bleiben getrennt von Cloud. Nach lokalem Disconnect zeigt AT Cloudwerte,
auch wenn alte lokale Werte im Cache bleiben; nach Reconnect gewinnt lokal wieder.

**Schreiben der AT-Kurve bleibt lokal.** Im Cloud-only-Betrieb sind H36-/Linear-/
7-Punkt-Schreibbuttons gesperrt. Die CP1-Codes bekommen keine Cloud-Schreibfreigabe.
Cloud-Schreiben erfordert einen späteren separaten PR mit bestätigtem Endpoint,
Payload, Reihenfolge und Readback am realen Gerät.

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


## Empfehlung bei der Fehlersuche

Für einen möglichst einfachen Testbetrieb:

- **H25 = Outlet Water Temp.**
- eine sinnvolle feste Heizwassertemperatur einstellen
- AT-Entschädigung zunächst deaktivieren
- prüfen, ob die WP sauber startet und die Solltemperatur erreicht

Erst danach Heizkurve, Raumregelung oder externe Steuerung Schritt für Schritt ergänzen.

Die genaue optimale Heizkurve hängt stark von Gebäude, Heizflächen und gewünschter Raumtemperatur ab und kann deshalb nicht allgemein vorgegeben werden.
