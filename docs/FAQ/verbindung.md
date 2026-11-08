# FoxAir Control – welche Verbindung soll ich verwenden?

FoxAir Control kann auf **mehreren Wegen** mit einer FoxAir-/PHNIX-Wärmepumpe kommunizieren. Wichtig dabei: **Nicht jeder Anschluss ist derselbe Modbus-Bus.** Außerdem ist eine Cloud-Verbindung etwas anderes als eine direkte Verbindung über RS485.

Du musst nicht alle Verbindungsarten verwenden. Für den Einstieg reicht **eine passende Verbindung**.

## Die vier Verbindungsarten im Vergleich

| Verbindung in FoxAir Control | Woher kommen die Daten? | Wofür geeignet? |
| --- | --- | --- |
| **Modbus Standard** | Direkter Benutzer-Modbus der Wärmepumpe | Livewerte, bekannte Parameter und viele lokale Lese-/Schreibfunktionen |
| **Modbus Display** | Kommunikation zwischen Mainboard und Touch-Display | Zusätzliche Display-Daten und spezielle Display-Bedienfunktionen |
| **Modbus Warmlink LTE** | Bus zwischen Mainboard und WarmLink-/LTE-Kommunikationsmodul | Diagnose der internen Kommunikation und spezielle Warmlink-Funktionen |
| **WarmLink Cloud** | Internetverbindung zur PHNIX-/WarmLink-Cloud | Fernzugriff ohne eigenen RS485-Anschluss, soweit die Cloud Daten und Funktionen anbietet |

**Empfehlung:** Wer einen eigenen RS485-Anschluss an der Wärmepumpe nutzen möchte, beginnt normalerweise mit **Modbus Standard**. Wer keinen Adapter anschließen möchte und bereits die WarmLink-App verwendet, kann zunächst die **Cloud** ausprobieren.

## 1. Modbus Standard – der direkte Benutzeranschluss

Das ist der normale, für externe Steuerungen vorgesehene Modbus-Anschluss der Wärmepumpe.

Bei der untersuchten GL9 befindet er sich am Klemmfeld und ist mit **485_A2 / 485_B2** bezeichnet.

Typische Einstellungen dieser Gerätefamilie:

- **9600 Baud, 8N1**
- **Modbus-Adresse (Unit ID): 1**

Mit diesem Anschluss können bekannte Register direkt abgefragt und – wenn sie schreibbar sind – verändert werden. Einige Funktionen, etwa bestimmte virtuelle SG-Ready-Vorgaben oder Engineering-Werte, sind ausdrücklich an diesen Mainboard-Zugang gebunden.

Mehr dazu: [Modbus-Anschluss am Klemmfeld](modbus.md).

## 2. Modbus Display – der Bus zum Touch-Display

Zwischen dem Touch-Display und dem Mainboard gibt es eine **eigene serielle Kommunikation**. Bei der untersuchten Anlage arbeitet sie mit **4800 Baud**.

FoxAir Control kann diesen Datenverkehr ebenfalls verarbeiten. Darüber lassen sich unter anderem Display-bezogene Werte, Parameterpakete und besondere Bedienabläufe nachvollziehen.

Wichtig zu wissen:

- Dieser Anschluss ist **nicht identisch** mit dem normalen Benutzer-Modbus.
- Einige Änderungen müssen über besondere **Display-Bedienbefehle** übertragen werden.
- Die Funktion **„Display-Parameter synchronisieren“** löst selbst Kommunikation aus und ist daher **kein reines passives Mithören**.
- Nicht alle angezeigten virtuellen Displaywerte sind direkt als echte Register auslesbar.

Der Display-Modus ist vor allem für Anwender interessant, die die Display-Kommunikation gezielt untersuchen möchten. Für den normalen Einstieg ist der Benutzer-Modbus meist einfacher.

## 3. Modbus Warmlink LTE – der Bus zum Kommunikationsmodul

Der Warmlink-/LTE-Bus verbindet das Mainboard mit dem vorhandenen Kommunikationsmodul für die WarmLink-App. Bei der untersuchten GL9 läuft er mit **9600 Baud, 8N1**.

FoxAir Control kann diesen Datenverkehr auswerten und bietet dafür unter anderem eine **Langzeitaufzeichnung (RAW-Capture)**. Auch bestimmte Lese- und Schreibfunktionen sind über diesen Weg möglich.

