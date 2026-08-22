# HowTo: Warmlink-/LTE-Modbus per USB-RS485 parallel mithören

## Zweck

Diese Anleitung beschreibt ausschließlich den **Hardware-Anschluss eines USB-RS485-Adapters** an den Warmlink-/LTE-Modbus der untersuchten FoxAir/PHNIX-Wärmepumpe.

Der Adapter wird parallel auf die vorhandene RS485-Verbindung zwischen Wärmepumpen-Mainboard und Warmlink-/LTE-Modem (DTU) aufgelegt. Die bestehende Verbindung zum LTE-Modem bleibt dabei unverändert bestehen.

> **Hinweis zum aktiven Betrieb:** Für einen reinen Mitschnitt sollte der zusätzliche USB-RS485-Adapter möglichst nur mithören. Über denselben Adapter sind jedoch auch aktive Modbus-Abfragen und Schreibzugriffe möglich und wurden im Projekt bereits erfolgreich verwendet. Da das LTE-Modem gleichzeitig weiter kommuniziert, befinden sich dabei mehrere aktive Teilnehmer auf demselben RS485-Bus. Das kann praktisch funktionieren, es gibt dabei aber keine koordinierte Bus-Arbitrierung; zeitgleiche Telegramme können sich daher gegenseitig stören. Aktive Zugriffe sollten deshalb bewusst und nicht unnötig häufig erfolgen.

Die Bedienung und Konfiguration des Langzeit-Captures in FoxAir Control ist separat in [warmlink_raw_capture.md](warmlink_raw_capture.md) beschrieben.

## Schnittstellenparameter

Für den Warmlink-/LTE-Modbus der hier untersuchten FoxAir/PHNIX-Wärmepumpe werden folgende Parameter verwendet:

- **Baudrate:** 9600 Baud
- **Datenbits:** 8
- **Parität:** None
- **Stopbits:** 1
- Kurzform: **9600 8N1**

Nicht mit dem Display-/DWIN-Bus verwechseln: Der Displaybus arbeitet bei der untersuchten Anlage mit **4800 Baud**.

## Identifizierte Warmlink-/LTE-DTU-Hardware

Bei der untersuchten Anlage wurde das Warmlink-/LTE-DTU geöffnet und die sichtbaren Hardwarebezeichnungen dokumentiert. Die folgenden Angaben beziehen sich auf genau dieses Gerät und müssen nicht für andere PHNIX-/FoxAir-DTU-Versionen gelten.

### Trägerplatine

Auf der Leiterplatte ist direkt aufgedruckt:

- **Name:** `MXL290`
- **Board-Datum:** `2021-05-25`
- **B/T:** `1.6 mm`
- **C/T:** `1 oz`

Eine eindeutige öffentliche technische Dokumentation zur Bezeichnung `MXL290` konnte bisher nicht gefunden werden. Es handelt sich daher sehr wahrscheinlich um eine kundenspezifische DTU-/Trägerplatine.

Eindeutige gerätespezifische Serien-/IMEI-Nummern werden hier bewusst nicht vollständig veröffentlicht.

### Mobilfunkmodul

Auf dem abgeschirmten Mobilfunkmodul befindet sich unter anderem die Kennzeichnung:

```text
Z30AN S2-107EQ
```

Die vollständige SIMCom-PN **`S2-107EQ-Z30AN`** wird in öffentlich verfügbaren Firmware-/Hardwareunterlagen dem **SIMCom SIM7600E-H** zugeordnet. Damit ist die Identifikation als SIM7600E-H sehr wahrscheinlich.

Quellen:

- SIMCom Produktseite SIM7600X-H / SIM7600E-H: https://www.simcom.com/product/SIM7600X-H.html
- Dokumentierte PN-Zuordnung `S2-107EQ-Z30AN` zum SIM7600E-H: https://github.com/Xinyuan-LilyGO/LilyGo-Modem-Series/blob/main/docs/en/esp32/sim7600-esp32/upgrade/sim7600_upgrade.md

Der SIM7600E-H ist ein LTE-Cat.-4-Modul und stellt laut SIMCom unter anderem **USB, UART, GNSS und AT-Command-Schnittstellen** bereit. SIMCom nennt außerdem FOTA als unterstützte Softwarefunktion.

