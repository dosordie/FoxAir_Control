# Modbus-Anschluss am Klemmfeld

Die FoxAir / PHNIX GL9 besitzt einen eigenen **externen Modbus-RTU-Anschluss** für Gebäudeautomation, Raspberry Pi, USB-RS485-Adapter, SPS oder andere Modbus-Master.

Dieser Anschluss ist unabhängig vom Display-Bus und vom internen Warmlink-/LTE-Bus.

## Anschluss

Am Klemmfeld des Außengeräts ist der externe Modbus mit folgenden Klemmen bezeichnet:

- **485_A2** = RS485 A
- **485_B2** = RS485 B

Der Modbus-Master bzw. USB-RS485-Adapter wird direkt an diese beiden Klemmen angeschlossen.

> Vor Arbeiten am Klemmfeld die Wärmepumpe spannungsfrei schalten.

## Schnittstellenparameter

Für den Benutzer-Modbus werden bei der untersuchten GL9 verwendet:

- **9600 Baud**
- **8 Datenbits**
- **keine Parität**
- **1 Stopbit**
- Kurzform: **9600 8N1**
- **Modbus-Adresse / Unit ID: 1**

Eine zusätzliche Freigabe in der Wärmepumpe ist normalerweise nicht erforderlich.

## Lesen und Schreiben

Die Wärmepumpe verwendet normales **Modbus RTU**.

Typische Funktionen:

- **FC03** – Holding Register lesen
- **FC06** – einzelnes Register schreiben
- **FC16** – mehrere Register schreiben

Nicht jedes Register ist schreibbar. Vor Schreibzugriffen deshalb immer die Registerbeschreibung beachten.

## Welche Register gibt es?

Die aktuelle Registertabelle wird direkt in **FoxAir Control** gepflegt.

Im Hauptfenster **„FoxAir Main“** werden unter anderem angezeigt:

- Registernummer
- Name / Bedeutung
- aktueller Wert
- Einheit
- bekannte Wertebereiche
- Hinweise und bisherige Reverse-Engineering-Erkenntnisse

Die Registertabelle in FoxAir Control ist der empfohlene Bezugspunkt, da sie laufend mit neuen Erkenntnissen ergänzt wird.

[FoxAir Control auf GitHub](https://github.com/dosordie/FoxAir_Control)

Für eine Verbindung über den externen Klemmfeld-Modbus in FoxAir Control die Kommunikationsart **„Modbus Standard“** verwenden.

## Nicht mit anderen RS485-Anschlüssen verwechseln

An der FoxAir existieren mehrere serielle Verbindungen.

Für den normalen Benutzer-Modbus am Klemmfeld ist **485_A2 / 485_B2** vorgesehen.

Nicht verwechseln mit:

- dem **Display-/DWIN-Bus**
- dem **Warmlink-/LTE-DTU-Bus**
- anderen internen RS485-Verbindungen auf dem Mainboard

Diese Busse können andere Adressen, Baudraten oder Kommunikationsabläufe verwenden.

## Wenn keine Verbindung zustande kommt

Zuerst prüfen:

- wirklich **485_A2 / 485_B2** verwendet?
- **9600 8N1** eingestellt?
- **Unit ID 1** eingestellt?
- A und B korrekt angeschlossen?
- richtiger COM-Port bzw. RS485-Adapter gewählt?

Wenn keine Antwort kommt, kann testweise **A/B getauscht** werden. Unterschiedliche Hersteller bezeichnen RS485 A und B teilweise gegensätzlich.

