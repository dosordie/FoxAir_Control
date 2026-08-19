# HowTo: Warmlink-/LTE-Modbus per USB-RS485 parallel mithören

## Zweck

Diese Anleitung beschreibt, wie ein USB-RS485-Adapter parallel auf den Modbus zwischen Wärmepumpen-Mainboard und Warmlink-/LTE-Modem (DTU) aufgelegt wird. Damit kann der vorhandene Datenverkehr mit FoxAir Control mitgeschnitten und analysiert werden, ohne die bestehende Verbindung zum LTE-Modem zu trennen.

> **Wichtig:** Der zusätzliche USB-RS485-Adapter ist beim Mithören nur als Empfänger gedacht. Er darf nicht als zweiter Modbus-Master aktiv Telegramme auf den Bus senden, solange das LTE-Modem angeschlossen ist.

> **Stand der Firmware-Untersuchung:** Der eigentliche Firmware-Datenstrom wurde im Projekt bereits auf dem **Display-Modbus** beobachtet und dieser Übertragungsweg damit bestätigt. Der Warmlink-/LTE-Langzeit-Capture soll deshalb vor allem untersuchen, **welche Auslöser, Handshakes, Steuertelegramme oder Metadaten auf dem Warmlink-/LTE-Bus rund um einen Updatevorgang sichtbar werden** und wie diese zeitlich mit dem bekannten Firmwaretransfer auf dem Display-Modbus zusammenhängen.
>
> Nach bisherigem Kenntnisstand führt FoxAir **keine automatischen Firmwareupdates** durch. Ein Update muss bei **Kensol** beauftragt bzw. angefordert und von dort angestoßen werden. Ohne einen solchen gezielt ausgelösten Updatevorgang ist daher auch bei einem langen Mitschnitt nicht mit einem Firmwaretransfer zu rechnen.
>
> Der Warmlink-Logger bleibt ein Forschungswerkzeug: Es ist nicht garantiert, dass der eigentliche Update-Auslöser auf diesem Bus sichtbar ist oder dass sich aus einem Mitschnitt später ein reproduzierbarer eigener Update-Trigger ableiten lässt.

## Schnittstellenparameter

Für den Warmlink-/LTE-Modbus der hier untersuchten FoxAir/PHNIX-Wärmepumpe werden folgende Parameter verwendet:

- **Baudrate:** 9600 Baud
- **Datenbits:** 8
- **Parität:** None
- **Stopbits:** 1
- Kurzform: **9600 8N1**

Nicht mit dem Display-/DWIN-Bus verwechseln: Der Displaybus arbeitet bei der untersuchten Anlage mit **4800 Baud**.

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

## Schritt für Schritt: Hardware

1. Wärmepumpe vollständig spannungsfrei schalten.
2. Vorhandene RS485-Leitungen identifizieren, die vom Mainboard zum Warmlink-/LTE-Modem bzw. DTU führen.
3. Im Schaltplan bzw. an den Klemmen **485-A** und **485-B** prüfen.
4. Leitung **A** des USB-RS485-Adapters parallel zur vorhandenen A-Leitung anklemmen.
5. Leitung **B** des USB-RS485-Adapters parallel zur vorhandenen B-Leitung anklemmen.
6. Am USB-RS485-Adapter sicherstellen, dass **keine zusätzliche 120-Ω-Terminierung** aktiviert ist.
7. Darauf achten, dass keine Litzen herausstehen und kein Kurzschluss zu benachbarten Klemmen entstehen kann.
8. USB-RS485-Adapter mit dem PC bzw. Capture-System verbinden.
9. Wärmepumpe wieder einschalten.

## FoxAir Control für den USB-RS485-Abgriff einstellen

Im aktuellen Programm erfolgt die Konfiguration unter **Programm-Einstellungen → Verbindung**:

1. **Kommunikationsart:** `Modbus Warmlink LTE`
2. **Transport:** `Serial / COM-Port`
3. **COM-Port:** den vom USB-RS485-Adapter verwendeten Port auswählen/eintragen, z. B. `COM3`
4. **Baudrate:** `9600`
5. **Parität:** `None / N`
6. **Datenbits:** `8`
7. **Stopbits:** `1`

Die Warmlink-Vorgaben entsprechen damit **9600 8N1**.

Bei aktiver Verbindung sind die Kommunikationsparameter im Einstellfenster gesperrt. Falls Kommunikationsart, Transport oder COM-Port geändert werden müssen, zuerst die bestehende Verbindung trennen.

## Empfohlen: streng passiv mit dem Langzeit-Capture mithören

Für den hier beschriebenen **parallelen Abgriff bei weiterhin angeschlossenem LTE-Modem** sollte in FoxAir Control der Modus **`Firmware-Langzeit-Capture (streng passiv)`** verwendet werden.