> **Wichtig:** Die Identifikation basiert derzeit auf der sichtbaren PN-Zuordnung. Eine zusätzliche Bestätigung direkt über das Modem, z. B. mit `AT+SIMCOMATI`, `AT+CGMM` oder `AT+CGMR`, steht noch aus.

### USB-Anschluss auf der DTU-Platine

Auf der MXL290-Platine ist ein **Micro-USB-Anschluss** vorhanden und eindeutig mit `USB` beschriftet.

Da das vermutete SIM7600E-H selbst eine USB-Schnittstelle besitzt, ist dieser Anschluss für Diagnosezwecke besonders interessant. **Noch nicht bestätigt ist jedoch, ob der Micro-USB-Port der MXL290-Platine direkt auf die USB-Leitungen des SIM7600E-H geführt ist oder ob zusätzliche Logik dazwischenliegt.**

Ein sinnvoller erster Test ist deshalb ausschließlich die USB-Erkennung am PC, ohne Konfigurationsänderungen oder Firmwarezugriffe.

Bei einem direkt angebundenen SIM7600E-H können unter Windows nach Installation der passenden SIMCom-Treiber mehrere USB-Interfaces erscheinen, typischerweise beispielsweise:

- `SimTech HS-USB AT Port 9001`
- `SimTech HS-USB Diagnostics 9001`
- `SimTech HS-USB NMEA 9001`
- ggf. weitere USB-Interfaces

Ein vergleichbares USB-Interface-Layout ist z. B. in der SIM7600E-H-Dokumentation von Waveshare beschrieben:

https://www.waveshare.com/wiki/SIM7600E-H_4G_HAT

### Sicherer erster USB-Test

Solange die Verschaltung der MXL290-Platine nicht vollständig bekannt ist, sollte der Test konservativ erfolgen:

1. DTU zunächst normal über die Wärmepumpe versorgen.
2. Vor Verbindung mit dem PC prüfen, ob USB-VBUS auf der DTU-Seite bereits Spannung führt bzw. wie die USB-Versorgung verschaltet ist.
3. Wenn möglich für den ersten Diagnoseversuch ein USB-Datenkabel verwenden, bei dem **VBUS/+5 V nicht verbunden** ist, während D+, D- und GND verbunden bleiben.
4. Windows-Gerätemanager beobachten und neu erscheinende USB-/COM-Geräte dokumentieren.
5. Noch keine Firmwaretools und keine schreibenden/konfigurationsändernden AT-Kommandos verwenden.

Falls ein SIMCom-AT-Port erscheint, sind als erste rein lesende Abfragen sinnvoll:

```text
AT
ATI
AT+SIMCOMATI
AT+CGMI
AT+CGMM
AT+CGMR
AT+CSUB
AT+CSQ
AT+COPS?
AT+CPSI?
AT+CGSN
```

`AT+CGSN` kann eine eindeutige Gerätekennung/IMEI zurückgeben. Solche eindeutigen Kennungen sollten bei öffentlichen Logs oder Screenshots vor Veröffentlichung anonymisiert werden.

### Diagnose- und Firmware-Schnittstellen

Die vorhandene USB-Schnittstelle ist für das Reverse Engineering interessant, weil der SIM7600-H laut Hersteller USB- und AT-Schnittstellen sowie FOTA unterstützt. Außerdem ist die konkrete PN `S2-107EQ-Z30AN` in öffentlich verfügbaren SIM7600E-H-Firmwareunterlagen ausdrücklich aufgeführt.

Das bedeutet **nicht**, dass über diesen USB-Port automatisch die Firmware des Wärmepumpen-Mainboards zugänglich ist. Zu unterscheiden sind mindestens:

- Firmware/Diagnose des **SIM7600E-H-Mobilfunkmoduls**,
- mögliche Firmware/Logik der **MXL290-DTU-Platine**,
- Firmware des eigentlichen **Wärmepumpen-Mainboards**.

Für dieses Projekt ist insbesondere interessant, ob über USB zusätzliche Informationen über Cloud-Verbindung, DTU-Software, Updateablauf oder die Kommunikation zum Wärmepumpen-Mainboard sichtbar werden.

> **Keine SIM7600-Firmware auf Verdacht flashen.** In den öffentlich verfügbaren Upgradehinweisen wird ausdrücklich darauf hingewiesen, dass die Firmware zur exakten PN des Moduls passen muss. Ziel ist zunächst ausschließlich passive Identifikation und Diagnose.

