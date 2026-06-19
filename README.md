# FoxAir / Phnix Control PUBLIC V0.2.45

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.

> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern oder Cloud-Werten kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.

## PUBLIC V0.2.45 – Cloud-only-Schalter bereinigt

Diese Public-Version enthält weiterhin die WarmLink/Linked-Go-Cloud-Funktionen aus der bisherigen PRIVATE V0.2.44 fix4 und bereinigt die Cloud-only-Bedienung:

- Cloud-Login mit gespeicherter E-Mail und Passwort im OS-Keyring (`keyring>=25.0`)
- Cloud-Geräte-/Device-ID-Anzeige
- Cloud-Polling, Overlay und Cloud-Spalten im Hauptfenster
- Cloud-Wertefinder
- Cloud-Schreibtest mit bestätigtem Endpunkt `app/device/control?lang=en`
- Rechtsklick **Wert per Cloud schreiben ...** für bekannte schreibbare Cloud-Codes
- **Cloud-only Zeilen** gibt es nur noch im WarmLink-Cloud-Fenster; dort ist der Schalter standardmäßig aktiviert
- Log-Spam-Reduktion für stark wiederholte Display-Bus-Frames, z. B. `0x02 / 3001`

### Quellen / Attribution

WarmLink/Linked-Go-Cloud-Erkenntnisse und Mapping-Ideen basieren unter anderem auf öffentlicher Recherche und öffentlich verfügbaren Projekten, insbesondere:

- `srbjessen/ha-warmlink`
- `00gtw00/homeassistant_warmlink`
- ursprüngliche Reverse-Engineering-Hinweise, soweit dort genannt, z. B. `zyznos321/warmlink`

Die App enthält eigenen Code; fremde Quellen werden im Code/README genannt, damit Attribution und Lizenzhinweise nachvollziehbar bleiben.

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- WarmLink/Linked-Go Cloud: Login, Geräteübersicht, Statuswerte, Overlay, Wertefinder und Schreiben bekannter Cloud-Codes
- Lesen und Schreiben per Modbus Standart, Modbus Display und Modbus Warmlink LTE
- TCP/IP/ser2net oder USB-RS485/COM-Port
- F1 Hilfe/About mit Version, GitHub-Link und Update-Prüfung
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder
- Offline Register-Browser mit Umschaltung zwischen Warmlink/WP- und Display/DWIN-Mapping



### PRIVATE V0.2.38 fix12 – Display-Zusatzwerte im Hauptfenster

Im Backend **Modbus Display** werden jetzt zusätzlich die vom WP-Master abgefragten DWIN-/Displaywerte ab `3000` im Hauptfenster sichtbar gemacht, z. B. `3001ff`, `3011/0BC3` und `3021`. Diese Werte nutzen weiter das getrennte Display-/DWIN-Mapping, erscheinen aber nun in der normalen Registertabelle, damit Kandidaten fuer Anzeige-/Icon-/Statuswerte leichter beobachtet werden koennen.

Bus-Teilnehmer `0x04` und `0x05` werden nur dann in die Hauptliste übernommen, wenn deren Registerbereich nicht mit bekannten WP-/Warmlink-Registern kollidiert. Bekannte Paket-/Statusbereiche wie `1001ff` oder `2000ff` bleiben fuer diese Fremdteilnehmer Diagnose, damit keine echten WP-Werte überschrieben werden. Warmlink und Standard-Modbus sind davon nicht betroffen.

### PRIVATE V0.2.38 fix11 – Display-Snapshot

Im Backend **Modbus Display** ist **Display Reboot Fake** jetzt die Standard-Snapshot-Methode für **Alle bekannten Register lesen**. Die App setzt dabei `5112H=0` und `0BC3H=8000H` ACK-gesteuert, damit der echte Master die Parameterpakete wieder an Unit `0x03` schreibt.

Der PRIVATE Display-Testbereich ist in der normalen UI ausgeblendet, bleibt aber im Code erhalten. Manuelle FC03-Reads bleiben weiterhin direkt möglich, damit gezielte `qty=90`-Reads weiter getestet werden können. Warmlink und Standard-Modbus sind davon nicht betroffen.


