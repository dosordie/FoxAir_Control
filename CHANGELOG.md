## PUBLIC V0.2.44

- Public-Build auf Basis von **PUBLIC V0.2.42** erstellt; `APP_EDITION` bleibt **PUBLIC**.
- Cloud-Funktionen aus **PRIVATE V0.2.44 fix4** übernommen: Login, Geräte-/Device-ID-Anzeige, Polling, Overlay, Wertefinder, Schreibtest und Hauptfenster-Rechtsklick **Wert per Cloud schreiben ...**.
- Cloud-Schreiben nutzt das live bestätigte Format: `app/device/control?lang=en` mit `appId="16"` und `param: [{deviceCode, protocolCode, value}]`.
- Hauptfenster: Checkbox **Cloud-only Zeilen**, Standard eingeschaltet.
- Display-Modus-/Write-Pfade bleiben gegenüber **PUBLIC V0.2.42** unverändert.
- Log-Spam-Reduktion aus PUBLIC V0.2.42 bleibt enthalten.
- Quellen-/Attributionshinweise für öffentliche Warmlink-/Linked-Go-Recherchequellen ergänzt.
- Installer-Version auf 0.2.44 gesetzt.

## PUBLIC V0.2.42

- Public-Build auf Basis von **PUBLIC V0.2.41 fix7** erstellt; `APP_EDITION` bleibt **PUBLIC**.
- Keine Änderung an den Display-Modus-/Write-Pfaden übernommen. Die experimentellen Display-Schreibabläufe bleiben unverändert zum letzten Public-Stand.
- Log-Spam im Backend **Modbus Display** reduziert: stark wiederholte Fremdframe-/Read-Request-Zeilen werden pro Frame-Typ zusammengefasst, z. B. bei massiven `0x02 / 3001` Polls.
- Quellen-/Attributionshinweise für den GitHub-Public-Release ergänzt, u. a. Hinweise auf öffentlich genutzte Warmlink-Recherchequellen.
- Installer-Version auf 0.2.42 gesetzt.

## PUBLIC V0.2.41 fix7

- Public-Build aus internem Stand **V0.2.41 fix7** erstellt; `APP_EDITION` ist **PUBLIC**.
- Display-Modbus: verbesserte Timer-/Popup-Schreibpfade mit `Register + 0x2000` nur im Backend **Modbus Display**.
- Display-Modbus: Popups warten auf benötigte Paketdaten und öffnen/schreiben nicht mehr blind mit leeren oder alten Werten.
- Display-Modbus: Mehrfachwrites werden einzeln/sequenziell abgearbeitet; `1181ff`-Timerpfade enthalten zusätzlichen Fallback über Kommunikationsregister und `0BC3=0x0008`.
- Log-Level 1–7 ergänzt und nachgeschärft; Level 4 ist für normale Diagnose-Logs geeignet, RAW/TX erst ab Level 6.
- RAW anzeigen liefert HEX+ASCII; separate RAW-ASCII-Checkbox aus der Kopfzeile entfernt.
- FC06/FC16-Auswahl aus der normalen Einstellungsseite ausgeblendet; Spezialpfade entscheiden intern.
- Installer-Version auf 0.2.41 gesetzt.

## V0.2.38 PRIVATE fix12

- Backend **Modbus Display**: DWIN-/Displaywerte ab Register `3000` werden jetzt im Hauptfenster sichtbar, z. B. `3001ff`, `3011/0BC3` und `3021`.
- `foxair_phnix_display_registers.json` um Einträge `3001–3021` ergänzt, inklusive Klartext für `3011/0BC3` als Parameter-Sync-/Änderungsflag.
- Teilnehmer `0x04` und `0x05` werden nur dann in die Hauptliste übernommen, wenn deren Register nicht mit bekannten WP-/Warmlink-Registern kollidieren. Null-/Fremdblöcke auf bekannten Bereichen wie `1001ff` oder `2000ff` bleiben Diagnose.
- Die Änderung gilt ausschließlich für das Backend **Modbus Display**. Warmlink RAW und Standard-Modbus bleiben unverändert.

## V0.2.38 PRIVATE fix11