### Sichtbare TTL-Kennzeichnung

In der Nähe des Kabelsteckers ist auf der Platine außerdem die Beschriftung **`TTL`** sichtbar. Daneben befinden sich mehrere als `ESD` sowie `R27`/`R28`/`R29` bezeichnete Schutz-/Serienbauteile.

Die Beschriftung ist ein deutlicher Hinweis auf eine TTL-/UART-bezogene Schnittstelle bzw. Signalgruppe. Aus dem Foto allein lassen sich jedoch weder das genaue Pinout noch die Signalpegel sicher ableiten.

Vor einem Anschluss eines USB-TTL-Adapters müssen daher zunächst **GND, Versorgung und Signalpegel gemessen** bzw. die Leiterbahnen nachvollzogen werden. Insbesondere darf eine Versorgungsspannung nicht mit einem TTL-Signal verwechselt werden.

## Verwendeter USB-RS485-Adapter

Für den beschriebenen Aufbau wurde ein **Jhoinrch RH-06 LK3 USB-zu-RS485/RS422-Wandler** verwendet. Der Adapter basiert auf einem FT232RNL-USB-Seriell-Chip und ist für RS485/RS422 ausgelegt.

Amazon/ASIN **B0FX2PTXQ7**:

https://www.amazon.de/dp/B0FX2PTXQ7

Andere USB-RS485-Adapter können ebenfalls funktionieren. Für Diagnosearbeiten ist ein Adapter mit sauberem RS485-Transceiver und möglichst guter Schutzbeschaltung zu bevorzugen.

> **120-Ohm-Jumper beachten:** Der gezeigte Adapter besitzt eine zuschaltbare **120-Ω-Terminierung**. Für den hier beschriebenen parallelen Diagnoseabgriff darf keine zusätzliche Terminierung zugeschaltet werden. Falls der Jumper bei `120Ω` gesteckt ist, diesen für den Mitschnitt entfernen.

## Anschluss am Mainboard

Die beiden RS485-Leitungen des USB-RS485-Adapters werden **parallel** zu den bereits vorhandenen Leitungen des Warmlink-/LTE-Modems in die entsprechenden Klemmen am Mainboard gesteckt.

Es wird also nichts aufgetrennt:

```text
Mainboard RS485 A  ───── LTE-Modem / DTU A
        │
        └────────── USB-RS485 A

Mainboard RS485 B  ───── LTE-Modem / DTU B
        │
        └────────── USB-RS485 B
```

### Position am Mainboard

Auf dem folgenden Foto sind die beiden Klemmen rechts unten markiert, an denen der Warmlink-/LTE-Modbus zum DTU angeschlossen ist. Der USB-RS485-Adapter wird an genau diesen beiden Klemmen **parallel** zu den vorhandenen Leitungen aufgelegt.

![Warmlink-/LTE-Modbus Klemmen am Mainboard](images/warmlink_modbus/mainboard_lte_modbus_klemmen.jpg)

*Mainboard der untersuchten GL9-Anlage. Markiert sind die beiden RS485-Klemmen zum Warmlink-/LTE-DTU.*

### Position im Schaltplan

Auch im Schaltplan ist der Anschluss rechts unten beim **DTU** zu finden. Markiert sind die Klemmen **485-A** und **485-B**.

![Warmlink-/LTE-Modbus Klemmen im Schaltplan](images/warmlink_modbus/schaltplan_lte_modbus_klemmen.jpg)

*Schaltplan GL-9-1, Code 20220809-0002. Der Warmlink-/LTE-DTU ist rechts unten über 485-A/485-B angebunden.*

Die Klemmen für **A** und **B** sind damit sowohl im Schaltplan als auch am Anschlussbereich der Anlage nachvollziehbar.

Falls trotz korrekter Schnittstellenparameter keinerlei verwertbare Telegramme empfangen werden, können **A und B vertauscht** sein. In diesem Fall die beiden RS485-Leitungen am USB-Adapter tauschen. Ein Vertauschen von A/B führt normalerweise lediglich dazu, dass keine gültigen Daten empfangen werden.

## Schritt für Schritt

