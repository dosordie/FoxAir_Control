# WarmLink-App, LTE-Modem und SIM-Karte

Die FoxAir GL9 besitzt in vielen Ausführungen bereits ein **LTE-/4G-Kommunikationsmodul** für die WarmLink-App.

Dafür ist normalerweise **kein WLAN der Wärmepumpe** erforderlich. Das Kommunikationsmodul nutzt eine eigene IoT-SIM und verbindet sich darüber mit der PHNIX-/WarmLink-Cloud.

## WarmLink-App verbinden

Der normale Ablauf ist:

1. **WarmLink** auf dem Smartphone installieren.
2. Benutzerkonto anlegen und anmelden.
3. In der App auf **+** bzw. Gerät hinzufügen gehen.
4. Den QR-Code / Barcode der Wärmepumpe bzw. des Kommunikationsmoduls scannen.
5. Das Gerät dem eigenen Konto hinzufügen.

Danach können – abhängig von App- und Firmwareversion – unter anderem angezeigt oder geändert werden:

- Betriebsart
- Temperaturen
- Sollwerte
- Timer
- Betriebszustände
- viele Parameter aus den Factory Settings

Für die App ist kein Home Assistant oder zusätzlicher Server erforderlich.

## Die Wärmepumpe hat Internet ohne WLAN

Das serienmäßige WarmLink-/LTE-Modul besitzt eine Mobilfunkverbindung.

Deshalb kann die Wärmepumpe auch dann online sein, wenn:

- sie nicht mit dem Heim-WLAN verbunden ist,
- kein LAN-Kabel angeschlossen ist,
- kein zusätzlicher Router in der Nähe der Wärmepumpe steht.

Im Gerät befindet sich dafür ein LTE-/4G-Modul mit Antenne.

## SIM-Karte und Laufzeit

Die Laufzeit der IoT-SIM kann in der WarmLink-App im Bereich **SIM-Karte** angezeigt werden.

Dort werden – abhängig von App-Version und Konto – auch Möglichkeiten zur Verlängerung angezeigt.

Die Preise und angebotenen Laufzeiten können sich ändern. Deshalb am besten direkt in der App prüfen, welche Verlängerung aktuell angeboten wird.

Im Forum wurden bereits Verlängerungen für mehrere Jahre erfolgreich angezeigt bzw. angeboten.

## Funktioniert die Wärmepumpe ohne WarmLink?

**Ja.**

Die eigentliche Regelung läuft auf dem Mainboard der Wärmepumpe. WarmLink ist nur ein zusätzlicher Fernzugriff.

Auch ohne Internet bzw. ohne funktionierende WarmLink-App kann die Wärmepumpe weiterhin über das mitgelieferte Touch-Display bedient werden.

Das ist wichtig, wenn:

- die SIM abgelaufen ist,
- kein Mobilfunkempfang vorhanden ist,
- die WarmLink-Cloud nicht erreichbar ist,
- oder eine App-Version Probleme macht.

## WarmLink zeigt „Offline“

Wenn das Gerät in der App offline erscheint, zuerst prüfen:

- Wärmepumpe und LTE-Modul haben Spannung?
- Mobilfunkantenne angeschlossen?
- ausreichender Mobilfunkempfang?
- App vollständig schließen und neu öffnen
- Wärmepumpe bzw. LTE-Modul nur bei Bedarf kontrolliert neu starten
- SIM-Laufzeit in der App prüfen

Ein App-Problem bedeutet nicht automatisch, dass die Wärmepumpe selbst gestört ist.

## Registrierungsmail kommt nicht an

Im Forum gab es Fälle, bei denen die Bestätigungs-/Registrierungsmail vom Mailanbieter gefiltert wurde.

Falls keine Mail ankommt:

- Spam-Ordner prüfen
- Absender bzw. Domain auf die Whitelist setzen
- Registrierung erneut versuchen

## Unterschiede zwischen App-Versionen

WarmLink wurde mehrfach verändert. Menüs können sich daher zwischen:

- Android und iOS
- verschiedenen App-Versionen
- unterschiedlichen Mainboard-Firmwareständen

unterscheiden.

Im Forum gab es beispielsweise App-Versionen, bei denen der Zugriff auf das erweiterte Parameter-Menü mit **Code 66** nicht funktionierte, während derselbe Code direkt am Touch-Display weiterhin funktionierte.

Wenn ein Menü nach einem App-Update fehlt, deshalb zuerst prüfen, ob es am **Touch-Display** weiterhin vorhanden ist.

## V3.5, AI Saving und dynamischer Stromtarif

Die neu analysierte Mainboard-Firmware **V3.5 (`82400644 / 0035`)** erweitert die über WarmLink/Warmlink mögliche Remote-Regelung.

Dabei sind insbesondere neue spezialisierte Mainboard-Verbraucher für die Warmlink-Werte **8021–8028** und **8055** vorhanden. Sie können unter anderem Kompressor-Frequenzgrenzen sowie Heiz-/Kühl-/Warmwasser- und Zonen-Sollwerte beeinflussen.

Wichtig zur Einordnung:

- der grundlegende **AI-Saving-/Remote-Energy-Control-Pfad existiert bereits in V3.4**
- V3.5 erweitert diesen vorhandenen Regelkomplex
- der analysierte LTE-Dienst reicht entsprechende MQTT-Downlink-Nutzdaten als Modbus/RS485-Payload zum Mainboard weiter; die 802x-Werte werden dort nicht im LTE-Modem selbst berechnet
- daraus ist eine Cloud-/Server-Optimierung technisch gut ableitbar, aber **nicht**, dass tatsächlich ein Machine-Learning-/AI-Modell eingesetzt wird

Ohne Cloud-/LTE-Verbindung läuft die normale lokale Wärmepumpenregelung weiter. Cloudabhängige Optimierungswerte können dann jedoch naturgemäß nicht neu vom Server eintreffen.

## Erweiterte Diagnose

FoxAir Control kann zusätzlich direkt mit der Wärmepumpe bzw. dem WarmLink-/LTE-Bus kommunizieren und ist für Diagnose, Registeranalyse und lokale Steuerung gedacht.

[FoxAir Control mit der Wärmepumpe verbinden](verbindung.md)

Für den normalen Betrieb ist FoxAir Control aber nicht erforderlich.