- PRIVATE Display-Testbereich in der Seitenleiste ausgeblendet, Code/Methoden bleiben zum Reaktivieren und Debuggen erhalten.
- Backend **Modbus Display**: Button **Alle bekannten Register lesen** nutzt jetzt standardmäßig den ACK-gesteuerten **Display Reboot Fake** als Snapshot-Methode statt aktive Qty90-Paketreads.
- Popup-/Arbeitsablauf-Reads auf bekannte Display-Parameterpakete werden im Display-Backend entprellt ebenfalls über den Reboot-Snapshot aktualisiert. Manuelle FC03-Reads bleiben direkt möglich, damit der Qty90-Direktleseweg weiter untersucht werden kann.
- Warmlink und Standard-Modbus bleiben unverändert und nutzen weiterhin ihre eigenen Init-/Lesepfade.


## V0.2.38 PRIVATE fix10

- Display-Parameterpakete `0x03/1001ff..1541ff` werden nun auch bei passiv gesehenen Master-Reads wieder mit dem normalen WP-/Warmlink-Mapping dekodiert.
- Damit bleiben Klartexte/Value-Maps nach Bedienwert-Writes sichtbar, z. B. `1012 = 0 Warmwasser`, `1012 = 1 Heizen`, `1012 = 2 Kühlen`.
- Display-/DWIN-Diagnoseadressen wie `3001ff` bleiben weiterhin im getrennten Display-Mapping.

## PRIVATE V0.2.38 fix9

- Normale Schreiblogik im Backend **Modbus Display** erweitert: bekannte Display-Parameterpaket-Nutzwerte werden jetzt automatisch wie eine echte Display-Bedienung geschrieben. Beispiel: `1012=2` wird als `23F4=2` gesendet.
- Der Rechtsklick-Write und Popups wie WP-Steuerung, Timer-/Parameterfenster usw. brauchen dafür keine Extra-Bestätigung.
- Neue ACK-gesteuerte Warteschlange für Display-Parameterwrites: mehrere Popup-Schreibbefehle laufen nacheinander statt parallel auf dem Bus.
- Default für den Display-Wert-Test ist jetzt Variante **A**: nur Benutzerwert (`Register + 0x2000`). Das Display setzt `0BC3` selbst.
- Fallback bleibt automatisch: wenn Variante A nicht sicher greift, wird `0BC3` nachgesetzt bzw. B/C versucht.

## PRIVATE V0.2.38 fix8

- Display-Experimente PRIVATE: Reboot-Fake jetzt ACK-gesteuert. `5112H=0` wird erst nach ACK fortgesetzt; `0BC3H=8000H` wird bei fehlendem ACK oder fehlendem `3001/3011=0x8000` gezielt erneut gesendet.
- Display-Wert-Test jetzt ACK-gesteuert: Paketwert/Userwert/`0BC3` werden sequenziell gesendet; der nächste Schritt startet erst nach ACK von Unit `0x03`.
- Wenn `0BC3` beim nächsten `3001`-Poll nicht sichtbar wird, setzt die App nur `0BC3` erneut, statt lange auf einen Paketblock zu warten.
- Variante B (`23xx` Benutzerwert + `0BC3`) nutzt automatisch Variante C (`03xx` Paketwert + `23xx` Benutzerwert + `0BC3`) als Fallback, wenn B trotz ACK/Retry nicht greift.
- Schnellbutton **WW** ergänzt: setzt `1012=0` laut `MODE_0_4` Mapping. Heizen bleibt `1012=1`, Kühlen `1012=2`.

## V0.2.38 fix2
- Display-Init-Paketreads werden vorerst wieder ins Hauptfenster übernommen, wenn der WP-Paketkopf gültig ist.
- Broadcast 0x00/2001 und 0x00/2091 bleiben weiterhin gültige zyklische Display-Livewertquellen und können die Werte später aktualisieren.
- Hintergrund: Bis ein besseres Display-Init-Timing/Quelle gefunden ist, sollen die aktiv vom Display gelesenen Init-Werte sichtbar im Hauptfenster stehen.



## V0.2.37 Fix31

