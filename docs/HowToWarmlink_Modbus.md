# HowTo: Warmlink-/LTE-Modbus per USB-RS485 parallel mithören

## Zweck

Diese Anleitung beschreibt, wie ein USB-RS485-Adapter parallel auf den Modbus zwischen Wärmepumpen-Mainboard und Warmlink-/LTE-Modem aufgelegt wird. Damit kann der vorhandene Datenverkehr mitgeschnitten und analysiert werden, ohne die bestehende Verbindung zum LTE-Modem zu trennen.

> **Wichtig:** Der zusätzliche USB-RS485-Adapter ist beim Mithören nur als Empfänger gedacht. Er darf nicht als zweiter Modbus-Master aktiv Telegramme auf den Bus senden, solange das LTE-Modem angeschlossen ist.

## Schnittstellenparameter

Für den Warmlink-/LTE-Modbus der hier untersuchten FoxAir/PHNIX-Wärmepumpe wurden folgende Parameter verwendet:

- **Baudrate:** 9600 Baud
- **Datenbits:** 8
- **Parität:** None
- **Stopbits:** 1
- Kurzform: **9600 8N1**

Nicht mit dem Display-/DWIN-Bus verwechseln: Dieser verwendet bei der untersuchten Anlage eine andere Schnittstelle bzw. Baudrate.

## Anschluss am Mainboard

Die beiden RS485-Leitungen des USB-RS485-Adapters werden **parallel** zu den bereits vorhandenen Leitungen des Warmlink-/LTE-Modems in die entsprechenden Klemmen am Mainboard gesteckt.

Es wird also nichts aufgetrennt:

```text
Mainboard RS485 A  ───── LTE-Modem A
        │
        └────────── USB-RS485 A

Mainboard RS485 B  ───── LTE-Modem B
        │
        └────────── USB-RS485 B
```

Die Klemmen für **A** und **B** sind auf dem Schaltplan bzw. an der Anlage entsprechend bezeichnet.

Falls trotz korrekter Schnittstellenparameter keinerlei verwertbare Telegramme empfangen werden, können **A und B vertauscht** sein. In diesem Fall die beiden RS485-Leitungen am USB-Adapter tauschen. Ein Vertauschen von A/B führt normalerweise lediglich dazu, dass keine gültigen Daten empfangen werden.

## Schritt für Schritt

1. Wärmepumpe vollständig spannungsfrei schalten.
2. Vorhandene RS485-Leitungen identifizieren, die vom Mainboard zum Warmlink-/LTE-Modem führen.
3. Beschriftung der Klemmen für **A** und **B** prüfen.
4. Leitung **A** des USB-RS485-Adapters parallel zur vorhandenen A-Leitung anklemmen.
5. Leitung **B** des USB-RS485-Adapters parallel zur vorhandenen B-Leitung anklemmen.
6. Darauf achten, dass keine Litzen herausstehen und kein Kurzschluss zu benachbarten Klemmen entstehen kann.
7. USB-RS485-Adapter mit dem PC bzw. Capture-System verbinden.
8. Serielle Schnittstelle auf **9600 Baud, 8N1** einstellen.
9. Wärmepumpe wieder einschalten und prüfen, ob Modbus-Telegramme empfangen werden.
10. Falls keine plausiblen Daten sichtbar sind, A/B am USB-RS485-Adapter tauschen und erneut testen.

## Wichtige Hinweise

### Nur A und B anschließen

Für das reine Mithören werden grundsätzlich nur die beiden RS485-Datenleitungen **A und B** benötigt. Versorgungsspannungen des Mainboards oder des LTE-Modems dürfen nicht mit dem USB-Adapter verbunden werden, sofern dies nicht für einen konkret verwendeten Adapter ausdrücklich erforderlich und elektrisch geprüft ist.

### Keinen zweiten Master erzeugen

Das LTE-Modem kommuniziert bereits aktiv mit dem Mainboard. Ein parallel angeschlossener Adapter sollte deshalb beim Mitschnitt **keine eigenen Modbus-Abfragen oder Schreibbefehle senden**.

Software, die beim Öffnen des COM-Ports automatisch Geräte scannt, pollt oder Register liest, ist für einen rein passiven Mitschnitt ungeeignet. Im Zweifel zuerst mit einem Tool arbeiten, das den seriellen Port ausschließlich lesend beobachtet bzw. keinerlei Telegramme sendet.

### Keine zusätzliche Terminierung

Der zusätzliche Abgriff ist nur ein kurzer paralleler Stub. Am USB-RS485-Adapter sollte für diesen Zweck **kein zusätzlicher 120-Ohm-Abschlusswiderstand** aktiviert werden. Eine zusätzliche Terminierung kann den bestehenden RS485-Bus unnötig belasten.

### Leitungen kurz halten

Die Stichleitung vom vorhandenen Bus zum USB-RS485-Adapter möglichst kurz halten. Für einen temporären Diagnoseabgriff sind kurze Leitungen unkritischer als eine lange, zusätzlich parallel verlegte Verbindung.

### Galvanisch getrennten Adapter bevorzugen

Wenn möglich einen **galvanisch getrennten USB-RS485-Adapter** verwenden. Dadurch wird das Risiko von Masseschleifen oder Potentialproblemen zwischen Wärmepumpe und angeschlossenem PC reduziert.

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

- COM-Port korrekt ausgewählt?
- 9600 Baud / 8N1 eingestellt?
- A und B korrekt angeschlossen?
- A/B testweise vertauschen.
- LTE-Modem und Wärmepumpe eingeschaltet und kommunizieren tatsächlich?

### Daten vorhanden, aber nur unbrauchbare Zeichen / ungültige Frames

- Baudrate und 8N1 nochmals prüfen.
- Sicherstellen, dass wirklich der LTE-/Warmlink-Bus und nicht der Display-/DWIN-Bus abgegriffen wurde.
- A/B prüfen.

### Kommunikation der Wärmepumpe wird nach Anschluss gestört

USB-RS485-Adapter sofort wieder abklemmen und prüfen:

- Ist eine Terminierung am Adapter aktiviert?
- Sendet die verwendete Software aktiv Daten?
- Wurde versehentlich eine zusätzliche Leitung wie GND oder Versorgungsspannung angeschlossen?
- Ist der Adapter für echtes RS485 geeignet und elektrisch unauffällig?

## Bilder

Fotos vom Mainboard, den Warmlink-/LTE-Klemmen und dem parallel angeschlossenen USB-RS485-Adapter können diese Anleitung sinnvoll ergänzen. Geeignete Bilder können z. B. unter `docs/images/warmlink_modbus/` abgelegt und anschließend hier per Markdown eingebunden werden.

Beispiel:

```markdown
![Warmlink-Modbus Klemmen am Mainboard](images/warmlink_modbus/mainboard_klemmen.jpg)
```

## Hinweis

Diese Dokumentation basiert auf der untersuchten FoxAir/PHNIX-Konfiguration und ist keine offizielle Herstelleranleitung. Klemmenbezeichnungen und Hardwarevarianten können bei anderen Mainboards oder Geräteversionen abweichen.