### PRIVATE V0.2.38 fix9 – Display-Schreiben

Im Backend **Modbus Display** werden normale Schreibbefehle auf bekannte Display-Parameterpaket-Nutzwerte automatisch ueber den Bedienwertpfad ausgefuehrt. Beispiel: Ein normaler Write auf `1012=2` wird nicht direkt in den Paketblock geschrieben, sondern als `23F4=2` an Unit `0x03` gesendet. Danach wartet die App auf das vom Display gesetzte `0BC3`-Modified-Flag und den Master-Read des passenden Parameterpakets.

Damit profitieren auch Rechtsklick-Write und Popups wie WP-Steuerung, Timer- und Parameterfenster. Mehrere Writes werden intern in eine ACK-gesteuerte Warteschlange gelegt.

## Installation / Download

Für normale Windows-Nutzer sind die GitHub-Release-Downloads der einfachste Weg:

1. **Setup-EXE** herunterladen und installieren.  
   Erstellt Startmenü-/optional Desktop-Verknüpfung und kann spätere Versionen überinstallieren.
2. **Windows Portable ZIP** herunterladen, entpacken und EXE starten.  
   Ohne Installation, gut für Tests oder portable Nutzung.

Python-Start ist weiterhin möglich, aber eher für Entwicklung/Tests gedacht.

## Unterstützte Verbindungstypen / „Modbusse“

| Modus | Transport | Was ist das? | Typisch |
|---|---|---|---|
| Modbus Standart | TCP/IP oder COM/RS485 | Offizielle Modbus-Klemmen am Gerät | Unit 1, Port 10001 bei TCP-Gateway |
| Modbus Display | TCP/IP oder COM/RS485 | Bus, der zum Display / DWIN-HMI geht | 4800 8N1 laut Display-CONFIG, meist Unit 3, optional +0x2000 für DWIN-Speicher |
| Modbus Warmlink LTE | TCP/IP/ser2net oder COM/RS485 | Modem-/Warmlink-Bus im Außengerät, an den Klemmen am Mainboard | Bus 0x63, RAW-Protokoll |

Kurz gesagt:

- **Standart** = die offiziellen Modbus-Klemmen am Gerät.
- **Display** = der Bus, der zum Display geht.
- **Warmlink LTE** = nur im Außengerät vorhanden, an den Klemmen am Mainboard / Modem-Bus.


### Verbindungsstatus / Teststand

- **Modbus Standart** ist getestet.
- **Modbus Warmlink LTE** zum LTE-/Warmlink-Modem ist getestet.
- **Modbus Display / HMI** wurde inzwischen passiv mitgeschnitten. Baudrate/Format: sehr wahrscheinlich **4800 8N1**. Der Bus enthält mehrere Teilnehmer/Platinen und ist für aktives Steuern deutlich schwieriger als Warmlink. Für aktives Lesen/Schreiben bleibt Warmlink aktuell die bevorzugte Variante.

Aktueller DWIN-Diagnosestand:

- Warmlink/WP-Register und Display/DWIN-Adressen sind getrennt. Der normale Registerbrowser bleibt Warmlink/WP; im Offline-Registerbrowser kann auf Display/DWIN-Mapping umgeschaltet werden.
- Display-Bus-Parameterpakete von Unit `0x03` werden mit WP-/Warmlink-Mapping dekodiert; zusätzliche DWIN-/Displaywerte ab `3000` erscheinen in PRIVATE fix12 im Hauptfenster. Fremdteilnehmer `0x04`/`0x05` werden nur kollisionsfrei übernommen.
- `3021` / `0x0BCD` im Block `0x03 / 3001ff` ist ein Kandidat für Display-Istmodus / Anzeige-Icon-Code. Der Wert wird bewusst **nicht** automatisch als `2012` übernommen.
- `3013` wurde als Display-Softwareversion bestätigt/beobachtet: `17` = V1.7.
- Für sichtbare Display-Temperaturen wie T1/T2/T4 gibt es im manuellen Register-Popup jetzt die Buttons **DWIN Temp-Suche** und **DWIN Status-Suche**. Diese lesen Anzeigeadressen auf Unit `0x03`, z. B. `0x1270`, `0x127C`, `0x1800`, `0x1880`, `0x1A00`, `0x11C0`, `0x1720`, `0x1730`.
- Ziel der Temp-Suche: Werte wie `206`, `210`, `170` oder ggf. direkt `20`, `21`, `17` finden, wenn das Display T1/T2/T4 anzeigt.

