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
git tag v0.2.33
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
