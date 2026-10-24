# Auslauftemperatur und Kompressorfrequenz – wie regelt die FoxAir?

Die FoxAir passt ihre Heizleistung hauptsächlich über die **Kompressorfrequenz** an. Entscheidend ist dabei nicht die Zahl der Vorlauftemperatur in °C, sondern die **Abweichung zwischen gewünschter und gemessener Temperatur**.

Diese Beschreibung bezieht sich auf die untersuchte **Mainboard-Firmware V3.5 (Softwarecode 82400644)**. Ältere Versionen, insbesondere V1.3, können sich im Detail anders verhalten.

## Was bedeutet Auslauftemperaturregelung?

Mit **H25 = 0 (Outlet Water Temp.)** wird die **Auslasswassertemperatur T02 (Vorlauf)** als zentrale Regelgröße verwendet.

Beispiel: Sind 35 °C gewünscht und T02 liegt bei 30 °C, besteht Heizbedarf. Nähert sich T02 den 35 °C, muss die WP nicht mehr dieselbe Leistung liefern. Liegt T02 darüber, muss sie die Leistung weiter reduzieren oder – wenn das nicht mehr möglich ist – schließlich abschalten.

Die Solltemperatur kann fest eingestellt sein oder durch eine aktive **AT-Entschädigung / Heizkurve** und weitere Korrekturen verändert werden. Es ist daher wichtig, den **tatsächlich wirksamen Sollwert** zu betrachten und nicht nur die ursprünglich eingestellte Temperatur.

Andere H25-Modi verwenden Raum-, Puffer- oder Einlasstemperatur als übergeordnete Führungsgröße. Die interne Leistungsregelung bleibt komplexer als ein direkter Vergleich dieser Temperatur mit der Frequenz. Mehr dazu unter [Heizungsregelung, H25 und Heizkurve](regelung_heizkurve.md).

## Wie wird die Kompressorfrequenz geregelt?

Die untersuchte Firmware verwendet im normalen Temperaturregelpfad einen **PID-Regler**. Dieser berücksichtigt nicht nur die aktuelle Temperaturabweichung, sondern auch deren zeitlichen Verlauf.

Vereinfacht:

- **Temperatur deutlich unter dem Soll:** Die Regelung kann eine höhere Frequenz anfordern, um mehr Wärme zu liefern.
- **Temperatur nähert sich dem Soll:** Die Frequenz wird nicht beliebig oder sprunghaft verändert. Im kleinen Regelbereich kann die aktuelle Anforderung zunächst gehalten werden.
- **Temperatur oberhalb des Solls:** Die Regelung arbeitet auf eine Verringerung der Frequenz hin. Ob und wie weit sie tatsächlich herunterkommt, hängt auch von Mindestfrequenz und Betriebszustand ab.

Der PID-Rechenkern wird etwa **alle 0,5 Sekunden** ausgeführt. Das bedeutet **nicht**, dass der reale Verdichter alle 0,5 Sekunden seine Drehzahl ändern muss: weitere Freigaben, Begrenzungen und die Dynamik des Kältekreises wirken mit.

Die zugehörigen Serviceparameter heißen **C13 (P-Anteil)**, **C14 (I-Skalierung)** und **C15 (D-Anteil)**. Sie beeinflussen das Regelverhalten, sind aber **keine normalen Optimierungsregler für den Anwender**. Ohne belastbare Messungen sollten sie nicht verändert werden; insbesondere ist C14 intern ein Divisor und darf nicht auf 0 gesetzt werden.

Eine einfache Formel wie **„Auslauftemperatur in °C + 2 = Kompressorfrequenz in Hz“** existiert im untersuchten V3.5-Regelpfad nicht. Wenn die angezeigten Zahlen zufällig ähnlich sind, ergibt das noch keinen Zusammenhang.

## Warum dreht der Verdichter nicht sofort hoch oder herunter?

Die geforderte Frequenz ist nicht automatisch die tatsächlich mögliche Frequenz.

Unter anderem greifen:

- **C02 / Register 1219:** konfigurierte Mindestfrequenz (häufig 30 Hz als Ausgangswert)
- **C03 / Register 1220:** konfigurierte Höchstfrequenz
- dynamische Frequenzgrenzen und Schutzfunktionen, beispielsweise abhängig von Kältekreiszustand, Druck oder elektrischer Belastung
- Start-, Betriebs- und Sonderzustände wie Abtauen und Ölrückführung
- gegebenenfalls externe Leistungsbegrenzungen und Remote-/SG-Regelungen

Besonders wichtig ist die **Mindestfrequenz**: Benötigt das Gebäude weniger Wärme, als der Verdichter bei seiner derzeitigen Mindestfrequenz abgibt, kann die WP nicht unbegrenzt heruntermodulieren. Die Temperatur kann weiter steigen, bis die Regelung über ihre Ein-/Ausschaltschwellen den Verdichter stoppt. Das ist nicht automatisch ein Regelfehler.

Auch umgekehrt gilt: Wenn der Verdichter nicht hochdreht, obwohl die Temperatur deutlich unter dem Soll liegt, sollte zuerst nach aktiven Frequenzbegrenzungen geschaut werden – nicht gleich nach einem defekten PID-Regler.

**Wichtig:** In V3.5 können zusätzlich externe/adaptive Regelpfade aktiv sein. Sie ändern aber nichts daran, dass die üblichen Mindest-/Höchstgrenzen und Schutzfunktionen berücksichtigt werden.

## Warum ist es beim Warmwasser anders?

Bei der **Warmwasserbereitung** muss die Wärmepumpe den Speicher über einen Wärmetauscher erwärmen. Die angezeigte Speichertemperatur ist nicht identisch mit der Auslasswassertemperatur T02.

Je wärmer der Speicher wird, desto kleiner wird gewöhnlich die Temperaturdifferenz, über die noch Wärme übertragen werden kann. Hinzu kommen die höheren erforderlichen Kältekreistemperaturen und mögliche Leistungs- oder Schutzgrenzen. Deshalb kann sich die Frequenz im Warmwasserbetrieb anders verhalten als beim Heizen.

Für die Beurteilung müssen deshalb **Speicher-Istwert, Warmwasser-Sollwert, T01/T02, Kompressorfrequenz und der zeitliche Verlauf** gemeinsam betrachtet werden.

Siehe auch [Warmwasser mit der FoxAir](warmwasser.md).

## Warum habe ich nur 2 K Spreizung zwischen Vorlauf und Rücklauf?

Die **Spreizung (T02 minus T01)** ist ein anderer Sachverhalt als die Kompressorregelung. Sie hängt von der **abgegebenen Wärmeleistung und vom Wasserdurchfluss** ab.

- **Mehr Wasserdurchfluss** bei gleicher Leistung → kleinere Spreizung.
- **Weniger Wasserdurchfluss** bei gleicher Leistung → größere Spreizung.
- **Geringere Heizleistung** bei gleichem Durchfluss → ebenfalls kleinere Spreizung.

**2 K sind daher nicht automatisch ein Fehler.** Bei ungefähr 1,0 m³/h entspricht eine Spreizung von 2 K rechnerisch nur rund 2,3 kW übertragener Wärmeleistung. Bei 1,5 m³/h wären es rund 3,5 kW. Der Zusammenhang erklärt, weshalb eine stark laufende Umwälzpumpe eine niedrige Spreizung erzeugen kann.

**Wichtig bei älterer Firmware:** Dass die PWM-Leitung korrekt angeschlossen wurde, bedeutet nicht automatisch, dass die Wärmepumpe den Durchfluss selbst auf eine Soll-Spreizung regelt. Die **automatische ΔT-Pumpenregelung gibt es in der untersuchten Firmwarefamilie ab Mainboard V3.3**. Dort sind **H31** (richtiger Pumpentyp), **P10 = 0 %** (Automatik) und **P11/P12** relevant. Mit älterer V1.3 oder fester P10-Vorgabe kann die Pumpendrehzahl trotz PWM-Anschluss einfach fest sein.

