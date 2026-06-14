# Changelog

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