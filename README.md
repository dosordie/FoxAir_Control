## PUBLIC V0.2.39 Hinweis

Diese Public-Version basiert auf dem internen Stand **V0.2.38 fix11**.

**Neu gegenüber Public V0.2.38:** Der Display-/HMI-Bus ist nicht mehr nur passive Diagnose. Bekannte Parameterpaket-Nutzwerte können jetzt über den beobachteten Display-Bedienweg geschrieben werden: normale Registerwrites auf z. B. `1012` werden im Display-Backend automatisch als Benutzerwert `Register + 0x2000` gesendet, also `1012 -> 23F4`. Der direkte PRIVATE-Testbereich bleibt im Code vorhanden, ist in der Public-UI aber ausgeblendet.

**Wichtig:** Der Display-/HMI-Bus bleibt experimentell. Für sichere/produktive Änderungen bleiben **Modbus Standart** und **Modbus Warmlink LTE** die bevorzugten Wege. Vor Änderungen immer Backup erstellen.

# FoxAir / Phnix Control

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.

> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- Lesen und Schreiben per Modbus Standart und Modbus Warmlink LTE
- Experimentelle Display-/HMI-Unterstützung: passives Mithören, Snapshot per Reboot-Fake und ACK-gesteuertes Schreiben bekannter Parameterpaket-Nutzwerte
- TCP/IP/ser2net oder USB-RS485/COM-Port
- F1 Hilfe/About mit Version, GitHub-Link und Update-Prüfung
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder
- Offline Register-Browser mit Umschaltung zwischen Warmlink/WP- und Display/DWIN-Mapping

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
| Modbus Display | TCP/IP oder COM/RS485 | Bus, der zum Display / DWIN-HMI geht | 4800 8N1 laut Display-CONFIG, meist Unit 3, Display-Bedienwerte über +0x2000 |
| Modbus Warmlink LTE | TCP/IP/ser2net oder COM/RS485 | Modem-/Warmlink-Bus im Außengerät, an den Klemmen am Mainboard | Bus 0x63, RAW-Protokoll |

Kurz gesagt:

- **Standart** = die offiziellen Modbus-Klemmen am Gerät.
- **Display** = der Bus, der zum Display geht.
- **Warmlink LTE** = nur im Außengerät vorhanden, an den Klemmen am Mainboard / Modem-Bus.

### Verbindungsstatus / Teststand

- **Modbus Standart** ist getestet.
- **Modbus Warmlink LTE** zum LTE-/Warmlink-Modem ist getestet.
- **Modbus Display / HMI** wurde passiv mitgeschnitten und aktiv experimentell getestet. Baudrate/Format: sehr wahrscheinlich **4800 8N1**. Der Bus enthält mehrere Teilnehmer/Platinen und ist timingkritischer als Warmlink.

Aktueller Display-/HMI-Stand:

- Warmlink/WP-Register und Display/DWIN-Adressen sind getrennt. Der normale Registerbrowser bleibt Warmlink/WP; im Offline-Registerbrowser kann auf Display/DWIN-Mapping umgeschaltet werden.
- Display-Bus-Parameterpakete von Unit `0x03` (`1001ff`, `1091ff`, `1181ff`, `1271ff`, `1361ff`, `1451ff`, `1541ff`) werden mit normalem WP-/Warmlink-Mapping dekodiert, damit Klartexte/Value-Maps sichtbar bleiben.
- **Alle bekannten Register lesen** nutzt im Backend **Modbus Display** aktuell einen Display-Reboot-Snapshot: `5112H=0` und `0BC3H=8000H`. Dadurch lädt der Master die Parameterpakete erneut ins Display.
- Normale Display-Parameterwrites laufen über den Bedienwertpfad. Beispiel: `1012=2` wird als `23F4=2` gesendet. Das Display bzw. die Fallback-Logik setzt danach das passende `0BC3`-Flag, damit der Master das Paket liest.
- Mehrere Display-Writes laufen ACK-gesteuert nacheinander, damit Popup-/Timer-/Parameterwrites nicht parallel auf den Bus gehen.
- Manuelle FC03-Reads bleiben direkt möglich, um den noch unsicheren direkten `qty=90`-Leseweg weiter zu untersuchen.
- `3001ff` und andere echte DWIN-/Display-Diagnoseadressen bleiben im getrennten Display-Mapping.
- `3021` / `0x0BCD` im Block `0x03 / 3001ff` ist ein Kandidat für Display-Istmodus / Anzeige-Icon-Code. Der Wert wird bewusst **nicht** automatisch als `2012` übernommen.
- `3013` wurde als Display-Softwareversion bestätigt/beobachtet: `17` = V1.7.

Aktuelle Display-/HMI-Bus-Vermutungen aus Mitschnitten:

| Adresse | Vermutung | Beobachtet |
|---|---|---|
| 0x01 | Live-/Status-Teilnehmer | 1999/2099, FC03/FC16 |
| 0x02 | DWIN-/Display-Speicher Teilnehmer | 3001ff Reads, Parameterpaket-Spiegel |
| 0x03 | Display / DWIN-DGUS Speicher | 3001ff, Parameterpakete, +0x2000-Bedienwerte |
| 0x04 | Parameterblock-Poller | 1011ff Reads |
| 0x05 | interner Parameter-/Liveblock | 2000ff Reads, 1001-1090 Writes |
| 0x06 | Testadresse | bisher keine gesicherte Rolle |

Hinweis zu **1999/2001 / 20xx** im Display-/HMI-Modbus: diese Blöcke sind noch nicht sauber verifiziert. FC16-ACKs und unklare 1999/2001-Frames werden deshalb nur geloggt, aber nicht blind in die Hauptliste übernommen. **2012** wird im Display-Modbus nicht aus 1012 gespiegelt, weil 1012 Sollmodus und 2012 Ist-/Betriebsstatus mit unterschiedlicher Codetabelle sind. Für echte/saubere Istwerte bleibt Warmlink die bessere Quelle.

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

```bat
pip install -r requirements.txt
python foxair_phnix_control.py
```

## Windows-Build

```bat
build_windows_exe.bat
build_windows_setup.bat
```

## Hinweise

- Vor dem Schreiben von Parametern immer Backup erstellen.
- Werte, Einheiten und Registertexte sind aus Mitschnitten/ASM/App-Vergleichen rekonstruiert und können Fehler enthalten.
- Unbekannte Display-/DWIN-Werte sind als Diagnose zu verstehen.