Aktuelle Display-/HMI-Bus-Vermutungen aus Mitschnitten:

| Adresse | Vermutung | Beobachtet |
|---|---|---|
| 0x01 | Live-/Status-Teilnehmer | 1999/2099, FC03/FC16 |
| 0x02 | DWIN-/Display-Speicher Teilnehmer | 3001ff Reads |
| 0x03 | Display / DWIN-DGUS Speicher | 3001ff, +0x2000 relevant |
| 0x04 | Parameterblock-Poller | 1011ff Reads |
| 0x05 | interner Parameter-/Liveblock | 2000ff Reads, 1001-1090 Writes |
| 0x06 | Testadresse | bisher keine gesicherte Rolle |

Wichtig: Auf dem Display-/HMI-Bus werden passive Frames und manuelle DWIN-Lesungen **nicht mehr automatisch in die Haupt-Registerliste übernommen**. Die Hauptliste bleibt Warmlink/WP-Mapping. Display-/DWIN-Adressen werden getrennt über `foxair_phnix_display_registers.json` nur für Popup/Log-Diagnose beschriftet. Damit überschreiben Rohblöcke wie `0x01/2099ff` keine bekannten Warmlink-Register ab 2101 mehr.

Hinweis zu **1999/2001 / 20xx** im Display-/HMI-Modbus: diese Blöcke sind noch nicht sauber verifiziert. FC16-ACKs und unklare 1999/2001-Frames werden deshalb nur noch geloggt, aber nicht in die Hauptliste übernommen. **2012** wird im Display-Modbus nicht mehr aus 1012 gespiegelt, weil 1012 Sollmodus und 2012 Ist-/Betriebsstatus mit unterschiedlicher Codetabelle sind. Für echte/saubere Istwerte bleibt Warmlink die bessere Quelle.

Hinweis fuer Kaskaden: Bei Kaskadenanlagen koennten am **HMI-/Display-Modbus** mehrere Geraete mit unterschiedlichen Slave-Adressen haengen. Das ist noch nicht verifiziert, wird aber fuer spaetere Bus-Scan-/Mehrgeraete-Funktionen vorgemerkt.


### PRIVATE V0.2.38 fix8 – Display-Experiment Hinweise

Die PRIVATE-Buttons im Bereich **Display-Experimente** arbeiten jetzt ACK-gesteuert:

- **Display Reboot Fake** setzt `5112H=0` und danach `0BC3H=8000H`. Beide Writes werden auf ACK von Unit `0x03` geprüft. Wenn `0BC3` beim nächsten `3001/3011`-Poll nicht sichtbar wird, wird nur `0BC3` erneut gesetzt.
- **Display-Wert testen** schreibt die gewählte Variante sequenziell und wartet je Schritt auf ACK. Erst danach wird auf `0BC3` und den Master-Read des betroffenen Paketblocks gewartet.
- Variante **B** ist der bevorzugte Bedienweg: `Register+0x2000` / Benutzerwert plus `0BC3`-Maske. Wenn B nicht greift, versucht die App automatisch Variante **C** als Fallback.
- Schnellbuttons für Modus `1012`: **WW=0**, **Heizen=1**, **Kühlen=2**.

## Unterstützte Geräteauswahl für Defaultwerte

Die Geräteauswahl beeinflusst nur die Anzeige und Pflege von Defaultwerten in der Wissensdatenbank.

- FoxAir Green Line GL9-1
- FoxAir Green Line GL15-3
- FoxAir Green Line GL22-3
- FoxAir Blue Line BL8-1
- FoxAir Blue Line BL12-3
- FoxAir Blue Line BL23-3