- Warmlink/LTE-Init-Lesen in `workers/warmlink_worker.py` ausgelagert.
- Neuer `WarmlinkInitReadController`: sendet die Init-Blöcke sequenziell und wartet auf Antwort oder Timeout.
- Fix für Warmlink-Timing: späte Antworten der letzten Statusblöcke können nicht mehr so leicht dem falschen Pending-Read zugeordnet werden.
- DisplayWorker-Timing verbessert: vor aktiven Display-Paketreads wird jetzt auf eine Buslücke gewartet; Timeout leicht erhöht.
- Warmlink/Standard-Lesepfad und DisplayWorker bleiben funktional getrennt.
# V0.2.37 Fix23

- Fix für „Alle bekannten Register lesen“ am Backend „Modbus Display“: Der Display-Sonderpfad wird nun zusätzlich über das sichtbare Backend-Label erkannt.
- Die bekannten Display-Paketreads werden fest an Unit 0x03 gesendet; die UI-Unit wird hierfür bewusst ignoriert, weil Unit 0x01 keine gültigen 90er-Paketblöcke liefert.
- Der Display-Init nutzt weiterhin nur die bisher bestätigten Paketblöcke 1001/90, 1091/90, 1181/90 und 1361/90 ohne +0x2000-Übersetzung.

# V0.2.37 PRIVATE Fix12 (ohne Versionsanhebung)

- Dual-Bus Logger: Warmlink-FC03-Responses werden jetzt lokal den gesendeten Polls zugeordnet.
- Dadurch erscheinen Warmlink-Poll-Antworten wieder als `WARMLINK RX zugeordnet` / `WARMLINK DIFF` im Dual-Log.
- Warmlink-Polling im Dual-Logger verlangsamt (700 ms Abstand), damit ser2net/Warmlink sauberer antwortet.
- Keine Änderung am normalen Registerbrowser und keine Übernahme von Dual-Logger-Werten in Hauptwerte.

# Changelog

## V0.2.37 PRIVATE Fix9 (ohne Versionsanhebung)

- Display-Bus bleibt weiter strikt von der Warmlink-Hauptliste getrennt.
- Fix8-Korrektur verfeinert: bekannte Display-Parameterpakete von Unit `0x03` (`1001ff`, `1091ff`, `1181ff`, `1271ff`, `1361ff`, `1451ff`, `1541ff`) werden wieder als getrennte Diagnosewerte geloggt.
- Neue getrennte Display-Wertelisten intern: `display_last_values` / `display_latest_regs`; Logausgabe mit Prefix `DREG ...`. Dadurch sieht man die sicheren 10xx-Werte wieder, ohne `last_values` / Registerbrowser / Warmlink-Mapping zu überschreiben.
- Offline-Registerbrowser kann jetzt zwischen `Warmlink/WP` und `Display/DWIN` umgeschaltet werden. Display/DWIN nutzt `foxair_phnix_display_registers.json`.
- Aus dem Display-Browser gelesene Register werden automatisch auf Unit `0x03` gelesen.

## V0.2.37 PRIVATE Fix8 (ohne Versionsanhebung)

- Kritischer Rollback: normales `foxair_phnix_registers.json` wieder auf Warmlink/WP-Mapping zurückgesetzt; Display/DWIN-Diagnose überschreibt keine bekannten Register ab 2101 mehr.
- Neues getrenntes Diagnose-Mapping `foxair_phnix_display_registers.json` ergänzt. DWIN-/Display-Adressen werden nur für Popup/Log-Diagnose benutzt.
- Display-Modbus: passive Blöcke wie `0x01/2099ff` und `0x03/1001ff` werden nicht mehr in die Haupt-Registerliste übernommen, sondern nur noch als Snapshot/Diff geloggt.
- Manuelle DWIN-Lesungen werden im Popup angezeigt, aber nicht mehr in `last_values`/Haupttabelle geschrieben.
- `4732/0x127C` wieder auf Kandidat zurückgestuft; kein bestätigtes Warmlink-Register.

## V0.2.37 PRIVATE Fix6 (ohne Versionsanhebung)