Der normale Modus **`Normaler Langzeit-Capture`** zeichnet zwar ebenfalls Daten auf, lässt aber die normalen Lese- und Schreibfunktionen von FoxAir Control weiterhin zu. Damit könnte FoxAir Control selbst Telegramme senden und wäre auf dem bereits vom LTE-Modem benutzten Bus nicht mehr nur passiver Zuhörer.

### Firmware-Langzeit-Capture starten

1. Im Hauptfenster auf **`Langzeit-Capture ...`** klicken.
2. Als Modus **`Firmware-Langzeit-Capture (streng passiv)`** auswählen.
3. Capture-Verzeichnis kontrollieren oder über **`Auswählen ...`** festlegen.
4. Für eine spätere Analyse mindestens **`RX aufzeichnen`** und **`Events/Index schreiben`** aktiviert lassen.
5. `TX aufzeichnen` kann aktiviert bleiben. Im streng passiven Modus sollten durch FoxAir Control **0 TX-Bytes** entstehen; der Live-Status zeigt dies zusätzlich an.
6. Auf **`PASSIV verbinden & Firmware-Capture starten`** klicken.

Der Capture kann nur gestartet werden, wenn die Kommunikationsart **`Modbus Warmlink LTE`** ausgewählt ist. Bei einem anderen Backend zeigt das Capture-Fenster einen Hinweis und deaktiviert den Start-Button.

### Gezielter Mitschnitt eines Firmwareupdates

Da der eigentliche Firmwaretransfer bereits auf dem **Display-Modbus** bestätigt wurde und Updates nach bisherigem Kenntnisstand nur nach Beauftragung bei **Kensol** angestoßen werden, ist für einen aussagekräftigen Forschungs-Mitschnitt folgendes Vorgehen sinnvoll:

1. Warmlink-Capture **vor** der Update-Anforderung starten und streng passiv laufen lassen.
2. Wenn möglich parallel auch den **Display-Modbus** mitschneiden, um Steuerverkehr und Firmwaretransfer zeitlich miteinander vergleichen zu können.
3. Erst danach das Firmwareupdate bei **Kensol** beauftragen bzw. anstoßen lassen.
4. Capture während des gesamten Updatevorgangs weiterlaufen lassen.
5. Zeitpunkt der Beauftragung, Beginn des sichtbaren Display-Firmwaretransfers und eine eventuelle Änderung von Register 2104 möglichst genau notieren.

Ein langer Warmlink-Capture ohne beauftragtes Update liefert zwar weiterhin normale Betriebsdaten, kann aber naturgemäß keinen Update-Auslöser zeigen, wenn gar kein Update angestoßen wurde.

### Woran erkennt man den passiven Betrieb?

Im Fenster **Warmlink Langzeit-Capture** werden unter anderem angezeigt:

- Warmlink-Verbindung
- Capture aktiv/inaktiv
- Modus
- **TX-Sperre**
- Energiespar-Sperre
- aktuelles Segment
- RX-Bytes
- **TX durch FoxAir Control**
- letzter RX/TX-Zeitpunkt
- Drops
- Anomalien
- Fehler

Im Firmware-Modus sollte insbesondere stehen:

- **Firmware-Capture AKTIV – STRENG PASSIV**
- **TX-SPERRE AKTIV – streng passiv**
- **TX durch FoxAir Control: 0 B ✓**

Auch der Button im Hauptfenster wechselt bei aktivem Firmware-Capture auf **`● Firmware-Capture AKTIV`**.

Der Firmware-Modus sperrt innerhalb von FoxAir Control eigene Sendungen bereits auf der Worker-/TX-Ebene. Zusätzlich werden unter anderem Auto-Polling, Init-Lesevorgänge und aktive Warmlink-Diagnose gestoppt bzw. verhindert. Damit ist dieser Modus für den parallelen Mitschnitt wesentlich geeigneter als der normale Langzeit-Capture.

> Die TX-Sperre gilt für FoxAir Control. Andere Programme oder Geräte am gleichen RS485-Bus können selbstverständlich weiterhin senden.

### Energiesparmodus

Beim Firmware-Capture wird die Energiespar-Sperre automatisch aktiviert, damit Windows den Rechner während eines langen Mitschnitts möglichst nicht in Standby schickt. Im normalen Langzeit-Capture ist diese Option separat einstellbar.

### Capture beenden

Im Capture-Fenster **`Capture stoppen`** verwenden. Wird die Warmlink-Verbindung getrennt oder geht sie verloren, wird der aktuelle Capture ebenfalls beendet.

Weitere Details zu Segmenten, Dateiformaten und Firmware-Erkennung stehen in [warmlink_raw_capture.md](warmlink_raw_capture.md).

## Wichtige Hinweise

### Nur die RS485-Signale anschließen

