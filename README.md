# FoxAir / Phnix Controll

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.

> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- Lesen und Schreiben per Warmlink RAW, Standard Modbus und Display Modbus
- TCP/IP/ser2net oder USB-RS485/COM-Port
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder
- Offline Register-Browser mit editierbarer Wissensdatenbank

## Unterstützte Verbindungstypen

| Modus | Transport | Hinweis |
|---|---|---|
| Warmlink RAW | TCP/IP oder COM | bisheriger Hauptmodus |
| Standard Modbus | TCP/IP oder COM | typischerweise Unit 1 |
| Display Modbus / DWIN | TCP/IP oder COM | typischerweise Unit 3, optional +0x2000 |

## Unterstützte Geräteauswahl für Defaultwerte

Die Geräteauswahl beeinflusst nur die Anzeige und Pflege von Defaultwerten in der Wissensdatenbank.

- FoxAir Green Line GL9-1
- FoxAir Green Line GL15-3
- FoxAir Green Line GL22-3
- FoxAir Blue Line BL8-1
- FoxAir Blue Line BL12-3
- FoxAir Blue Line BL23-3

GL = R290, BL = R32.

## Installation mit Python

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
dist\FoxAir_Phnix_Controll_Portable\
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
git tag v0.2.26
git push origin main --tags
```

Die enthaltene GitHub-Actions-Workflow-Datei kann auf Windows automatisch ein Portable-ZIP und optional den Installer bauen und als Release-Artefakte hochladen.

## Dateien

| Datei | Zweck |
|---|---|
| `foxair_phnix_controll.py` | GUI |
| `foxair_phnix_core.py` | Kommunikation/Parser |
| `foxair_phnix_registers.json` | technische Registerdaten |
| `foxair_phnix_knowledge.json` | Beschreibungen, Hinweise, Defaults |
| `app_icon.png` / `app_icon.ico` | App-, Fenster- und Taskleisten-Icon |
| `tools/modbus_sniffer_plus.py` | Zusatztool/Sniffer |

## Haftung

Dieses Tool kann Register schreiben. Falsche Werte können Störungen, Fehlfunktionen oder unerwünschtes Anlagenverhalten verursachen. Nutzung nur, wenn klar ist, was geändert wird. Vor jedem Restore oder Schreiben ein Backup erstellen.
