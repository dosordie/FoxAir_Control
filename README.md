## PUBLIC V0.2.42 Hinweis

Diese Public-Version basiert auf **PUBLIC V0.2.41 fix7** und enthält bewusst **keine Änderung an den Display-Modus-/Write-Pfaden**.

**Neu gegenüber Public V0.2.41 fix7:**

- Log-Spam im Backend **Modbus Display** reduziert: stark wiederholte Bus-Diagnosezeilen, z. B. `0x02 / 3001`, werden im Log zusammengefasst statt tausendfach einzeln ausgegeben.
- Quellen-/Attributionshinweise für den Public-Release ergänzt.

**Aus Public V0.2.41 fix7 weiterhin enthalten:**

- Display-/HMI-Schreibpfade weiter verbessert: bekannte Parameter-/Timerwerte werden im Backend **Modbus Display** nur dort über den Bedienwertpfad `Register + 0x2000` geschrieben, z. B. `1287 -> 0x2507`.
- Timer 1-6, WP-Ein/Aus Timer, Silent Timer, SG Ready, WP-Steuerung, AT-Kompensation und Parameterfenster warten im Display-Modus auf die benötigten Paketdaten, statt leere/alte Werte blind zu schreiben.
- Mehrfachänderungen werden sequenziell geschrieben und bestätigt; besonders Timer-/Popupwrites laufen nicht mehr parallel auf den Bus.
- Für den WP-Ein/Aus-/Silent-Timer (`1181ff`) ist ein zusätzlicher Fallback über Kommunikationsregister + `0BC3=0x0008` enthalten.
- Neues Log-Level 1–7: Level 4 ist für Chat-/Fehlerdiagnose gedacht, RAW/TX-Spam erst ab Level 6.
- RAW anzeigen zeigt HEX+ASCII zusammen; die separate RAW-ASCII-Option entfällt.
- FC06/FC16-Auswahl ist in der normalen UI ausgeblendet; die Display-Spezialpfade wählen intern selbst den passenden Schreibweg.
- Unit-Einstellung bleibt als aktives Ziel für manuelle Modbusbefehle sichtbar; im Displaybus werden die passiven Rollen `0x00`, `0x01`, `0x03` usw. weiterhin separat erkannt.

**Wichtig:** Der Display-/HMI-Bus bleibt experimentell. Für sichere/produktive Änderungen bleiben **Modbus Standart** und **Modbus Warmlink LTE** die bevorzugten Wege. Vor Änderungen immer Backup erstellen.

# FoxAir / Phnix Control

Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir-/Phnix-basierte Wärmepumpen.

> **Wichtig:** Dieses Projekt ist kein offizielles FoxAir- oder Phnix-Tool. Das Schreiben von Registern kann Betriebsparameter verändern. Nutzung auf eigene Verantwortung. Vor Änderungen immer ein Backup erstellen.


## PUBLIC V0.2.44 – WarmLink Cloud

Diese Version übernimmt die Cloud-Funktionen aus **PRIVATE V0.2.44 fix4**, lässt aber die Public-Display-Modus-/Write-Pfade aus **PUBLIC V0.2.42** unverändert.

Neu/enthalten:

- WarmLink/Linked-Go Cloud-Login mit E-Mail in Settings und Passwort im OS-Keyring
- Geräte-/Device-ID-Anzeige
- Cloud-Polling, Overlay und Cloud-Spalten im Hauptfenster
- Cloud-Wertefinder
- Cloud-Schreibtest mit bestätigtem Endpunkt `app/device/control?lang=en`
- Rechtsklick **Wert per Cloud schreiben ...** für bekannte schreibbare Cloud-Codes
- Hauptfenster-Checkbox **Cloud-only Zeilen**, Standard eingeschaltet
- Log-Spam-Reduktion für stark wiederholte Display-Bus-Frames

### Quellen / Attribution

WarmLink/Linked-Go-Cloud-Erkenntnisse und Mapping-Ideen basieren unter anderem auf öffentlich verfügbaren Projekten/Recherchen, insbesondere `srbjessen/ha-warmlink`, `00gtw00/homeassistant_warmlink` und dort genannten ursprünglichen Reverse-Engineering-Hinweisen wie `zyznos321/warmlink`.

## Funktionen

- Live-Registeranzeige mit bekannten FoxAir/Phnix-Datenpunkten
- WarmLink/Linked-Go Cloud: Login, Geräteübersicht, Statuswerte, Overlay, Wertefinder und Schreiben bekannter Cloud-Codes
- Lesen und Schreiben per Modbus Standart und Modbus Warmlink LTE
- Experimentelle Display-/HMI-Unterstützung: passives Mithören, Snapshot per Reboot-Fake und ACK-gesteuertes Schreiben bekannter Parameterpaket-Nutzwerte
- TCP/IP/ser2net oder USB-RS485/COM-Port
- F1 Hilfe/About mit Version, GitHub-Link und Update-Prüfung
- Parameter-Einstellfenster mit Beschreibungen/Wissensdatenbank
- Backup/Restore für Parameterbereiche mit Diff-Vorschau
- Timer-Editoren, SG-Ready-Editor, Kontakt-/Lastausgang-/Fehlerdecoder
- Offline Register-Browser mit Umschaltung zwischen Warmlink/WP- und Display/DWIN-Mapping


## Quellen / Attribution

Dieses Projekt ist ein inoffizielles Diagnose- und Parametrierwerkzeug. Es ist kein offizielles FoxAir-, Phnix-, DWIN- oder WarmLink-Produkt.

Für Reverse Engineering, Plausibilitätsprüfungen und Protokollvergleich wurden neben eigenen Mitschnitten/Analysen auch öffentlich verfügbare Projekte und Diskussionen als Orientierung genutzt, unter anderem:

- `srbjessen/ha-warmlink`
- `00gtw00/homeassistant_warmlink`

Die Public-Version enthält keine fremden Warmlink-Cloud-Dateien und keine Zugangsdaten. Bitte beim Veröffentlichen auf GitHub die jeweiligen Projektlizenzen und Quellenhinweise beachten.

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
