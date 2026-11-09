# FoxAir / Phnix Control

<p align="center">
  <img src="app_icon.png" alt="FoxAir / Phnix Control Logo" width="160">
</p>

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.


> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern oder Cloud-Werten kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.

## 💙 Unterstützung

Ich bastle an diesem Tool in meiner Freizeit.  
Wenn er dir gefällt oder dir weiterhilft, freue ich mich über eine kleine Spende:

[![Spenden via PayPal](https://img.shields.io/badge/Spenden-PayPal-blue.svg?logo=paypal)](https://www.paypal.com/paypalme/AuhuberD)

## Dokumentation

- [FoxAir FAQ – Anleitungen und häufige Fragen](docs/FAQ/FAQ.md)


## Firmware-Übersicht

Eine kompakte Übersicht über bekannte **Mainboard-, Display- und LTE-DTU-Firmwarestände**, Softwarecodes und Gerätezuordnungen gibt es hier:

- [FoxAir / PHNIX Firmware-Übersicht](docs/firmware_overview.md)

Wichtig zur Einordnung: **Display V1.7 ist nicht Mainboard V1.7.** Bei FoxAir-Geräten können z. B. Display `82400463 / V1.7` und Mainboard `82400644 / V1.3`, `V3.3`, `V3.4` oder `V3.5` gleichzeitig installiert sein.


## Cloud-Steuerung

Die Cloud Steuerung wurde aus der Warmlink App rekonstruiert 
und beitet schon viele der in der App vorhandenen Funktionen.



## Screenshots

![FoxAir / Phnix Control Hauptfenster](docs/screenshots/Screenshot%20Fox_main.png)

![FoxAir / Phnix Control Hauptfenster mit erweiterten Werten](docs/screenshots/Screenshot%20Fox_main2.png)

![FoxAir / Phnix Control Cloud-Ansicht](docs/screenshots/Screenshot%20Fox_cloud.png)

![FoxAir / Phnix Control Steuerung](docs/screenshots/Screenshot%20Fox_control.png)

![FoxAir / Phnix Control Timer](docs/screenshots/Screenshot%20Fox_timer.png)

![FoxAir / Phnix Control AT-Kompensation](docs/screenshots/Screenshot%20Fox_AT.png)

![FoxAir / Phnix Control Einstellungen](docs/screenshots/Screenshot%20Fox_settings.png)

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- WarmLink/Linked-Go Cloud: Login, Geräteübersicht, Statuswerte, Overlay, API-Debugger und Schreiben bestätigter Cloud-Codes
- Lesen und Schreiben per Modbus Standart, Modbus Display und Modbus Warmlink LTE
- TCP/IP/ser2net oder USB-RS485/COM-Port
- F1 Hilfe/About mit Version, GitHub-Link und Update-Prüfung
- Eigenständige **Geräte-Info** für Mainboard-, ProductKey- und Kommunikationsmodul-Identitäten
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder

### Geräte-Info über Warmlink/LTE

Die Schaltfläche **Geräte-Info** öffnet eine lokale Diagnoseansicht. **Geräte-Info
auslesen** liest die verfügbaren Angaben regulär per FC03 (`200/1`, `2001/8` und
`50500/13`). Die bestätigungspflichtige **Sonderfunktion Update Anfrage Cloud**
sendet dagegen FC03 an Busadresse `0x63`, Register `4`, Anzahl `1`. Dieser besondere
Read erwartet keine normale FC03-Antwort, sondern veranlasst das LTE-Modem, ein
MQTT-Telegramm mit den Geräteinformationen an die Cloud zu senden. Die acht
normalen Datenblöcke enden bei Register 2180. Hardware-/Softwareinformation kann
erst nach ungefähr 50 Sekunden eintreffen, der Dialog wartet insgesamt 180 Sekunden
und behält bei einem Timeout alle Teilergebnisse.

Angezeigt werden die individuelle WiFi-/Kommunikationsmodul-ID aus 2001–2006, der
ProductKey als Kennzeichen der PHNIX/Aliyun Produkt- bzw. Cloudfamilie sowie
Hardware- und Softwarecode des Mainboards. Die WiFi-ID ist nicht die Seriennummer
des Typenschilds; der ProductKey ist ebenfalls keine individuelle Seriennummer.
Vollständige WiFi-ID und ProductKey erscheinen bewusst nur im ausdrücklich
geöffneten lokalen Dialog und werden nicht in normale Diagnoseausgaben übernommen.

Bei aktivierter Einstellung **Engineering-Parameter anzeigen** bietet Geräte-Info
zusätzlich die gefährliche, Warmlink-only [Mainboard-WiFi-ID-Servicefunktion](docs/mainboard_wifi_identity.md).
Sie verlangt eine erneute ID-Bestätigung, Backup, ACK-/Rückleseprüfung und eine
60-s-Wartezeit vor einem manuellen Neustart.

## UDP-Diagnoseausgabe

FoxAir Control kann optional kompakte Diagnoseereignisse per UDP an lokale Auswertewerkzeuge senden. Die Funktion ist standardmäßig deaktiviert und sendet ausschließlich ausgehend (Best Effort, kein Empfangspfad, keine Wiederholungen).

* Standardziel: `127.0.0.1:8766`
* Registeränderungen und Raw-Busdaten sind getrennt aktivierbar.
* Gesendet werden nur kleine JSON-Datagramme, keine Zugangsdaten oder kompletten Registerlisten.
* Ein kleiner Testempfänger kann so gestartet werden:

```bash
python tools/udp_diag_receiver.py
```

Beispielausgabe:

```json
{"event":"register_change","ts":"...","backend":"display_modbus","reg":2106,"old_raw":0,"raw":1,"hex":"0x0001","name":"Pumpenregel-/PWM-Regelzyklus Flag (Kandidat)"}
```

## Lizenz
[GPLv3](LICENSE)
