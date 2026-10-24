# FoxAir Control – Diagnose, Sicherheit und Grenzen

FoxAir Control enthält neben den normalen Bedienfunktionen auch Werkzeuge, mit denen sich **Fehler, ungewöhnliche Betriebszustände und die Kommunikation der Wärmepumpe** untersuchen lassen.

Viele davon sind für die reine Beobachtung gedacht. Einige Expertenfunktionen können dagegen aktiv in die Steuerung eingreifen. Deshalb ist es wichtig, die Unterschiede zu kennen.

## Fehler und Zustände verständlich anzeigen

In der Wärmepumpe werden zahlreiche Zustände als Zahlen oder einzelne Bits gespeichert. FoxAir Control kann einige davon in übersichtlichen Dialogen aufbereiten.

Dazu gehören unter anderem:

- **Störungsanzeige:** aktuelle Fehler- und Störungsinformationen
- **Kontaktdecoder:** Zustände von Eingängen wie Schaltern und Freigaben
- **Lastausgangsdecoder:** aktuelle Zustände bekannter Ausgänge
- **System-/I/O-Status:** zusätzliche Betriebs- und Schutzinformationen

Bei der Cloud-Anbindung aus **v0.4.0** können mehrere dieser Anzeigen ihre Werte auch über WarmLink laden.

**Wichtig:** Nicht jedes Statusbit ist vollständig geklärt. Das Programm unterscheidet deshalb zwischen bekannten Funktionen und noch offenen Interpretationen. Eine angezeigte Bitänderung beweist für sich allein nicht die Ursache einer Störung.

Weitere Hinweise: [Fehler und Betriebszustände anzeigen](fehler_und_status.md).

## Geräte-Info und Firmwarestände

Ein eigener **Geräte-Info-Dialog** versucht, die verfügbaren Informationen über Mainboard, Softwarestand und Kommunikationsmodul auszulesen.

Das hilft zum Beispiel, wenn du wissen möchtest, **welche Mainboard-Firmware** tatsächlich installiert ist.

Dabei ist zu beachten:

- Die Version des **Mainboards** ist nicht dieselbe wie die des **Displays**.
- Ein Kommunikationsmodul besitzt ebenfalls eigene Kennungen und gegebenenfalls eine eigene Firmware.
- Nicht jede Kennung ist die Seriennummer vom Typenschild.

Je nach Gerät und Verbindung sind nicht alle Angaben vorhanden.

Mehr dazu: [Firmware-Versionen und Updates](firmware.md).

## Kommunikationsmitschnitt und Langzeitaufzeichnung

Für technisch Interessierte bietet FoxAir Control Möglichkeiten, den Datenverkehr auf dem **Warmlink-/LTE-Bus** aufzuzeichnen.

Der **RAW-Langzeit-Capture** speichert dabei empfangene beziehungsweise selbst gesendete Daten sowie ergänzende Diagnoseereignisse.

Es gibt einen normalen Aufzeichnungsbetrieb und einen besonders vorsichtigen **Firmware-Capture-Modus**:

- **Normaler Capture:** Datenverkehr beobachten; reguläre Kommunikationsfunktionen können weiter genutzt werden.
- **Firmware-Capture:** Streng passiver Mitschnitt, bei dem FoxAir Control selbst keine Modbus-Telegramme auf diesen Bus senden soll.

Der passive Modus ist zum Beispiel dafür gedacht, mögliche Firmwareübertragungen zu untersuchen, **ohne selbst ein Update auszulösen**.

Das ist ein Diagnosewerkzeug für Fortgeschrittene und für den normalen Heizungsbetrieb nicht notwendig.

## Ist FoxAir Control ein Firmware-Updater?

**Nein.** Der Warmlink-Capture kann zwar Hinweise auf Firmwareübertragungen aufzeichnen, er **schreibt aber keine Firmware** und spielt keine aufgezeichneten Daten zurück.

