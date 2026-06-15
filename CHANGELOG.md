# Changelog

## V0.2.35 PUBLIC
- Public-Version aus dem letzten PRIVATE V0.2.35 Fix1 Stand erstellt.
- Edition auf PUBLIC gesetzt; Public wird in der UI nicht sichtbar markiert.
- Hinweis: EXE-/Installer-Assets müssen im GitHub-Release separat aus diesem Source-Stand neu gebaut/hochgeladen werden; ein Source-ZIP aktualisiert keine bestehende EXE automatisch.

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