- Display-/HMI-Modbus: manuelles Register-Popup um schnelle DWIN-Probelesungen erweitert. Neue Buttons: „DWIN Temp-Suche“ und „DWIN Status-Suche“.
- DWIN-Probelesungen lesen gezielt Anzeigeadressen wie 0x1270, 0x127C, 0x11C0, 0x1720, 0x1730, 0x1800, 0x1880 und 0x1A00 auf Unit 0x03, um sichtbare Display-Werte wie T1/T2/T4 und Status-/Iconfelder zu finden.
- Register-Mapping um DWIN-Diagnoseadressen ergänzt: 3012/3013 Display-Software, 3021 Display-Istmodus/Icon-Code-Kandidat sowie mehrere Temperatur-/Anzeige-Kandidatenblöcke.
- 3013 ist als beobachtete Display-Softwareversion V1.7 dokumentiert.
- Keine Änderung an 2012: 2012 wird weiterhin nicht aus 1012 oder 3021 überschrieben.

## V0.2.37 PRIVATE Fix5 (ohne Versionsanhebung)

- Display-/HMI-Modbus: Rohblock-Diagnose mit Snapshots und Diffs für 0x01/1999ff, 0x01/2099ff, 0x03/3001ff, 0x03/1001ff und 0x05/1001ff ergänzt.
- Kleine wechselnde Codes 0..4 werden als Kandidaten für Istmodus/Icon/Anzeigezustand markiert.
- In den Tests wurde 3021/W21 im DWIN-Anzeigeblock als starker Kandidat für einen Display-Istmodus-/Icon-Code sichtbar.

## V0.2.37 PRIVATE Fix5 (ohne Versionsanhebung)

- Display-/HMI-Modbus: 1012→2012-Fallback wieder entfernt. 1012 ist Sollmodus, 2012 ist Ist-/Betriebsstatus mit anderer Codetabelle; ein Spiegeln erzeugt falsche Werte.
- Display-/HMI-Modbus: Addr 0x01 / 1999ff bzw. 2001ff wird nicht mehr in die Hauptliste übernommen, solange der Block nicht eindeutig als vollständiger Nutzdatenblock verifiziert ist.
- Display-/HMI-Modbus: zusätzliche Debug-Logs für gesperrte 1999/2001-Frames und FC16-ACKs ergänzt. Damit können die 20xx-Blöcke weiter untersucht werden, ohne 2012/2001-2010 zu verfälschen.
- Addr 0x03 / 1001ff Parameterpakete bleiben aktiv; 1012 läuft beim Umschalten am Display weiter mit.

## V0.2.37 PRIVATE Fix3 (ohne Versionsanhebung)

- Display-/HMI-Modbus: 1999/2001-Statusblöcke von Addr 0x01 werden jetzt auch als FC16-Write-Request übernommen, falls Nutzdaten statt nur ACK sichtbar sind.
- Display-/HMI-Modbus: Fallback ergänzt, der 2012 in der Anzeige aus 1012 nachführt, wenn der Display-Bus keinen zyklischen echten 2012-Statusblock liefert. Der Log kennzeichnet diesen Wert ausdrücklich als Fallback.
- Warmlink/Standard-Modbus bleiben unverändert; der Fallback gilt nur für Display-/HMI-Diagnose.

## V0.2.37 PRIVATE Fix2 (ohne Versionsanhebung)

- Display-/HMI-Modbus: Statusblock von Addr 0x01 / 1999ff wird nun zusätzlich in die Hauptliste übernommen.
- Damit können Statuswerte wie 2011/2012 aus dem Display-Bus mitlaufen, wenn die Hauptplatine den 1999ff-Block sendet.
- Fix1 bleibt unverändert: Addr 0x03 / 1001ff Parameterpakete werden weiter für 1012 übernommen; Fremdadressen wie 0x05 bleiben gesperrt.

## V0.2.37 PRIVATE Fix1 (ohne Versionsanhebung)

- Display-/HMI-Modbus: Parameterpakete von Addr 0x03 / 1001ff, 1091ff, 1181ff, 1271ff, 1361ff, 1451ff werden nun unabhängig von der aktuell eingestellten manuellen Unit in die Hauptliste übernommen.
- Damit bleiben bei Diagnose-Unit 0x01 die sicheren Live-/Statuswerte 2099ff sichtbar und zusätzlich die HMI-Parameterpakete von 0x03, z. B. Register 1012 beim Umschalten am Display.
- Aktive Unit wird weiterhin für manuelles Lesen/Schreiben verwendet; Fremdadressen wie 0x05 werden weiterhin nicht blind übernommen.