Den Durchfluss niemals nur für eine größere Spreizung so weit senken, dass Mindestdurchfluss, Wärmeübertragung oder Abtauen gefährdet werden.

Mehr dazu: [Wasserdurchfluss und Pumpenbetriebsarten](wasserdurchfluss_pumpe.md) und [Automatische Regelung der Umwälzpumpe](automatische_up_regelung.md).

## So lässt sich die Regelung gezielt überprüfen

Statt nur einen einzelnen Frequenzwert zu vergleichen, ist ein Verlauf über einige Minuten deutlich aussagekräftiger. Am besten getrennt für **Heizen** und **Warmwasser** folgende Werte protokollieren:

| Wert | Bedeutung |
| --- | --- |
| **T01 / T02** | Einlass- und Auslasswassertemperatur (Rücklauf/Vorlauf) |
| **wirksamer Temperatur-Sollwert** | Nicht nur der manuell eingestellte Wert; bei Heizen ggf. Heizkurve/Korrekturen beachten |
| **2071 (Soll-Hz)** | Vom Mainboard angeforderte Kompressorfrequenz |
| **2072 (Ist-Hz)** | Tatsächlich gemeldete Kompressorfrequenz |
| **2077 (Durchfluss)** | Tatsächlich gemeldeter Wasserdurchfluss, sofern plausibel erfasst |
| **C02 / C03** | Eingestellte Frequenzgrenzen |
| **H25 / P10 / H31** | Art der Temperaturregelung sowie Pumpenkonfiguration |
| **Betriebsart und WW-Speichertemperatur** | Zur Unterscheidung von Heizen und Warmwasser |

Bei Bedarf können in V3.5 zusätzlich **2139 (Frequenzbegrenzungsstatus)** und **2152 (EMS-/Remotezustände)** Hinweise liefern. **Ein einzelnes gesetztes Bit beweist noch keine aktuell wirksame Frequenzbegrenzung.**

Als erste Einordnung:

- **Soll- und Istfrequenz liegen dauerhaft an C02:** möglicherweise Mindestleistung erreicht; die WP kann nicht weiter herunterregeln.
- **Sollfrequenz bleibt niedrig, obwohl die wirksame Solltemperatur deutlich unterschritten wird:** H25, Sollwertquelle, Betriebszustand und Regelpfad prüfen.
- **Sollfrequenz steigt, Istfrequenz folgt nicht:** mögliche Inverter-, Betriebs- oder Schutzbegrenzung prüfen.
- **Nur 2 K Spreizung bei hohem Durchfluss:** zunächst Wasserleistung und Pumpeneinstellung beurteilen, nicht die Verdichterregelung verdächtigen.

Kurzzeitig höhere Verdichterfrequenzen können auch durch die [Ölrückführung (Oil Return)](oelrueckfuehrung.md) entstehen.

## Hilft ein Firmware-Update?

Ein Update **kann** neue Funktionen und ein anderes Betriebsverhalten mitbringen, ist aber **keine Garantie** dafür, dass die Wärmepumpe anschließend stärker oder schneller moduliert.

Gerade bei **Mainboard V1.3** ist der Unterschied relevant, weil die automatische Pumpenregelung auf Soll-Spreizung erst ab **V3.3** dokumentiert ist. Die Mainboard-Version ist außerdem **nicht** mit der getrennten Display-Firmware zu verwechseln.

Vor einem Update den **Mainboard-Softwarecode und die genaue Mainboard-Version** überprüfen, Einstellungen sichern und die Kompatibilität abklären. Siehe [Firmware-Versionen und Update](firmware.md).

---

**Kurz gesagt:** Die FoxAir regelt die Kompressorfrequenz nicht nach der bloßen Vorlauftemperaturzahl. Im V3.5-Regelpfad werden Temperaturabweichung, zeitlicher Verlauf und Betriebsgrenzen berücksichtigt. Eine niedrige Wasserspreizung ist dabei kein Beweis für eine fehlerhafte Verdichterregelung.