Für Mainboard-Firmwareupdates existiert das **separate Projekt [FoxAir Updater](https://github.com/dosordie/FoxAir_updater)**.

Firmwareupdates und Änderungen an Serviceparametern sollten nicht mit normalen Diagnosefunktionen verwechselt werden.

## Vorsicht beim Schreiben von Einstellungen

Es gibt einen wichtigen Unterschied:

| Aktion | Was passiert? |
| --- | --- |
| **Werte lesen** | Der aktuelle Zustand wird abgefragt, ohne gezielt eine Einstellung zu ändern. Je nach Bus kann bereits die Abfrage selbst Kommunikation auslösen. |
| **Parameter schreiben** | Eine Einstellung in der Wärmepumpe wird verändert. |
| **Backup wiederherstellen** | Mehrere Einstellungen können verändert werden, teilweise mit unmittelbarer Wirkung. |
| **Passiver Busmitschnitt** | FoxAir Control zeichnet Verkehr auf, ohne selbst neue Busabfragen zu senden. |

**Vor Änderungen an Betriebs- oder Serviceparametern immer ein Backup anlegen.** Nicht wahllos Register beschreiben, nur weil ein Schreibfeld angeboten wird.

Besonders wichtig:

- Manche Parameter unterscheiden sich **zwischen Firmwareversionen**.
- Nicht alle Registerbeschreibungen sind endgültig bestätigt.
- Mindestdurchfluss, Kompressorgrenzen und Schutzfunktionen dürfen nicht ohne fundierte Prüfung verändert werden.
- Ein erfolgreich gesendeter Schreibbefehl bedeutet nicht in jedem Fall, dass die Wärmepumpe die gewünschte Änderung tatsächlich dauerhaft übernommen hat.

## Besonderheiten bei Cloud und mehreren Bussen

Eine aktive Cloud-Verbindung ist nicht dasselbe wie ein direkter Mainboard-Zugriff. Es kann Unterschiede bei **Aktualität, Schreibbarkeit und verfügbaren Daten** geben.

FoxAir Control bevorzugt bei einigen gemeinsamen Bedienfunktionen eine aktive lokale Verbindung. Die Cloud kann eine Alternative sein, wenn kein lokaler Zugriff vorhanden ist.

Beim **Warmlink-/LTE-RS485-Bus** kommuniziert normalerweise bereits das LTE-Modul. Zusätzliche aktive Modbus-Abfragen können mit dessen Telegrammen kollidieren. Bei einer reinen Diagnose deshalb nach Möglichkeit mit Bedacht oder passiv arbeiten.

Auch eine unterbrochene Cloud-Verbindung bedeutet **nicht**, dass die Wärmepumpe ihren normalen Heizbetrieb einstellt.

## Welche Daten sollte ich nicht öffentlich teilen?

Logdateien, Rohmitschnitte und Screenshots können vertrauliche Informationen enthalten, beispielsweise:

- Gerätekennungen, Seriennummern oder ProductKeys
- Cloud-Gerätecodes und Kennungen des Kommunikationsmoduls
- Netzwerkadressen und Verbindungsdetails
- gegebenenfalls Benutzer- oder Zugangsinformationen in Diagnoseausgaben

Diese Angaben vor dem Teilen im Forum oder in einem GitHub-Issue prüfen und gegebenenfalls unkenntlich machen. **Keine Passwörter, Tokens oder vollständigen privaten Mitschnitte öffentlich hochladen.**

## Wie kann ich bei Problemen helfen?

Hilfreich für eine Fehlermeldung sind:

1. **FoxAir-Control-Version** (zum Beispiel v0.4.0)
2. **Mainboard- und gegebenenfalls Display-Firmwareversion**
3. verwendete **Verbindungsart** (Standard, Display, Warmlink oder Cloud)
4. eine kurze Beschreibung: **Was wurde erwartet, was ist passiert?**
5. ein geeigneter Screenshot oder bereinigter Logauszug

Fehler und Verbesserungsvorschläge können unter [GitHub Issues](https://github.com/dosordie/FoxAir_Control/issues) gemeldet werden.

---

**FoxAir Control ist und bleibt ein inoffizielles Community-Werkzeug.** Es ersetzt weder die Herstellerdokumentation noch die Prüfung durch eine fachkundige Person bei sicherheitsrelevanten Arbeiten.

Zurück zur [Übersicht](foxair_control_ueberblick.md) · [Verbindungsarten](verbindung.md) · [Funktionen und Bedienung](foxair_control_funktionen.md).