## V0.2.37 PRIVATE

- Display-/HMI-Modbus Diagnose weiter verbessert: passive Read-Requests werden gemerkt und die folgenden Responses dadurch dem Startregister zugeordnet.
- Sichere passive Live-/Statuswerte von Addr 0x01 / 2099ff können in die Hauptliste übernommen werden.
- Werte von der aktiven Display-Unit werden als Display-HMI-Quelle geloggt; Fremdadressen werden weiterhin nicht blind übernommen.
- DWIN-/Parameter-Sync-Flag 3011 / 0x0BC3 wird im Log als solches benannt.
- Adress-Vermutungen für Display-/HMI-Bus aktualisiert.

## V0.2.36 PRIVATE

- Display-/HMI-Modbus Diagnose verbessert: manuelle Busadresse im Lesen/Schreiben-Feld wird jetzt beim Display-Modbus wirklich verwendet. Damit können 4/5/6 getestet werden, auch wenn in den Programmeinstellungen Unit 3 steht. Andere Modbus-Modi bleiben unverändert.
- Display-/HMI-Modbus: passive Registerwerte fremder Slave-Adressen werden nicht mehr global in die Haupt-Registerliste übernommen. Das verhindert, dass z. B. Register 1012 durch Fremdframes scheinbar wieder auf WW springt.
- Log-Vermutungen für Display-/HMI-Adressen nach den aktuellen Mitschnitten ergänzt: 0x01 Live-/Statusbereich 1999/2099, 0x02/0x03 DWIN-Speicher 3001ff, 0x04 Parameterblock 1011ff, 0x05 Live-/Parameterblock 2000ff/1001-1090.
- Display-Modbus Default-Baudrate auf 4800 gesetzt, passend zur Display-CONFIG (`R1=02`).
- Button **Log löschen** ergänzt; leert nur das sichtbare Logfenster, Raw-Datei und Registerwerte bleiben erhalten.

## V0.2.35 PRIVATE Fix1

- WP-Steuerung-Popup liest beim Öffnen automatisch die benötigten Werte.
- WP-Steuerung-Popup: Autorefresh-Checkbox mit einstellbarem Intervall ergänzt.
- Button **Status/Livewerte lesen** übernimmt anschließend automatisch die gelesenen Livewerte in die Anzeige.
- Bereich **Wärmepumpe Ein / Aus** klarer benannt.
- In Kombimodi **Warmwasser + Heizen** und **Warmwasser + Kühlen** kann der zusätzliche WW-Sollwert über Register 1157 angezeigt und geschrieben werden.
- AT-Kompensation-Popup liest beim Öffnen automatisch die benötigten Werte und hat ebenfalls Autorefresh.
- AT-Kompensation zeigt die Kurve zusätzlich als einfache Grafik/Canvas an; Tabelle bleibt zur Kontrolle erhalten.

## V0.2.35 PRIVATE

- Private-Version auf Basis von V0.2.34 erstellt.
- Neue Funktion **WP-Steuerung ...**: Ein/Aus, Modus setzen, Betriebsstatus anzeigen, wichtige Temperaturen/Livewerte, passende Solltemperatur je Modus schreiben und Silent Mode über 1016 Bit 1 per Read-Modify-Write schalten.
- Neue Funktion **AT-Kompensation ...**: H36/1236 aktivieren/deaktivieren, Slope 1234 und Offset 1235 lesen/schreiben, aktuelle Außentemperatur/kompensierte Solltemperatur anzeigen und Kurventabelle aus App-Formel darstellen.
- Register-/KB-Korrekturen: 2043 und 2062 als Voltwerte, 2063 als °C/TEMP1; 1012 sauber als Einstellmodus, 2012 als aktueller Betriebsstatus dokumentiert.
- Splash weiter gegen Theme-Mischfarben abgesichert.
- README um SmartScreen-Hinweis ergänzt.