Für das reine Mithören werden die beiden RS485-Datenleitungen **A und B** benötigt. Versorgungsspannungen des Mainboards oder des LTE-Modems dürfen nicht mit dem USB-Adapter verbunden werden, sofern dies nicht für einen konkret verwendeten Adapter ausdrücklich erforderlich und elektrisch geprüft ist.

Beim verwendeten USB-Adapter erfolgt die Versorgung über USB. Eine 12-V- oder sonstige Versorgung von der Wärmepumpe wird **nicht** benötigt.

### Keinen zweiten Master erzeugen

Das LTE-Modem kommuniziert bereits aktiv mit dem Mainboard. Ein parallel angeschlossener Adapter sollte deshalb beim Mitschnitt **keine eigenen Modbus-Abfragen oder Schreibbefehle senden**.

In FoxAir Control dafür den **Firmware-Langzeit-Capture (streng passiv)** verwenden. Andere Software, die beim Öffnen des COM-Ports automatisch Geräte scannt, pollt oder Register liest, ist für diesen Aufbau ungeeignet.

### Keine zusätzliche Terminierung

Der zusätzliche Abgriff ist nur ein kurzer paralleler Stub. Am USB-RS485-Adapter sollte für diesen Zweck **kein zusätzlicher 120-Ohm-Abschlusswiderstand** aktiviert werden. Eine zusätzliche Terminierung kann den bestehenden RS485-Bus unnötig belasten.

Beim gezeigten Jhoinrch-Adapter ist deshalb besonders der mit **`120Ω`** beschriftete Jumper zu kontrollieren.

### Leitungen kurz halten

Die Stichleitung vom vorhandenen Bus zum USB-RS485-Adapter möglichst kurz halten. Für einen temporären Diagnoseabgriff sind kurze Leitungen unkritischer als eine lange, zusätzlich parallel verlegte Verbindung.

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

- Richtiger COM-Port ausgewählt?
- Kommunikationsart wirklich **Modbus Warmlink LTE**?
- Transport wirklich **Serial / COM-Port**?
- **9600 Baud / 8N1** eingestellt?
- Wirklich die **485-A / 485-B**-Klemmen des DTU verwendet?
- A und B korrekt angeschlossen?
- A/B testweise vertauschen.
- LTE-Modem/DTU und Wärmepumpe eingeschaltet und kommunizieren tatsächlich?

### Daten vorhanden, aber nur unbrauchbare Zeichen / ungültige Frames

- Baudrate und 8N1 nochmals prüfen.
- Sicherstellen, dass wirklich der LTE-/Warmlink-Bus und nicht der Display-/DWIN-Bus abgegriffen wurde.
- A/B prüfen.

### Capture lässt sich nicht starten

- In **Programm-Einstellungen → Verbindung** die Kommunikationsart **Modbus Warmlink LTE** auswählen.
- Falls die Verbindung bereits aktiv ist und die Kommunikationsart geändert werden muss: zuerst trennen.

### Im Firmware-Capture erscheinen TX-Bytes

Der Firmware-Modus ist darauf ausgelegt, eigene Telegramme von FoxAir Control zu sperren. Falls trotzdem TX-Bytes durch FoxAir Control gezählt werden oder der Status nicht **TX-SPERRE AKTIV** zeigt, Capture stoppen und die Konfiguration prüfen, bevor der parallele Mitschnitt fortgesetzt wird.

### Kommunikation der Wärmepumpe wird nach Anschluss gestört

USB-RS485-Adapter sofort wieder abklemmen und prüfen:

- Ist die **120-Ω-Terminierung** am Adapter aktiviert?
- Läuft versehentlich der normale Langzeit-Capture oder eine andere Software, die aktiv sendet?
- Wurde versehentlich eine zusätzliche Leitung wie Versorgungsspannung angeschlossen?
- Ist der Adapter für echtes RS485 geeignet und elektrisch unauffällig?
- Ist die zusätzliche Stichleitung unnötig lang?

## Hinweis

Diese Dokumentation basiert auf der untersuchten FoxAir/PHNIX-GL9-Konfiguration und ist keine offizielle Herstelleranleitung. Klemmenbezeichnungen und Hardwarevarianten können bei anderen Mainboards oder Geräteversionen abweichen.

Der eigentliche Firmwaretransfer über den **Display-Modbus** ist im Projekt bereits bestätigt. Der Firmware-Langzeit-Capture am Warmlink-/LTE-Bus ist dagegen ein experimentelles Forschungswerkzeug für den begleitenden Steuer- und Auslöseverkehr. Er stellt **keine Firmware-Update-Funktion** bereit und es gibt **keine Garantie**, dass sich aus dem Warmlink-Mitschnitt der von Kensol verwendete Update-Auslöser oder ein eigenes reproduzierbares Updateverfahren ableiten lässt.