1. Wärmepumpe vollständig spannungsfrei schalten.
2. Vorhandene RS485-Leitungen identifizieren, die vom Mainboard zum Warmlink-/LTE-Modem bzw. DTU führen.
3. Im Schaltplan bzw. an den Klemmen **485-A** und **485-B** prüfen.
4. Leitung **A** des USB-RS485-Adapters parallel zur vorhandenen A-Leitung anklemmen.
5. Leitung **B** des USB-RS485-Adapters parallel zur vorhandenen B-Leitung anklemmen.
6. Am USB-RS485-Adapter sicherstellen, dass **keine zusätzliche 120-Ω-Terminierung** aktiviert ist.
7. Darauf achten, dass keine Litzen herausstehen und kein Kurzschluss zu benachbarten Klemmen entstehen kann.
8. USB-RS485-Adapter mit dem PC bzw. Capture-Rechner verbinden.
9. Wärmepumpe wieder einschalten.
10. Am PC prüfen, ob der USB-RS485-Adapter als serielle Schnittstelle bzw. COM-Port erkannt wird.
11. Für den Warmlink-/LTE-Bus **9600 Baud, 8N1** verwenden.
12. Falls keine plausiblen Daten empfangen werden, zunächst A/B am USB-RS485-Adapter tauschen und erneut prüfen.

## Praxis: längere Leitung bis zum Capture-Rechner

Der parallele Abgriff wurde an der untersuchten Anlage bereits erfolgreich mit einem **ca. 30 Meter langen Patchkabel bis in den Keller** getestet. Der USB-RS485-Adapter bzw. der Capture-Rechner muss damit nicht zwingend direkt neben der Wärmepumpe stehen.

Für eine solche Verlängerung empfiehlt sich:

- **A und B über ein gemeinsames verdrilltes Adernpaar** des Netzwerkkabels führen.
- Die beiden RS485-Signale nicht auf Adern unterschiedlicher Paare verteilen.
- Keine Versorgungsspannung der Wärmepumpe über das Patchkabel zum USB-Adapter führen.
- Die zusätzliche **120-Ω-Terminierung am USB-RS485-Adapter deaktiviert lassen**, wie beim kurzen Parallelabgriff.
- Bei Empfangsproblemen zuerst A/B, Steckverbindungen, Leitungslänge und eventuelle zusätzliche Terminierungen prüfen.

> **Praxiserfahrung, keine allgemeine Garantie:** Die ca. 30 m lange Verbindung funktioniert an der hier untersuchten Anlage zuverlässig. Ob dieselbe Leitungslänge bei einer anderen Wärmepumpe, einem anderen RS485-Adapter, anderer Leitungsführung oder stärkerer elektrischer Störumgebung ebenfalls problemlos funktioniert, kann nicht garantiert werden.

RS485 ist grundsätzlich für deutlich größere Leitungslängen ausgelegt. Bei einem zusätzlichen parallelen Diagnoseabgriff spielt jedoch auch die konkrete Bus-Topologie eine Rolle. Eine kurze Stichleitung ist elektrisch günstiger; die hier getesteten ca. 30 m zeigen lediglich, dass eine längere Verbindung in diesem konkreten Aufbau praktisch funktioniert.

## Wichtige Hinweise

### Nur die RS485-Signale anschließen

Für das reine Mithören werden die beiden RS485-Datenleitungen **A und B** benötigt. Versorgungsspannungen des Mainboards oder des LTE-Modems dürfen nicht mit dem USB-Adapter verbunden werden, sofern dies nicht für einen konkret verwendeten Adapter ausdrücklich erforderlich und elektrisch geprüft ist.

Beim verwendeten USB-Adapter erfolgt die Versorgung über USB. Eine 12-V- oder sonstige Versorgung von der Wärmepumpe wird **nicht** benötigt.

### Aktive Modbus-Zugriffe

Für einen rein passiven Mitschnitt sind keine eigenen Modbus-Abfragen nötig. Der parallel angeschlossene USB-RS485-Adapter kann aber auch aktiv zum Lesen oder Schreiben von Registern verwendet werden; dies wurde an der untersuchten Anlage bereits erfolgreich getestet.

Dabei bleibt das LTE-Modem weiterhin aktiv am Bus. RS485 verhindert physikalisch nicht, dass mehrere Teilnehmer senden, bietet in diesem Aufbau aber keine automatische Kollisionsvermeidung zwischen zwei unabhängig arbeitenden Mastern. Einzelne aktive Zugriffe können daher funktionieren, während unnötig häufiges Polling oder mehrere gleichzeitig aktive Diagnoseprogramme die Wahrscheinlichkeit von Telegrammkollisionen erhöhen.