## V0.2.34 PUBLIC

- Theme-Fix: Darstellung **System / Hell / Dunkel** ergänzt; Windows-Appmodus wird bei System erkannt. Hellmodus wieder näher am alten hellen Layout, Log/Konsole hell. Dunkelmodus mit dunkler Haupt-Registertabelle.
- Splash/Startlogo separat gestylt, damit keine gemischten Theme-Farben übernommen werden.
- Public-Zusatz aus Titelleiste/About/Splash entfernt; nur PRIVATE-Versionen werden sichtbar markiert.
- Geräte-/Modellinfo aus der Verbindungs-Kopfzeile entfernt; Auswahl bleibt in den Programm-Einstellungen.
- Update-Asset-Auswahl verbessert: Setup/Portable werden anhand Namen und Einstellung gewählt; Source-ZIPs werden ignoriert.
- Bedienbereich: **Init-Blöcke lesen** in **Alle bekannten Register lesen** umbenannt und über dem Register-Lesen/Schreiben platziert.
- Kontaktdecoder und Lastausgangdecoder in Schreibweise/Benennung vereinheitlicht.
- Störmelde-/Fehlertexte für Fehlerregister 1–9 ergänzt und Schreibweisen korrigiert: Sauggastemperaturfehler, Winter-Frostschutz Stufe 1/2.

## V0.2.33 PUBLIC

- Eigenes App-Theme ergänzt: Standard ist Hell/Fusion, damit Windows-Darkmode keine unleserlichen Tabellen/Popups mehr verursacht; Dunkel ist optional vorbereitet.
- Programm-Einstellungen erweitert: Auto-Read Init on Startup, Livewerte-Auto-Poll ab 20xx mit Intervall, Parameterblock-Auto-Poll mit Intervall. Einstellungen werden persistent gespeichert.
- Parameterfenster: T-Block als Diagnose/Live markiert, bleibt aber weiterhin am Ende der Blockreihenfolge H A F D E R P G C Z ... T.
- Diagnose-/T-Werte ergänzt/korrigiert: 2054 Unit Power = kW /10, 2059 Unit Capacity = kW /10, 2060 COP = /100, 2065 Verdampfung, 2066 Exhaust Superheat, 2067 Suction Superheat, 2077 Durchfluss = m³/h /100.
- Knowledge Base erweitert: Hinweise zur Ableitung und Diagnosebedeutung von 2065-2067, inkl. Beobachtung 2066 ≈ Heißgas minus WP-Austritt/Kondensator-Referenz.
- README ergänzt: Standard-Modbus und Warmlink-Modbus sind getestet; HMI-/Display-Modbus ist noch ungetestet. Kaskaden-Hinweis für mögliche mehrere Slave-Adressen am HMI-/Display-Modbus ergänzt.

## V0.2.32 PUBLIC

- Public-Version aus dem letzten PRIVATE V0.2.32 Stand erstellt.
- Edition auf PUBLIC gesetzt; neutrale Public-Defaults bleiben aktiv: Host leer, Standard-Modbus als Default, Autoconnect aus.
- Update-Repo bleibt auf dosordie/FoxAir_Control korrigiert.
- Parameterfenster-Sortierung wie Warmlink-App: H, A, F, D, E, R, P, G, C, Z; Temperatur/T bleibt am Schluss.
- Hilfe/About bereinigt: kein doppelter Hilfe-Button, About rechts in der Kopfzeile, F1 bleibt aktiv.
- E-, R-, P-, G-, C- und Z-Block anhand der Warmlink-App-Videos ergänzt/korrigiert.
- Live bestätigte Registerkorrekturen übernommen: 1437 = D30, 1438 = P15, 1444 = P16, 1347 = C12, 1236 = H36, 1046 = H37.
- Manuelles Register-Lesen zeigt FC03-Antworten wieder direkt im Popup an und loggt die Werte als READ Werte.
- KB-Notiz für EEV-Smart-Modus als Vermutung/noch nicht verifiziert ergänzt.