**Besonderheit:** Das LTE-Modul kommuniziert normalerweise selbst auf diesem Bus. Wenn zusätzlich FoxAir Control aktiv Telegramme sendet, können sich Übertragungen überschneiden. Deshalb nicht unkontrolliert oder in sehr kurzen Abständen abfragen.

Für einen reinen Mitschnitt ist der **passive Capture-Modus** die sicherere Wahl.

Eine ausführliche Anleitung zum Anschluss eines USB-RS485-Adapters findest du hier: [Warmlink-/LTE-Bus parallel mithören](../HowToWarmlink_Modbus.md).

## 4. WarmLink Cloud – ohne eigenen RS485-Adapter

FoxAir Control kann sich mit einem vorhandenen **WarmLink-/PHNIX-Benutzerkonto** anmelden und die dort zugeordneten Geräte abrufen.

Damit sind – abhängig von der Unterstützung des jeweiligen Gerätes – beispielsweise folgende Funktionen möglich:

- Betriebszustände und Messwerte lesen
- Wärmepumpe ein-/ausschalten, Betriebsart und Sollwerte ändern
- Heizkurve einschließlich 7-Punkt-Kurve und SG-Ready-Einstellungen bearbeiten
- unterstützte Timer ansehen und ändern
- aktuelle Fehler-, Kontakt- und Lastausgangsinformationen auswerten

Die Cloud-Unterstützung wurde besonders mit **FoxAir Control v0.4.0** erweitert. Die Verfügbarkeit einzelner Funktionen hängt aber von Firmware, Cloud-Zuordnungen und Serverantworten ab. Nicht jeder lokale Modbus-Wert ist automatisch auch über die Cloud erhältlich.

Für die Cloud-Verbindung brauchst du keinen zusätzlichen Busanschluss. Allerdings müssen die Wärmepumpe und dein Computer Internetzugang haben und die WarmLink-Dienste erreichbar sein.

Die eigentliche Regelung der Wärmepumpe funktioniert auch **ohne Cloud** weiter.

## RS485, USB und TCP/IP – was ist der Unterschied?

Diese Begriffe werden oft miteinander verwechselt:

- **RS485** beschreibt die elektrische Verbindung zur Wärmepumpe.
- **USB-RS485-Adapter** macht daraus am Computer beispielsweise einen **COM-Port**.
- **Serielles Netzwerk-Gateway / ser2net** macht die serielle Verbindung über eine **IP-Adresse und einen TCP-Port** erreichbar.
- **Modbus Standard, Display und Warmlink** bezeichnen in FoxAir Control die unterschiedlichen Kommunikationswege und Protokollabläufe.

Ein TCP-Port bedeutet also nicht automatisch, dass die Wärmepumpe selbst eine normale Modbus-TCP-Schnittstelle besitzt. Häufig werden die seriellen Daten lediglich über das Netzwerk weitergeleitet.

## Wie gehe ich beim ersten Verbindungsversuch vor?

1. In FoxAir Control die **passende Kommunikationsart** auswählen.
2. Je nach Aufbau **COM-Port** oder **TCP/IP-Adresse und Port** einstellen.
3. Die zur Verbindung gehörenden Schnittstellenparameter prüfen.
4. Verbindung herstellen und zuerst einige **Livewerte lesen**.
5. Erst wenn Werte und Zuordnungen plausibel sind, weitere Funktionen ausprobieren.

Bei der Cloud-Verbindung stattdessen das **Cloud-Fenster** verwenden, anmelden, Gerät auswählen und Werte abrufen bzw. Polling starten.

Falls Daten fehlen oder unplausibel sind, ist die **falsche Busart** eine häufige Ursache. Auch ein laufendes zweites Programm auf derselben seriellen Verbindung kann Probleme verursachen.

## Sicherheit beim Anschluss

Im Wärmepumpengehäuse befinden sich elektrische Bauteile mit gefährlichen Spannungen. Arbeiten an internen Leitungen oder Klemmen nur **spannungsfrei und durch entsprechend fachkundige Personen** durchführen lassen.

**Keine unterschiedlichen RS485-Klemmen miteinander verbinden**, nur weil sie ähnliche Bezeichnungen tragen. Vor dem Anschluss immer den richtigen Bus identifizieren.

---

Weitere Informationen: [FoxAir Control – Überblick](foxair_control_ueberblick.md) · [Funktionen und Bedienung](foxair_control_funktionen.md) · [Diagnose und sichere Nutzung](foxair_control_diagnose.md).
