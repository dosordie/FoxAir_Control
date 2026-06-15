# FoxAir / Phnix Control

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.

> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- Lesen und Schreiben per Modbus Standart, Modbus Display und Modbus Warmlink LTE
- TCP/IP/ser2net oder USB-RS485/COM-Port
- F1 Hilfe/About mit Version, GitHub-Link und Update-Prüfung
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder
- Offline Register-Browser mit editierbarer Wissensdatenbank

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
| Modbus Display | TCP/IP oder COM/RS485 | Bus, der zum Display / DWIN-HMI geht | meist Unit 3, optional +0x2000 für Parameter |
| Modbus Warmlink LTE | TCP/IP/ser2net oder COM/RS485 | Modem-/Warmlink-Bus im Außengerät, an den Klemmen am Mainboard | Bus 0x63, RAW-Protokoll |

Kurz gesagt:

- **Standart** = die offiziellen Modbus-Klemmen am Gerät.
- **Display** = der Bus, der zum Display geht.
- **Warmlink LTE** = nur im Außengerät vorhanden, an den Klemmen am Mainboard / Modem-Bus.


### Verbindungsstatus / Teststand

- **Modbus Standart** ist getestet.
- **Modbus Warmlink LTE** zum LTE-/Warmlink-Modem ist getestet.
- **Modbus Display / HMI** ist aktuell noch ungetestet und sollte vorsichtig verwendet werden.

Hinweis fuer Kaskaden: Bei Kaskadenanlagen koennten am **HMI-/Display-Modbus** mehrere Geraete mit unterschiedlichen Slave-Adressen haengen. Das ist noch nicht verifiziert, wird aber fuer spaetere Bus-Scan-/Mehrgeraete-Funktionen vorgemerkt.

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





### PUBLIC V0.2.35 Hinweise

- Public-Version aus dem letzten PRIVATE V0.2.35 Fix1 Stand.
- Enthält WP-Steuerung-Popup, AT-Kompensations-Popup mit Kurvengrafik, Silent-Steuerung über 1016 Bit 1 und die Fix1-Aktualisierungen.
- Public wird in der Oberfläche nicht extra markiert; nur PRIVATE-Versionen tragen den PRIVATE-Zusatz.
- Hinweis für Releases: Source-ZIP und EXE/Setup sind getrennte Assets. Wenn nur das Source-ZIP aktualisiert wird, bleibt eine vorhandene EXE im GitHub-Release unverändert. Für Updates der EXE muss die EXE/Setup-Datei aus diesem Source-Stand neu gebaut und als Release-Asset hochgeladen werden.

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
