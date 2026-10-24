# FoxAir Control – Funktionen und Bedienung

FoxAir Control ist nicht nur eine Registerliste. Viele Funktionen sind über eigene Fenster erreichbar, damit sich die Wärmepumpe bedienen und untersuchen lässt, **ohne einzelne Registeradressen kennen zu müssen**.

Welche Schaltflächen und Werte tatsächlich funktionieren, hängt von der **gewählten Verbindung** und dem **Firmwarestand** der Wärmepumpe ab. Insbesondere Cloud und direkter Modbus haben nicht immer denselben Funktionsumfang.

## Das Hauptfenster: Livewerte und Register

Im Hauptfenster zeigt FoxAir Control die über die Verbindung empfangenen Informationen an. Dazu gehören beispielsweise:

- Vorlauf-, Rücklauf- und Außentemperaturen
- Kompressorfrequenz, Betriebsart und Status
- Wasserdurchfluss, Drücke und weitere verfügbare Messwerte
- Solltemperaturen, Einstellungen und Diagnoseinformationen

Wenn die Bedeutung eines Registers bekannt ist, erscheint eine **verständliche Beschreibung** mit Einheit und weiteren Hinweisen. Unbekannte Werte können weiterhin als Rohwerte dargestellt werden, statt ihnen eine ungesicherte Bedeutung zu geben.

Praktische Funktionen sind beispielsweise **Suchen und Filtern**, das Lesen bekannter Register und das Hervorheben veränderter Werte. Je nach Datenquelle werden lokale Messwerte und Cloudwerte getrennt berücksichtigt.

![Hauptfenster mit erweiterten Werten](../screenshots/Screenshot%20Fox_main2.png)

## Wärmepumpe steuern

Über einen eigenen Steuerungsdialog können unterstützte Funktionen ausgeführt werden, beispielsweise:

- Wärmepumpe **ein- und ausschalten**
- **Betriebsart** wählen
- wichtige **Temperatur-Sollwerte** einstellen
- aktuellen Betriebszustand und ausgewählte Messwerte ansehen

Bei vorhandener lokaler Modbus-Verbindung nutzt die gemeinsame Steuerung bevorzugt diesen Weg. Ohne lokale Verbindung können bestätigte Funktionen auch über die **WarmLink-Cloud** verfügbar sein.

![Steuerungsdialog](../screenshots/Screenshot%20Fox_control.png)

## Heizkurve und AT-Kompensation

Der Dialog für die Außentemperaturkompensation bietet bei unterstützter Firmware:

- lineare Heizkurve mit **Steigung und Verschiebung**
- **7-Punkt-Heizkurve** mit sieben Außentemperatur-Stützstellen
- grafische Darstellung und berechnete Solltemperatur
- Lesen und Schreiben der zugehörigen Einstellungen

Mit **v0.4.0** wurden insbesondere die Cloud-Funktionen für die 7-Punkt-Kurve erweitert. Die Kurvenwerte können bei entsprechend unterstützter Anlage auch über WarmLink eingelesen und geändert werden.

![Dialog für AT-Kompensation](../screenshots/Screenshot%20Fox_AT.png)

Für die grundsätzliche Funktionsweise siehe [Heizungsregelung und Heizkurve](regelung_heizkurve.md).

## SG Ready und PV-Überschuss

Über den SG-Ready-Dialog lassen sich die verfügbaren Betriebsarten und ihre Einstellungen übersichtlicher bearbeiten.

Bei unterstützten Firmwareständen umfasst das neben den klassischen SG-Ready-Zuständen auch **erweiterte PV- und Remote-Modi**. Die konkreten Optionen unterscheiden sich je nach Firmware.

Seit v0.4.0 sind die zugeordneten SG-Einstellungen auch umfangreich über die **Cloud** les- und schreibbar. Der tatsächliche Status wird dabei separat angezeigt.

Mehr zum Thema: [SG Ready und PV-Überschusssteuerung](sg_ready.md).

## Timer

FoxAir Control besitzt eigene Dialoge für die Zeitsteuerung, unter anderem:

- **Ein-/Ausschaltzeiten** der Wärmepumpe
- **Betriebsart-Timer 1–6**
- **Silentmodus-Timer**

Die Timer lassen sich nicht nur als unübersichtliche Registerwerte, sondern als zusammengehörige Einstellungen ansehen und bearbeiten.

Im Release **v0.4.0** wurden die Cloud-Timer und ihre Bedienung deutlich erweitert. Das Programm lädt unterstützte Werte beim Öffnen und versucht, nur tatsächlich geänderte Einstellungen zu übertragen und anschließend zu überprüfen.

**Hinweis:** Gerade bei neueren Cloud-Schreibfunktionen ist die Unterstützung geräte- und firmwareabhängig. Nach einer Änderung deshalb prüfen, ob die Wärmepumpe den gewünschten Timer auch tatsächlich übernommen hat.

![Timer-Dialog](../screenshots/Screenshot%20Fox_timer.png)

## Parameter ändern und Einstellungen sichern

Viele Einstellungen können über **Parameterdialoge** mit Beschreibungen bearbeitet werden. Die Registerdatenbank hilft dabei, bekannte Werte von noch nicht sicher identifizierten Werten zu unterscheiden.

Vor Änderungen empfiehlt sich die vorhandene **Backup-Funktion**:

1. Parameter der Wärmepumpe einlesen.
2. Einstellungen als Backup sichern.
3. Geplante Werte ändern.
4. Nach der Änderung die tatsächlichen Werte kontrollieren.

Für das Wiederherstellen unterstützt FoxAir Control einen **Vergleich der Werte**, damit nicht blind ein kompletter älterer Stand zurückgeschrieben werden muss.

Anleitung: [Einstellungen vor einem Firmwareupdate sichern](einstellungen_sichern.md).

## WarmLink-Cloud im Hauptfenster

Mit einem vorhandenen WarmLink-Konto kann FoxAir Control Geräte und verfügbare Cloudwerte abrufen. Dazu gehören auch **regelmäßige Aktualisierungen (Polling)**.

Unterstützte Cloudwerte erscheinen im Programm neben den lokalen Daten. Nicht jeder Cloudwert ist einem lokalen Register eindeutig zugeordnet. Wo die Zuordnung unklar ist, sollte man die Daten nicht als identisch interpretieren.

Der Cloud-Dialog bietet außerdem Funktionen zur Geräteauswahl sowie zum Verbinden und Trennen. Zugangsdaten und Tokens werden über die vorgesehene sichere Ablage des Betriebssystems verwaltet.

---

Wer tiefer einsteigen möchte, findet unter [Diagnose und sichere Nutzung](foxair_control_diagnose.md) weitere Werkzeuge. Falls du noch nicht verbunden bist, beginne mit den [Verbindungsarten](verbindung.md).