GL = R290, BL = R32.

## Installation mit Python / Entwicklung

1. Python 3.11, 3.12 oder 3.13 64-Bit installieren.
2. ZIP entpacken.
3. Im Programmordner ausführen:

```bat
py -m pip install -r requirements.txt
```

4. Starten:

```bat
start_gui.bat
```

Bei Problemen:

```bat
start_gui_debug_console.bat
```

## Windows-EXE bauen

Auf einem Windows-Rechner:

```bat
py -m pip install -r requirements.txt
py -m pip install -r requirements-build.txt
build_windows_exe.bat
```

Das portable EXE-Paket liegt danach unter:

```text
dist\FoxAir_Phnix_Control_Portable\
```

## Windows-Setup bauen

Nach dem EXE-Build kann mit Inno Setup ein Installer gebaut werden:

```bat
build_windows_setup.bat
```

Voraussetzung: Inno Setup 6 ist installiert.

## GitHub Release

Empfohlener Ablauf:

```bat
git tag v0.2.34
git push origin main --tags
```

Die enthaltene GitHub-Actions-Workflow-Datei kann auf Windows automatisch ein Portable-ZIP und optional den Installer bauen und als Release-Artefakte hochladen.

## Dateien

| Datei | Zweck |
|---|---|
| `foxair_phnix_control.py` | GUI |
| `foxair_phnix_core.py` | Kommunikation/Parser |
| `foxair_phnix_registers.json` | technische Registerdaten |
| `foxair_phnix_knowledge.json` | Beschreibungen, Hinweise, Defaults |
| `app_icon.png` / `app_icon.ico` | App-, Fenster- und Taskleisten-Icon |
| `tools/modbus_sniffer_plus.py` | Zusatztool/Sniffer |

## Haftung

Dieses Tool kann Register schreiben. Falsche Werte können Störungen, Fehlfunktionen oder unerwünschtes Anlagenverhalten verursachen. Nutzung nur, wenn klar ist, was geändert wird. Vor jedem Restore oder Schreiben ein Backup erstellen.

### Updates

Die Public-Version prüft beim Start automatisch die neueste GitHub-Release-Version.
Manuell geht das über **F1 / Hilfe → About → Update prüfen ...**.
Wenn eine neue Version vorhanden ist, wird ein Download-Link zur Setup-EXE bzw. Portable-ZIP angezeigt.
Die Setup-EXE kann später über eine vorhandene Installation drüber installiert werden.

### Speicherort der Einstellungen

