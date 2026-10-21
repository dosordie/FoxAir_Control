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
- [Solltemperaturen extern korrigieren – speicherschonend über RAM-Register 8802–8808](docs/FAQ/externe_sollwertkorrektur.md)


## Firmware-Übersicht

Eine kompakte Übersicht über bekannte **Mainboard-, Display- und LTE-DTU-Firmwarestände**, Softwarecodes und Gerätezuordnungen gibt es hier:

- [FoxAir / PHNIX Firmware-Übersicht](docs/firmware_overview.md)

Wichtig zur Einordnung: **Display V1.7 ist nicht Mainboard V1.7.** Bei FoxAir-Geräten können z. B. Display `82400463 / V1.7` und Mainboard `82400644 / V1.3`, `V3.3`, `V3.4` oder `V3.5` gleichzeitig installiert sein.

Die analysierte **Mainboard-V3.5 stammt von einer FoxAir BlueLine (BL)**. BlueLine und GreenLine (GL) mit Mainboard-Softwarecode **`82400644`** verwenden dieselbe Mainboard-Firmwarelinie; die V3.5 ist für entsprechende Geräte dieser Familie untereinander kompatibel.



### Warmlink RAW / Firmware-Logging

Ab Version `0.2.51` enthält FoxAir Control einen Expertenmodus für den passiven Warmlink RAW Langzeit-Capture.  
Damit können RX/TX-Rohdaten des Modbus-Warmlink/LTE-Datenstroms als Binärdateien gespeichert und über `events.jsonl` sowie `frame_complete` Events für spätere Offline-Analysen indexiert werden.

Die Funktion ist für Diagnose und spätere Firmware-Update-Erkennung vorbereitet:
- passive Beobachtung von Register `2104 / Hauptsoftwareversion`
- Erkennung vollständiger Warmlink-/Modbus-Frames mit Offsets in die RAW-Dateien
- robuste Segmentierung für Langzeitmitschnitte
- keine aktive Firmware-, Replay- oder Schreibfunktion

RAW-Captures können sensible Geräte-/Betriebsdaten enthalten und sollten nicht öffentlich geteilt werden.

## Cloud-Steuerung

AT-Kompensation und SG Ready schreiben regulär ohne experimentelle Freigabe und
starten Cloud-Writes direkt per Schreibbutton. Nur geänderte Kurven-/SG-Werte
werden gesendet. Ein `app/device/control?lang=en`-Request mit `appId: "16"` und
mehreren `param[]`-Einträgen ersetzt einzelne HTTP-Writes; alle geschriebenen Codes
werden gemeinsam frisch zurückgelesen. Teiländerungen bleiben sichtbar und offen,
soweit sie nicht bestätigt sind. Es gibt keinen automatischen Write-Retry oder Rollback.

Der Betreiber hat alle sieben AT-Punkte einzeln und einen gemeinsamen 7-fach-Write
mit gemeinsamem Readback am **17.10.2026 an der GL9** bestätigt. Lineare Kurve,
H36 und SG01–SG08 sind ebenfalls für den bestätigten Cloudweg freigegeben.
Eine atomare Übernahme durch den Server wird daraus nicht abgeleitet.

SG02–SG08 werden gemeinsam geprüft, bevor SG01 aktiviert/umgeschaltet wird.
SG01=0 wird zuerst geschrieben und bestätigt. SG08 ist eine Aus/Ein-Auswahl;
SG Status bleibt read-only, 8801 bleibt ausschließlich direktem Mainboard-Modbus vorbehalten.
AT, SG, Parameterblöcke und Störungsdecoder laden beim Öffnen gezielt aktuelle
Cloudwerte. Der Decoder verwendet alle elf aktuellen Fehlerwörter einschließlich
Sammelstörung, keine Fehlerhistorie. Schreibtest und Wertefinder wurden entfernt.
Lokale Bestätigungen und LTE-Recovery bleiben erhalten.

## Cloud-Decoder und Timer

