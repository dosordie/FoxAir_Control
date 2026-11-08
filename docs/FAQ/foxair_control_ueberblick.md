# FoxAir Control – Überblick und Download

**FoxAir Control** ist ein kostenlos verfügbares, quelloffenes Programm, mit dem sich viele FoxAir-/PHNIX-Wärmepumpen **auslesen, überwachen, diagnostizieren und – soweit unterstützt – einstellen** lassen.

Das Programm richtet sich sowohl an Anwender, die einfach Temperaturen und Betriebszustände ansehen möchten, als auch an technisch Interessierte, die Parameter, Kommunikation und Regelverhalten genauer untersuchen wollen.

> **Wichtig:** FoxAir Control ist ein **privates Community-Projekt**, **kein offizielles Programm von FoxAir oder PHNIX**. Es ist weder vom Hersteller entwickelt noch freigegeben. Die Nutzung, besonders das Ändern von Einstellungen, erfolgt auf eigene Verantwortung.

![Hauptfenster von FoxAir Control](../screenshots/Screenshot%20Fox_main.png)

## Was kann ich damit machen?

Einige Beispiele:

- **Livewerte ansehen:** Temperaturen, Kompressorfrequenz, Wasserdurchfluss, Betriebszustand und viele weitere verfügbare Daten.
- **Parameter verstehen:** Register werden nach Möglichkeit mit Namen, Einheiten, Wertebereichen und zusätzlichen Erklärungen angezeigt – statt nur mit einer Nummer.
- **Wärmepumpe bedienen:** Unter anderem Ein/Aus, Betriebsart und Solltemperaturen, abhängig von Verbindung und Firmware.
- **Heizkurve und SG Ready einstellen:** Mit eigenen übersichtlichen Dialogen statt einzelner Registereingaben.
- **Timer bearbeiten:** Ein-/Aus-Timer, Betriebsart-Timer und Silentmodus.
- **Einstellungen sichern:** Parameter-Backups erstellen, vergleichen und bei Bedarf gezielt wiederherstellen.
- **Fehler und Zustände untersuchen:** Zum Beispiel über die Fehler-, Kontakt- und Lastausgangsanzeige.

Welche Funktion verfügbar ist, hängt unter anderem von der **Mainboard-Firmware**, dem verwendeten **Kommunikationsweg** und den tatsächlich bekannten Registerzuordnungen ab.

Eine ausführlichere Übersicht findest du unter [Funktionen und Bedienung](foxair_control_funktionen.md).

## Brauche ich dafür eine besondere Hardware?

**Nicht zwingend.** FoxAir Control unterstützt sowohl direkte Verbindungen zur Wärmepumpe als auch die **WarmLink-Cloud**.

Für die Cloud-Verbindung ist normalerweise keine zusätzliche Verkabelung nötig. Du benötigst allerdings einen funktionierenden WarmLink-Zugang und ein Gerät, das dort deinem Konto zugeordnet ist.

Für den **direkten Modbus-Zugriff** wird eine geeignete Verbindung zur RS485-Schnittstelle benötigt, etwa ein USB-RS485-Adapter oder ein bereits vorhandenes serielles Netzwerk-Gateway.

Die Unterschiede erklärt der Artikel [Verbindungsarten: Standard-Modbus, Display, LTE und Cloud](verbindung.md).

## Download und Installation unter Windows

Am einfachsten verwendest du eine der fertigen Windows-Versionen:

**[Aktuelle Version über GitHub Releases herunterladen](https://github.com/dosordie/FoxAir_Control/releases/latest)**

Dort gibt es je nach Release beispielsweise:

| Variante | Für wen geeignet? |
| --- | --- |
| **Windows-Setup (.exe)** | Für Anwender, die das Programm normal installieren möchten. |
| **Windows Portable (.zip)** | Für Anwender, die es ohne klassische Installation aus einem Ordner starten möchten. |

Bei der portablen Version **immer das vollständige ZIP entpacken**. Die ausführbare Datei ist nicht als alleinstehende EXE gedacht.

Die fertigen Windows-Pakete benötigen keine separate Python-Installation. Wer das Projekt selbst aus dem Quellcode starten möchte, findet die dafür nötigen Hinweise im [GitHub-Repository](https://github.com/dosordie/FoxAir_Control).

## Ist FoxAir Control kostenlos?

Ja. Das Projekt wird öffentlich auf GitHub bereitgestellt. Es gibt keinen kostenpflichtigen Cloud-Dienst von FoxAir Control selbst.

**Wichtig:** Wenn du über WarmLink auf die Wärmepumpe zugreifst, hängt diese Verbindung weiterhin von der vorhandenen WarmLink-/PHNIX-Infrastruktur ab. Deren Zugangs- und Verfügbarkeitsbedingungen sind nicht Teil von FoxAir Control.

## Wo kann ich Fehler melden oder Änderungen verfolgen?

- [Projekt auf GitHub](https://github.com/dosordie/FoxAir_Control)
- [Aktuelle Releases und Änderungen](https://github.com/dosordie/FoxAir_Control/releases)
- [Fehler und Vorschläge (Issues)](https://github.com/dosordie/FoxAir_Control/issues)

FoxAir Control wird fortlaufend weiterentwickelt. Deshalb kann eine neuere Programmversion zusätzliche Funktionen oder andere Menüs besitzen als eine ältere Ausgabe.

---

**Tipp zum Einstieg:** Lies zuerst die [Verbindungsarten](verbindung.md), beobachte einige Livewerte und erstelle vor schreibenden Änderungen ein [Backup deiner Einstellungen](einstellungen_sichern.md).