### PRIVATE V0.2.32 - Korrektur H36/H37/Z16 (ohne Versionsanhebung)
- Register 1236 wieder korrekt als H36 / AT-Kompensationskurve Zone 1 aktivieren geführt; Z16-Duplikat entfernt.
- Register 1046 als H37 bestätigt; Register 1048 nicht mehr als H37 benannt.
- Knowledge-Base Hinweise zu H36/H37/Z16 ergänzt.


## V0.2.32 PRIVATE - Z-Block Video-Update

- Z-Block aus Warmlink-App-Video ergänzt/korrigiert.
- Z01-Z17 sowie Z19/Z20 mit App-Bezeichnungen, Einheiten/Typen und sichtbaren Defaults gepflegt.
- Z18 bewusst nicht angelegt: in App nicht sichtbar; ASM-Hinweis nennt Z18 gelöscht, Z19/Z20 ergänzt.
- Register 1236 wird für die Parameteransicht als Z16 geführt; vorherige H36/Weather-Compensation-Herkunft ist in der Wissensdatenbank notiert.
- Version nicht angehoben.


## V0.2.32 PRIVATE

- PRIVATE-Version auf Basis von V0.2.31 PUBLIC erstellt.
- App-Version auf 0.2.32 und Edition auf PRIVATE gesetzt.
- Private Default-IP wieder auf 192.168.10.43 gesetzt.
- Update-Repo auf dosordie/FoxAir_Control korrigiert, damit der Control/Controll-Versionsmismatch nicht mehr greift.
- Doppelten Hilfe-Button entfernt: Hilfe/About bleibt nur im Menü „Hilfe“ und per F1 erreichbar.
- Parameterblock-Reihenfolge im Fenster „Parameter Einstellungen“ an die Warmlink-App angepasst: A, F, D, E, R, P, G, C, Z; Temperatur/T bleibt am Schluss.
- Video 1: E-Block/EEV und R-Block Bezeichnungen, Einheiten und App-Werte ergänzt/korrigiert.
- Video 2: P-Block (Pumpen/Nachfüllung), G-Block (Desinfektion) und C-Block (Kompressor) Bezeichnungen, Einheiten und App-Werte ergänzt/korrigiert.
- Neue Anzeige-/Datentypen ergänzt: Hz, Sekunden, Stunden und Tage.
- C12 „Max. Comp. Frequency in DHW mode“ anhand Warmlink-App und ASM-Adresse 0543H/1347 ergänzt; Register 1347 zusätzlich live bestätigt.
- Korrektur nach Live-Test: 1437 ist D30 „Gehaeusewannenheizung Delays Off Time after Defrost“ und nicht P15.
- Korrektur nach Live-Test: P15 = Register 1438, P16 = Register 1444.
- Manuelles „Register lesen/schreiben“-Popup zeigt FC03-Antworten jetzt direkt im Popup an und loggt die gelesenen Werte zusätzlich als „READ Werte“.
- KB-Notiz für EEV-Smart-Modus ergänzt: Smart vermutlich erweiterte Auto-Regelung, E19 begrenzt wahrscheinlich den Korrekturbereich.

## V0.2.31 PUBLIC

- F1 Hilfe/About-Dialog ergänzt.
- About-Dialog zeigt Version, Build-Datum, kleines Logo, GitHub-Link und Warnhinweis.
- Update-Prüfung in den About-Dialog verschoben.
- Button im Hauptfenster: „Hilfe / About ...“.
- Kommunikationsmodi umbenannt:
  - Modbus Warmlink LTE
  - Modbus Display
  - Modbus Standart
- Public-Default jetzt Modbus Standart.
- Backup/Restore-Laden/Speichern mit besserem Busy-Status und weniger blockierenden Tabellenupdates.
- README erweitert: Setup/Portable als erste Installationsart und kurze Erklärung der Modbus-Anschlüsse.

## V0.2.30 PUBLIC