Kontaktdecoder (2034 / `S01~S10`) und Lastausgangsdecoder (2019 / `O01~023`)
laden beim Öffnen frische Cloudwerte. „jetzt lesen“ und optionales Polling nutzen
denselben asynchronen Cloudweg; fehlende Werte bleiben `--`. Die Decoder sind read-only.
Bei lokaler Modbus-Verbindung gilt weiterhin die lokale Datenpriorität.

Der Silentmodus-Timer lädt alle sechs Werte (1244–1249) gemeinsam. Geänderte Werte
werden ohne zusätzliche Cloud-Bestätigung als Batch geschrieben und gemeinsam
frisch zurückgelesen. Deaktivierungen werden zuerst bestätigt, geänderte Zeiten
vor Aktivierungen. Nicht bestätigte Änderungen und neuere Eingaben bleiben offen.
Der kombinierte WP-Ein/Aus-Timer-Editor zeigt über Cloud alle sechs WP-Timer
und den Silentmodus. Auch die Betriebsart-Timer 1–6 laden ihre 45 M-Codes
über Cloud und schreiben nur geänderte Werte mit Readback. Lokale Modbus- und
Display-Abläufe bleiben erhalten; Cloud-only erfordert keine Display-Pakete.

**Hinweis:** Cloud-Writes der Silent-, WP-Ein/Aus- und Betriebsart-Timer sind
implementiert, aber noch nicht sämtlich live an der GL9 verifiziert.
Details und offene Praxisprüfungen: [Cloud-Dokumentation](docs/warmlink_cloud_values.md#kontakt-lastausgangsdecoder-und-silentmodus-timer).

## PUBLIC V0.2.46 – Struktur-Refactoring

Diese Public-Version behält das Verhalten aus V0.2.45 bei und räumt die Projektstruktur auf:

- Cloud-Login mit gespeicherter E-Mail und Passwort im OS-Keyring (`keyring>=25.0`)
- Cloud-Geräte-/Device-ID-Anzeige
- Cloud-Polling, Overlay und Cloud-Spalten im Hauptfenster
- Cloud-Batch-Steuerung für bestätigte AT-/SG-Parameter mit gemeinsamem Readback
- Generischer API-Debugger; Exporte und Cloud ↔ Lokal bleiben verfügbar
- Rechtsklick **Wert per Cloud schreiben ...** für bekannte schreibbare Cloud-Codes
- Cloudwerte können als Overlay im Hauptfenster erscheinen; optionale **Cloud-only Zeilen** zeigen bestätigte Mappings auch ohne zuvor gelesenen lokalen Wert
- Der Doppelklickdialog bietet bei aktiver Cloud-Verbindung **Cloud lesen** und – nur für ausdrücklich freigegebene Schreibcodes – **Cloud schreiben**
- Log-Spam-Reduktion für stark wiederholte Display-Bus-Frames bleibt aktiv
- Runtime-Code ist in `core/`, `workers/`, `cloud/`, `dialogs/`, `ui/` und `data/` gegliedert


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


### WarmLink iOS 3.0.8: zusätzliche Diagnose

Die Cloud-Codeabdeckung enthält additiv die 108 in der Original-App beobachteten
Codebezeichnungen. Leere Werte bleiben erneut abfragbar; insbesondere die drei
PWM-Codes brauchen noch einen Gegencheck bei laufender Wärmepumpe.
Der Bereich **Geräte → SIM / LTE-Vertragsstatus** liest die Vertragsdaten nur
auf **Aktualisieren**. Er benötigt die ICCID aus der vorhandenen Geräteübersicht;
Statuscodes werden als Rohwerte angezeigt, Zahlungsfunktionen gibt es nicht.
**API-Debugger → OTA-Updateprüfung vorbereiten** befüllt lediglich einen
editierbaren Request. Das ist keine Firmware-Updatefunktion; erst **Senden**
führt die Abfrage aus. HTTP 404 bleibt eine Serverantwort und bedeutet nicht
„kein Update verfügbar“.