### Keine zusätzliche Terminierung

Der USB-RS485-Adapter wird als zusätzlicher Teilnehmer parallel auf den bestehenden Bus gelegt. Am Adapter sollte für diesen Aufbau **kein zusätzlicher 120-Ohm-Abschlusswiderstand** aktiviert werden, da eine zusätzliche Terminierung den bestehenden RS485-Bus unnötig belasten kann.

Beim gezeigten Jhoinrch-Adapter ist deshalb besonders der mit **`120Ω`** beschriftete Jumper zu kontrollieren.

### Galvanische Trennung

Eine galvanische Trennung ist für Diagnosearbeiten grundsätzlich vorteilhaft. Der konkret verwendete Adapter sollte nicht allein aufgrund der Bauform als galvanisch getrennt angenommen werden. Wer eine galvanische Trennung benötigt, sollte dies anhand der technischen Daten des jeweiligen Adapters ausdrücklich prüfen.

### Arbeiten im Gerät

Im Gehäuse der Wärmepumpe befinden sich neben der Kleinspannungs-/Kommunikationselektronik auch netzspannungsführende Komponenten.

- Vor dem Anklemmen die Anlage vollständig spannungsfrei schalten.
- Gegen Wiedereinschalten sichern.
- Spannungsfreiheit prüfen.
- Nur an eindeutig identifizierten Kommunikationsklemmen arbeiten.
- Keine unbekannten Klemmen probeweise mit USB, GND oder Versorgungsspannung verbinden.

Wer die Klemmen oder deren Funktion nicht eindeutig identifizieren kann, sollte den Anschluss nicht auf Verdacht durchführen.

## Fehlersuche

### Keine Daten

- Wird der USB-RS485-Adapter vom PC als COM-/Seriellschnittstelle erkannt?
- **9600 Baud / 8N1** eingestellt?
- Wirklich die **485-A / 485-B**-Klemmen des DTU verwendet?
- A und B korrekt angeschlossen?
- A/B testweise vertauschen.
- LTE-Modem/DTU und Wärmepumpe eingeschaltet und kommunizieren tatsächlich?
- Ist am USB-RS485-Adapter versehentlich die 120-Ω-Terminierung aktiviert?
- Bei langer Leitung: Steckverbindungen und verwendetes Adernpaar prüfen.

### Daten vorhanden, aber nur unbrauchbare Zeichen / ungültige Frames

- Baudrate und 8N1 nochmals prüfen.
- Sicherstellen, dass wirklich der LTE-/Warmlink-Bus und nicht der Display-/DWIN-Bus abgegriffen wurde.
- A/B prüfen.
- Bei längerer Leitung prüfen, ob A und B tatsächlich auf demselben verdrillten Adernpaar liegen.

### Kommunikation der Wärmepumpe wird nach Anschluss gestört

USB-RS485-Adapter sofort wieder abklemmen und prüfen:

- Ist die **120-Ω-Terminierung** am Adapter aktiviert?
- Sendet die verwendete Software sehr häufig oder gleichzeitig mit einem weiteren Diagnoseprogramm aktiv Daten?
- Wurde versehentlich eine zusätzliche Leitung wie Versorgungsspannung angeschlossen?
- Ist der Adapter für echtes RS485 geeignet und elektrisch unauffällig?
- Bei langer Leitung: verbessert sich das Verhalten mit einer kürzeren Testleitung?

## Software / Langzeit-Capture

Diese Datei beschreibt bewusst nur den **physischen Anschluss und die Verwendung des USB-RS485-Adapters am Warmlink-/LTE-Bus**.

Die Bedienung des Warmlink-Langzeit-Captures, die passiven Capture-Modi, Dateiformate, Segmentierung und die Forschungsfunktion zum Mitschneiden eines gezielt ausgelösten Updatevorgangs sind separat beschrieben:

**[Warmlink RAW Langzeit-Capture](warmlink_raw_capture.md)**

## Hinweis

Diese Dokumentation basiert auf der untersuchten FoxAir/PHNIX-GL9-Konfiguration und ist keine offizielle Herstelleranleitung. Klemmenbezeichnungen und Hardwarevarianten können bei anderen Mainboards oder Geräteversionen abweichen.