- Schreibweise von Controll auf Control korrigiert.
- GitHub-Update-Check auf dosordie/FoxAir_Control umgestellt.
- Hauptdatei auf foxair_phnix_control.py umbenannt.
- Build-/Installer-/Release-Dateinamen auf FoxAir_Phnix_Control umgestellt.
- Public-Version mit AppData-Speicherort fuer Settings/Cache/Knowledge/Backups/Raw-Logs.
- Fix: Host/IP und Programmeinstellungen werden in Setup- und Portable-Build korrekt gespeichert.
- Speichern der Settings erfolgt atomar ueber temporaere Datei.
- Kommunikation-Dialog zu Programm-Einstellungen umbenannt.
- Update-Pruefung in Programm-Einstellungen abrufbar.
- Automatische Update-Pruefung beim Start der Public-Version.
- Neutrale Public-Defaults: Host leer, Autoconnect aus.


## V0.2.28 PRIVATE

- User-/Arbeitsdateien bevorzugt im Programm-/EXE-Ordner statt im PyInstaller-_internal-Ordner.
- Backup-Vorschlagsordner und Raw-Logs ebenfalls im Programm-/Arbeitsordner.
- Hinweis-Banner im Hauptfenster in Kommunikationseinstellungen abschaltbar.
- Bessere Meldung bei fehlenden Schreibrechten unter Program Files.


## v0.2.26

Public-Prep-Version.

- README.md ergänzt
- LICENSE ergänzt
- PUBLIC_WARNING.txt ergänzt
- neutrale Default-IP / Host leer beim ersten Start
- Warnhinweis im Hauptfenster
- Windows-Build-Skripte ergänzt
- GitHub-Actions-Workflow für Release-Build ergänzt

## v0.2.25

- Neues App-/Fenster-/Taskleisten-Icon eingebaut

## v0.2.24

- falsche Defaultwerte bereinigt
- F10/Lüfteranzahl mit Geräte-Defaults ergänzt

## v0.2.23

- KG / WP Ein-Aus-Timer aus Parameter-Einstellungen entfernt

## v0.2.22

- JSON-Struktur bereinigt: name/code/block getrennt
- Geräteauswahl in Kommunikationseinstellungen verschoben
- Init-Blöcke lesen vereinfacht

## v0.2.21

- Geräteauswahl für Defaultwerte ergänzt

## v0.2.20

- Wissensdatenbank in separate foxair_phnix_knowledge.json ausgelagert
- Beschreibungen editierbar

## v0.2.19

- Tooltip-/Beschreibungsfunktion für Datenpunkte ergänzt

## v0.2.18

- Splash auf 8 Sekunden, X zum Schließen, Build-Datum fest

## v0.2.17

- Branding und Splash ergänzt

## v0.2.15

- Backup/Restore für Parameterbereiche ergänzt

## V0.2.37 Fix21

- Display-Paketblock-Test erweitert: testet sequenziell jetzt auch Unit `0x02` und `0x05` zusätzlich zu `0x03`, `0x01`, `0x04`.
- Unit `0x00` wird in der Busübersicht nicht mehr als ungültige Adresse bezeichnet, sondern als Modbus-Broadcast/System-Adresse.
- Unit `0x00` wird bewusst nicht aktiv gepollt, weil Broadcast-Reads keine normale Antwort erwarten lassen. Passive Broadcast-Paketblöcke `2001ff`/`2091ff` bleiben unverändert validiert und übernommen.

## PRIVATE V0.2.38 fix5

- Modbus Display: neue PRIVATE-Experimente in der Seitenleiste:
  - **Display Reboot Fake**: setzt Unit 3 / `5112H=0` und danach `0BC3H=8000H`, damit der echte Master wie beim Display-Neustart die Parameterblöcke ans Display schreiben soll.
  - **Display-Wert simulieren**: nutzt den zuletzt gesehenen vollständigen Display-Paketblock, ändert genau ein Register im Block, schreibt den kompletten Block per FC16 an Unit 3 und setzt anschließend das passende `0BC3`-Maskenbit.
  - Schnellbuttons für `1012=1` (Heizen) und `1012=2` (Kühlen).
- FC16-Block-Write für 90er Display-Paketblöcke ergänzt.
- Erwarteter echter Display-Pfad aus den RAW-Logs umgesetzt: `1001ff` wird als kompletter Block gelesen/geschrieben, `0BC3` signalisiert die Änderung (`1001`-Paket: `0x0002`; Reboot/Power-On: `0x8000`).