Bei Installation per Setup werden Benutzerdaten unter `%APPDATA%\FoxAir Phnix Control\` gespeichert.
Das vermeidet Schreibfehler unter `C:\Program Files`.
Portable/private Versionen koennen weiterhin alles im Programmordner speichern. Die Public-Version startet mit leerem Host und Standard-Modbus als Vorgabe.





### PRIVATE V0.2.37 Fix2 Hinweise

Display-/HMI-Modbus übernimmt zusätzlich den Statusblock `Addr 0x01 / 1999ff`.
Dadurch können Werte wie `2011` und `2012` aus den passiven Statuspaketen sichtbar werden.
Parameterpakete von `Addr 0x03 / 1001ff` bleiben weiterhin aktiv, damit `1012` beim Umschalten am Display mitläuft.

### PRIVATE V0.2.35 Fix1 Hinweise

- Die Popups **WP-Steuerung ...** und **AT-Kompensation ...** laden beim Öffnen automatisch die benötigten Register.
- Beide Popups besitzen eine optionale **Autorefresh**-Funktion.
- Im WP-Steuerung-Popup aktualisiert **Status/Livewerte lesen** die Anzeige automatisch, sobald Werte eingehen.
- Bei Kombimodi mit Warmwasser ist zusätzlich der **WW-Sollwert Register 1157** editierbar.
- Die AT-Kompensationskurve wird zusätzlich grafisch angezeigt.

### PRIVATE V0.2.35 Hinweise

- Neue Popups: **WP-Steuerung ...** und **AT-Kompensation ...**.
- WP-Steuerung trennt klar zwischen **1012 Modus setzen** und **2012 aktuellem Betriebsstatus**.
- Silent Mode wird über **1016 Bit 1 / Maske 0x0002** gelesen und per Read-Modify-Write geschrieben.
- AT-Kompensation nutzt **1236 / H36** als Aktiv-Schalter, **1234** als Slope und **1235** als Offset. Die Kurve wird nach der aus der App abgeleiteten Formel `Ziel = Offset - Slope × AT` mit Mindestbegrenzung angezeigt.
- Korrekturen: **2043 = V**, **2062 = V**, **2063 = °C**.

### Windows SmartScreen Hinweis

Da FoxAir / Phnix Control aktuell nicht digital signiert ist, kann Windows beim ersten Start eine SmartScreen-Warnung anzeigen, z. B. **"Der Computer wurde durch Windows geschützt"**.

Zum Starten:

1. **Weitere Informationen** anklicken.
2. **Trotzdem ausführen** auswählen.

Die Warnung erscheint typischerweise bei unbekannten bzw. nicht signierten EXE-Dateien. Sie bedeutet nicht automatisch, dass die Datei gefährlich ist. Bitte Releases nur aus dem offiziellen GitHub-Release herunterladen.

### PUBLIC V0.2.34 Hinweise

- Theme-Fix: Darstellung kann jetzt **System / Hell / Dunkel** nutzen. Bei System wird unter Windows der App-Modus aus der Registry erkannt. Hell soll wieder wie der frühere helle Standard aussehen; Dunkel nutzt konsequent dunkle Tabellenfarben.
- Haupt-Registertabelle im Dunkelmodus korrigiert; helle Zeilen mit heller Schrift werden vermieden. Log/Konsole ist im Hellmodus wieder hell.
- Splash/Startlogo wird separat gestylt und übernimmt keine gemischten Systemfarben mehr.
- Public wird in Titelleiste/About/Splash nicht mehr angezeigt; nur PRIVATE-Versionen bekommen eine sichtbare PRIVATE-Markierung.
- Kopfzeile bereinigt: Geräte-/Modellinfo wird nicht mehr neben der aktuellen Verbindung angezeigt, sondern bleibt in den Programm-Einstellungen.
- Update-Download verbessert: Setup/Installer und Portable werden anhand Release-Asset-Namen bzw. Einstellung **Automatisch / Portable / Setup** ausgewählt; Source-ZIPs werden ignoriert.
- Button **Init-Blöcke lesen** umbenannt in **Alle bekannten Register lesen** und im Bedienbereich über dem Register-Lesen/Schreiben platziert.
- Kontaktdecoder und Lastausgangdecoder wurden in Schreibweise/Benennung vereinheitlicht.
- Störmelde-/Fehlertexte für Fehlerregister 1–9 ergänzt; Schreibweisen geglättet, z. B. Sauggastemperaturfehler sowie Winter-Frostschutz Stufe 1/2.

### PUBLIC V0.2.33 Hinweise

- Eigenes helles Standard-Theme: Windows-Darkmode erzeugt keine unleserlichen Tabellen/Popups mehr. Optional kann in den Programm-Einstellungen auf Dunkel umgestellt werden.
- Auto-Funktionen in den Programm-Einstellungen:
  - Init-Blöcke nach erfolgreicher Verbindung automatisch lesen.
  - Livewerte ab 20xx zyklisch pollen.
  - Parameterblock im Einstellfenster zyklisch pollen.
  Die Einstellungen werden beim Programmende gespeichert.
- T-Block wird als Diagnose-/Livewert-Block behandelt, nicht mehr pauschal als Temperaturblock. In der Sortierung bleibt T weiter ganz am Schluss.
- Diagnosewerte ergänzt/korrigiert: 2054 Unit Power kW /10, 2059 Unit Capacity kW /10, 2060 COP /100, 2065 Verdampfung, 2066 Exhaust Superheat, 2067 Suction Superheat, 2077 Durchfluss /100 m³/h.
- KB-Hinweise zu 2065–2067 ergänzt: 2065 vermutlich aus Niederdruck berechnet, 2067 als wichtiger EEV-/Saugüberhitzungswert, 2066 vermutlich modellierter Wert aus Heißgas minus Kondensator-/WP-Austrittsreferenz.

### PUBLIC V0.2.32 Hinweise

- Das Fenster **Parameter Einstellungen** folgt bei den Block-Tabs jetzt der Warmlink-App-Reihenfolge: A, F, D, E, R, P, G, C, Z. Temperatur/T bleibt bewusst am Schluss.
- Der doppelte Hilfe-Button wurde entfernt; About sitzt rechts in der Kopfzeile, **F1** bleibt aktiv.
- Die Parameterblöcke P, G und C wurden anhand der Warmlink-App-Aufnahme ergänzt.
- P15/P16 sind live bestätigt: P15 = Register 1438, P16 = Register 1444.
- Achtung: Register 1437 ist live bestätigt D30 „Gehaeusewannenheizung Delays Off Time after Defrost“.
- EEV Smart-Modus ist in der Knowledge Base als Vermutung markiert, nicht als bestätigter Fakt.


### V0.2.32 PUBLIC Z-Block

Der Z-Block wurde anhand des Warmlink-App-Videos ergänzt. Die App-Reihenfolge im Parameterfenster bleibt H A F D E R P G C Z, Temperaturblock T am Schluss.


Hinweis V0.2.32: H36 ist Register 1236, H37 ist Register 1046. Register 1048 ist nicht mehr als H37 gekennzeichnet.


## V0.2.37 Fix21

- Display-Paketblock-Test erweitert: testet sequenziell jetzt auch Unit `0x02` und `0x05` zusätzlich zu `0x03`, `0x01`, `0x04`.
- Unit `0x00` wird in der Busübersicht nicht mehr als ungültige Adresse bezeichnet, sondern als Modbus-Broadcast/System-Adresse.
- Unit `0x00` wird bewusst nicht aktiv gepollt, weil Broadcast-Reads keine normale Antwort erwarten lassen. Passive Broadcast-Paketblöcke `2001ff`/`2091ff` bleiben unverändert validiert und übernommen.


## V0.2.37 Fix31

- Warmlink/LTE-Init-Lesen in `workers/warmlink_worker.py` ausgelagert.
- Neuer `WarmlinkInitReadController`: sendet die Init-Blöcke sequenziell und wartet auf Antwort oder Timeout.
- Fix für Warmlink-Timing: späte Antworten der letzten Statusblöcke können nicht mehr so leicht dem falschen Pending-Read zugeordnet werden.
- DisplayWorker-Timing verbessert: vor aktiven Display-Paketreads wird jetzt auf eine Buslücke gewartet; Timeout leicht erhöht.
- Warmlink/Standard-Lesepfad und DisplayWorker bleiben funktional getrennt.

### PRIVATE fix5 Display-Experimente

Im Backend **Modbus Display** gibt es in der Seitenleiste den Bereich **Display-Experimente PRIVATE**.

- **Display Reboot Fake** sendet an Unit 3 zuerst `5112H=0000H` und danach `0BC3H=8000H`. Erwartung: Der echte Master schreibt danach die Parameterblöcke `1001`, `1091`, `1181`, `1271`, `1361`, `1451` per FC16 an Unit 3 und löscht anschließend `0BC3` wieder auf `0`.
- **Display-Wert simulieren** benötigt einen vollständigen Paketblock im Cache, z. B. `1001-1090`. Der Block kommt normalerweise durch Display-Reboot, Display-Bedienung oder den Reboot-Fake herein. Das Tool ändert genau ein Register im Block, schreibt den ganzen Block per FC16 an Unit 3 und setzt danach das passende `0BC3`-Änderungsflag.
- Schnelltest Modus: **Heizen** setzt `1012=1`, **Kühlen** setzt `1012=2`. Der echte Status ist weiterhin im Broadcast `2012` zu beobachten.

Diese Funktionen sind Diagnose-/Experimentalfunktionen und sollten nur mit aktivem RAW-Log und kurzer Beobachtungszeit genutzt werden.
