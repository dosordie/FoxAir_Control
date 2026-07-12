Warmlink GUI Test v16

Änderungen aus Display-Firmware-Analyse:
- Mapping für Timer 1-6 vollständig ergänzt: je 7 Register ab 1281 / 0x0501.
- Register 1323-1325 als gepaarte Aktiv/Tage-Bitmasken bestätigt.
- Zirkulationspumpen-Timer 1326-1333 benannt.
- SG-Ready Block 1334-1341 benannt; SG05-SG07 als TEMP1/Offset bis 25.0 °C.
- Kommunikationsblock 1281-1360 entspricht Display-FW 0x0501-0x0550 / User-Variablen 0x2501-0x2550.

Hinweis:
- Timer-Editor ist weiterhin Timer-1-Editor; das Mapping kennt jetzt aber alle 6 Timer.
- SG-Ready-Editor ist noch nicht eingebaut, aber die Register sind jetzt in der Tabelle sauber benannt.

Aenderungen v15:
- Rechtsklick auf ein Register: neuer Punkt "Register ... schnell schreiben ...".
  Oeffnet ein Popup mit aktuellem Rohwert, decodiertem Wert, Eingabefeld,
  Lesen-Button und Schreiben-Button. Schreiben aus diesem Popup erfolgt ohne
  weitere Sicherheitsabfrage, weil das Popup bereits der bewusste Schreibdialog ist.
- Timer-Bitmasken aktualisiert:
    1323 / 0x052B = Timer 1+2 Aktiv/Tage Bitmaske
    1324 / 0x052C = Timer 3+4 Aktiv/Tage Bitmaske
    1325 / 0x052D = Timer 5+6 Aktiv/Tage Bitmaske
  Je Register gilt nach aktueller Beobachtung:
    Low-Byte = erster Timer des Paars, High-Byte = zweiter Timer des Paars
    je Byte: 0x80 aktiv, Mo=1, Di=2, Mi=4, Do=8, Fr=16, Sa=32, So=64
    Beispiel 0x8067: Timer 1 Low-Byte 0x67, Timer 2 High-Byte 0x80.
- Timer-1-Editor schreibt bei 1323 nur die Timer-1-Bedienlogik im Low-Byte
  und erhaelt das High-Byte aus dem geladenen Live-Wert, damit Timer 2 nicht
  versehentlich geloescht wird.
- Timer-Lesen im Timereditor liest jetzt 1281 bis 1325.

Warmlink GUI Test v15
=====================

Start:
  pip install -r requirements.txt
  python foxair_phnix_control.py

Default:
  Host: 192.168.10.43
  Port: 2001



Aenderungen v14:
- Timer-1-Modus-Codes gesichert:
    0 = WW
    1 = HZ
    2 = Kuehlen
    3 = HZ + WW
    4 = Kuehlen + WW
    9 = kein Modell gewaehlt / vermutlich aktueller Modus
- Timer-1-Kuehl-Zieltemperatur ergaenzt:
    1285 / 0x0505 = Kuehl-Zieltemperatur, TEMP1, 0.1 Grad C
    70 = 7.0 Grad C

Aenderungen v13:
- Timer-1-Editor aktualisiert sich live, wenn passende Register von der WP eintreffen.
  Felder mit Fokus werden dabei nicht ueberschrieben, damit man beim Bearbeiten
  keine Werte verliert.
- Timer-Editor ist jetzt nicht-modal: Hauptfenster bleibt weiter bedienbar.
- Timer-Erkenntnisse uebernommen:
    1281 = Ein-Zeit, 0xHHMM
    1282 = Aus-Zeit, 0xHHMM
    1283 = WW-Zieltemperatur, TEMP1, 550 = 55.0 C
    1284 = HZ-Zieltemperatur, TEMP1, 450 = 45.0 C
    1286 = Modus-Code, bekannt: raw 3 = HZ + WW
    1287 = maximale Leistung, raw 1 = 0.1 kW, raw 2 = 0.2 kW, ...
    1323 = Aktiv/Tage-Bitmaske, vermutlich 0x80 aktiv, Mo=1 Di=2 Mi=4 Do=8 Fr=16
           Beispiele: 133 = Mo+Mi aktiv, 159 = Mo-Fr aktiv
- Timer-Editor hat jetzt eigene Felder fuer HZ- und WW-Zieltemperatur,
  maximale Leistung in kW/Raw sowie Aktiv/Tage per Checkboxen.

Aenderungen v12:
- GUI kompakter:
    Rechte Seite ist jetzt scrollbar und schmaler.
    Das Logfenster hat wieder eine Mindesthoehe und sollte nicht mehr verschwinden.

- Sonderfunktionen kompakter:
    Kontaktdecoder Register 2034 ist jetzt ein Popup ueber den Button
    "Kontaktdecoder ...".
    Rechts im Hauptfenster bleibt nur eine kurze 2034-Zusammenfassung.

- Werte-Cache kompakter:
    Cache laden/speichern bleibt direkt sichtbar.
    Cache-Optionen sind erst nach Klick auf "Einstellungen ..." sichtbar.

- Init-Blöcke lesen:
    Neuer Button "Init-Blöcke lesen".
    Liest per FC03 nacheinander:
      1271 / 0x04F7, 90 Register
      2001 / 0x07D1, 90 Register
      2091 / 0x082B, 90 Register
    Zwischen den Requests wird intern eine kleine Pause gesetzt.

- Wertsuche kompakter und verbessert:
    Trefferanzahl wird direkt im Suchbereich angezeigt.
    "dec." ist jetzt eine kleine Checkbox:
      aus = Rohwert/signed
      an  = decodierter Wert
    Live-Suche loggt auch dann, wenn ein bereits bekannter Treffer einen neuen
    passenden Wert bekommt.
    Die Toleranz ist weiterhin eine echte Wert-Toleranz:
      Suchwert 340, Toleranz 5 findet 335..345.

- Namenssuche:
    Trefferanzahl wird direkt im Suchbereich angezeigt.
    Regex bleibt per Checkbox aktivierbar.

Aenderungen v11:
- Werte-Cache:
    Button "Cache speichern" schreibt die zuletzt erkannten Register nach
    foxair_phnix_last_values.json.
    Button "Cache laden" laedt diese Werte wieder in die Tabelle.
    Geladene Werte werden grau markiert, bis ein echter Live-Wert fuer dieses
    Register empfangen wurde.
    Optionen:
      beim Start laden
      beim Beenden speichern
      zyklisch speichern mit einstellbarem Intervall
    Die Cache-Optionen werden in foxair_phnix_settings.json gespeichert.

- Namenssuche:
    Suche im Namensfeld der aktuell bekannten/geladenen Register.
    Optional als Regex.
    Treffer werden violett markiert.

- Wertsuche verbessert:
    Suchwert kann weiter dezimal oder hex sein, z. B. 55 oder 0x0037.
    Die bisherige "Suchbereich"-Eingabe ist jetzt eine echte Wert-Toleranz.
    Beispiel: Suchwert 340, Toleranz 5 findet Werte von 335 bis 345.
    Auswahl:
      Rohwert/signed
      decodierter Wert
    Live-Schalter:
      Wenn aktiv, werden neue eintreffende Werte automatisch gegen die Suche
      geprueft und Treffer im Log gemeldet.

- Gezielt Register lesen:
    Im Bereich "Register schreiben" gibt es jetzt "FC03 lesen" mit Adresse
    und Anzahl.
    Rechtsklick auf eine Tabellenzeile:
      einzelnes Register lesen
      10 Register ab dieser Adresse lesen
      Adresse ins Schreib-/Lesefeld uebernehmen
    Antworten werden anhand der letzten eigenen Leseanforderung zugeordnet und
    dann in die Registertabelle eingetragen.

- Timer 1 Editor:
    Neuer Button "Von WP lesen".
    Liest den Timer-1-Bereich 1281 bis 1323 per FC03.
    Nach der READ/Response kann "Aus Live-Werten laden" die Werte in den Editor
    uebernehmen.
    Timer-Schreiben nutzt weiterhin die einstellbare Pause zwischen Writes.

Aenderungen v10:
- Erste Wertsuche mit Markierung und Live-Aktualisierung.
- Timer-Editor schreibt mit einstellbarer Pause zwischen den einzelnen Writes.
  Standard 1200 ms.

Aenderungen v9:
- Registertabelle hat neue Spalte "Letzter Wert".
- "nur bekannte Register anzeigen" ist standardmaessig AUS.
- Neuer Button "Timer 1 Editor ...".
  Register:
    1281 / 0x0501 = Timer 1 Einschaltzeit, Codierung 0xHHMM
    1282 / 0x0502 = Timer 1 Ausschaltzeit, Codierung 0xHHMM
    1284 / 0x0504 = Timer 1 Zieltemperatur, TEMP1, 0.1 Grad C
    1323 / 0x052B = Timer 1 maximale Leistung, Rohcode
    1287 / 0x0507 = Timer 1 Wochentag-Code
    1285 / 0x0505 = Timer 1 Kuehl-Zieltemperatur
    1286 / 0x0506 = Timer 1 Modus-Code
  Beobachtet bisher:
    1284 = 450 -> 45.0 Grad C
    1323 = 0x0090 etwa 0,6 kW, 0x0088 etwa 0,5 kW
    1287 = vermutlich Do=5, Fr=6
    1286 = Wechsel Deaktivieren -> Heizung schrieb 0x0009

Aenderungen v7/v8 weiterhin enthalten:
- Registertabelle bleibt nach Registernummer aufsteigend sortiert.
- Name-Spalte: Inhaltsbreite, maximal ca. 320 px, voller Name als Tooltip.
- Parser erkennt:
    FC03 Read Request
    FC03 Read Response, bei eigenen Reads auch mit Registerzuordnung
    FC16 Write Multiple Request mit Bytecount
    FC16 Write Multiple Response / ACK
    Warmlink/WP-90-Wort-Frames als FC16 Request mit qty=90 und bytecount=0xB4
- Eingebettete Marker wie "02 10 07 D1" oder "02 10 08 2B" im Payload werden
  nicht mehr als echte Fremdframes/Bus-Adresse 0x02 gewertet.
- Tabelle "Gesehene Bus-Adressen".
- Raw-Anzeige:
    "Raw anzeigen" = RX-Chunks als Hex
    "Raw ASCII-Vorschau" = zusaetzlich ASCII-Spalte
    "Raw in Datei (nc/bin)" = TCP-Stream 1:1 binaer nach raw_logs/*.bin

Wichtige Hinweise:
- Schreiben auf Bus 0x63 ist der bisher getestete Weg Richtung WP/Regler.
- FC03-Lesen ist neu. Falls keine Antwort kommt, bitte Raw/Log posten.
- Timer-Editor bitte zuerst mit "Dry-Run" pruefen.
- Modus-Codes, Timer-Aktiv/Tage, WW-Temp und max. Leistung sind fuer Timer 1 bestaetigt. Weitere Timer noch gegenpruefen.


v17 Änderung:
- Keine bestehenden bekannten Register überschrieben.
- Nur leere, unbekannte oder als reserviert markierte Register aus DEMONS.ASM ergänzt.
- Neue/ersetzte Namen tragen den Hinweis "(ASM)" und source="ASM DEMONS.ASM".
- Ergänzt u.a. Z08-Z16, KG1-KG60 Alt-Timerblock, A38/A39/H40/C13-C15/E20/E21/Z19/Z20 und Werkstestblock 1371-1380.
- Hinweis: ASM-Namen sind Display-Firmware-Bezeichnungen und nicht zwingend endgültige Warmlink-/WP-Menütexte.

v18 Änderung:
- Timer-Editor auf Timer 1-6 erweitert (Tabs). Schema:
    Timer n: 1281 + (n-1)*7
      +0 Ein-Zeit, +1 Aus-Zeit, +2 WW-Ziel, +3 HZ-Ziel,
      +4 Kuehlen-Ziel, +5 Modus, +6 max. Leistung.
- Timer-Bitmasken bleiben paarweise erhalten:
    1323 Timer 1+2, 1324 Timer 3+4, 1325 Timer 5+6.
    Low-Byte = erster Timer im Paar, High-Byte = zweiter Timer im Paar.
- Neue Decoder/Typen:
    TIME_HHMM, TIMER_MODE, MODE_0_4, SG_MODE, POWER_KW_X10, TIMER_BITPAIR.
- SG Ready besser decodiert:
    1334 SG01: 0=Aus, 1=Einfach/1 Kontakt, 2=Erweitert/2 Kontakte.
- Init-Lesen hat optional Checkbox "extra": liest zusaetzlich ASM-Blockstarts
    1001, 1091, 1181, 1361, 1451, 1541 je 90 Register.
- Parser kennt nun auch 1541 / 0x0605 als 90-Wort-Blockstart.
- Timer-Editor zeigt Ausstattungshinweis aus H05/Kuehlen (1021) und H28/WW (1028)
  und graut unpassende Modus-Auswahlen aus, wenn diese Live-Werte bekannt sind.
- Neuer SG Ready Editor fuer 1334-1341:
    SG01 Funktion als Dropdown, SG05-SG07 als TEMP1 bis 25.0 Grad C,
    Lesen per FC03 und Schreiben mit einstellbarer Pause.


v19 Mapping-Ergänzung aus Display-Firmware ASM:
- Weitere reservierte Register anhand von DEMONS.ASM benannt, ohne bekannte Namen zu überschreiben.
- Neu/verbessert: A31, E15/E16, R12/R13/R14, 2024/2025, 2065-2068, 2070, 2103, 2107, 2108.
- Zusätzliche value_map für AN/AUS, Modus, Kühlfunktion, Master/Slave, WW-Funktion, Temperatureinheit, Silent.

v20 Änderungen (Analyse DEMONS_V1.3.ASM):
- Legacy-Init-Lesen ergänzt: Checkbox "V1.3" liest 1018/73, 1101/80, 1191/80.
- Parser kennt zusätzlich Legacy-Paketstarts 0x03FA, 0x044D, 0x04A7, 0x05B5, 0x060F.
- Generischer bit_map/FAULT_BITS Decoder ergänzt.
- Fehlerregister 2085, 2089 und 2090 teilweise aus Fault_Status_Display der V1.3 decodiert.
- 2056 als weitere System-1-Frostschutztemperatur 2 aus V1.3 erkannt.
- 1086, 1141, 1193, 1194 und KG1-KG12 anhand V1.3 besser benannt.
- Neue ASM-V1.3 Register 1001, 1008, 1010 ergänzt.

v21 Änderung:
- Alles bisher sicher gefundene Mapping zusammengeführt.
- 2034 als Schalter-/Kontakt-Bitfeld mit S01-S16 Decoder.
- 2019 als Lastausgänge teildecodiert: Kompressor Bit0/1, WW-Dreiwegeventil Bit9.
- Fehlerregister 2081-2083 und 2085-2090 als FAULT_BITS aus Node-RED-Projektkontext + ASM V1.3 ergänzt.
- Zusatzdatei: v21_mapping_erkenntnisse.txt


v22 Änderung:
- Register 2019 / 0x07E3 Lastausgänge vollständig decodiert.
- Bit0 Kompressor, Bit2/3 Lüfter High/Low, Bit4 Wasserpumpe, Bit5 WW-Pumpe, Bit6 4-Wege-Ventil, Bit7/8 Heizstufen, Bit9 3-Wege-Ventil, Bit10 Alarm, Bit11 Kurbelgehäuseheizung, Bit12 Wannenheizung, Bit13 Heizungswasserpumpe, Bit14/15 Hydraulikmodul Elektroheizungen.
- Mapping stammt aus User-bestätigter Lastausgang-Bitliste.

v23 Änderung:
- 2034 / 0x07F2 um SG-Kontaktbits ergänzt:
  Bit12 = SG Kontakt 1
  Bit13 = SG Kontakt 2
- 2034, 2019, 2018 als read-only Statusregister markiert.
- 1353-1355 als reservierte/lückenhafte Register ohne belastbare ASM/DWIN-Referenz dokumentiert.
- v23_dwin_bin_erkenntnisse.txt ergänzt.

v24 Änderung:
- Rechtsklick -> "Register schnell schreiben ..." zeigt jetzt bei bekannten value_map/values einen Klartext-Dropdown.
- Auswahl im Dropdown setzt automatisch den Rohwert in das Schreibfeld.
- Manuelle Eingabe synchronisiert den Dropdown, wenn der Wert bekannt ist.
- Unterstützt vorhandene JSON value_map sowie generische Decoder für TIMER_MODE, MODE_0_4/RUN_MODE, SG_MODE und einfache AN/AUS-Werte.


v25 Änderung:
- Fenstertitel geändert auf: FoxAir / Phnix Control V25


v26 Änderung:
- Fenstertitel auf V26 aktualisiert.
- Kontaktdecoder Register 2034 zeigt jetzt SG Kontakt 1/2 auf Bit12/Bit13.
- Kontaktdecoder hat optionalen Poller: Checkbox, Intervall in Sekunden und „jetzt lesen“.
- Poller liest 2034/0x07F2 per FC03, GUI bleibt weiter bedienbar.

v27 Änderung:
- Versionsschema auf V0.1.27 umgestellt.
- Fenstertitel: FoxAir / Phnix Control V0.1.27
- Programmicon integriert: app_icon.png und app_icon.ico
- Qt setzt das Icon für Fenster und Anwendung/Taskleiste.
- Unter Windows wird zusätzlich eine AppUserModelID gesetzt, damit das Taskleistenicon sauber verwendet wird.

v28 Änderung:
- Versionsschema/Fenstertitel auf V0.1.28 gesetzt.
- Init-Blöcke lesen läuft jetzt per nicht-blockierender Qt-Timer-Warteschlange.
- Pause zwischen Init-Leseblöcken ist im Lesen-Bereich einstellbar, Standard 900 ms.
- Große Read-Responses aktualisieren die Registertabelle gebündelt: Spaltenbreite/GUI-Refresh nur noch einmal pro Frame statt pro Register.
- Ziel: Extra-/Legacy-Init darf die Oberfläche nicht mehr mehrere Sekunden blockieren.


V0.1.29
- Erste Bildschirmaufnahme der Original-App ausgewertet.
- H-/E-Parameter App-Namen und mehrere Dropdown-Wertelisten ins Mapping übernommen.
- Fenstertitel auf FoxAir / Phnix Control V0.1.29 gesetzt.
- Details siehe v29_app_video_parameterblock1.txt.

V0.1.30
- v29-Mapping bereinigt: technische/deutsche Namen und bestehende value_map bleiben erhalten.
- Original-App-Texte aus der Bildschirmaufnahme werden separat als app_label/app_values gespeichert.
- Neuer Button "Parameter Einstellungen ...".
- Neues Popup "Parameter Einstellungen" mit Blockauswahl oben (z. B. H, A, F, D, E, C, R, Z, SG, KG).
- Tabelle zeigt Code, Original-App-Name, aktuellen Wert, Rohwert, Register, Typ und Info.
- Sichtbare Parameter können blockweise gelesen werden.
- Doppelklick oder Button "ausgewähltes Register schreiben ..." öffnet das bekannte Einzelregister-Schreibpopup mit Klartext-Dropdown, falls Mapping vorhanden ist.

V0.1.31
- Parameter-Einstellungen: Blockauswahl als Buttons/Tabs oben statt Dropdown.
- Block "Alle" entfernt.
- Name-Spalte zeigt standardmaessig den deutschen/technischen Namen; Checkbox "App-Name anzeigen" schaltet auf Original-App-Name um.
- Bus-Eingabe im Parameterfenster entfernt.
- Rohwert-Spalte im Parameterfenster zeigt nur noch Dezimalwert ohne HEX.
- Einzelregister-Schnellschreibdialog ohne Bus-Eingabe.
- Schnellschreibdialog nutzt value_map bevorzugt und app_values als Fallback, z. B. fuer H31 Pump Type.

V0.1.32 Änderung:
- Registerübersicht read-only; Doppelklick öffnet Schnellschreiben.
- Parameterblock-Klick kann automatisch blockweise lesen (Checkbox aktiv).
- Parameter-Lesen fasst Register zu FC03-Blöcken zusammen, kleine Lücken werden mitgelesen.
- Schnellschreiben-Dropdown nutzt value_map/values/app_values zusammen.
- H31 und H37 Dropdown-Werte ergänzt.


V0.1.33 Änderung:
- Parameter-Einstellungen: kurze Blockbeschreibungen unter den Block-Tabs ergänzt.
  Vorschlag: H=Basis/Hardware, A=Schutz/Grenzen, F=Fan, D=Abtauen, E=EVI/EEV, C=Compressor, R=Sollwerte, Z=Zone, G=Legionellen, P=Pumpe.
- Beim Öffnen des Parameterfensters wird der erste ausgewählte Block automatisch gelesen, wenn „Block automatisch lesen“ aktiv ist.
- Weitere Blöcke werden weiterhin erst beim Klick auf den jeweiligen Block automatisch gelesen.


V0.1.34 Änderung:
- Blockbeschreibung KG geändert: Timer Basis.
- Bedeutung: Basis-Timer für WP Ein/Aus und Silent-Modus Ein/Aus.


V0.1.35:
- Parameter-Einstellungen: Block-Beschriftungen direkt unter den klickbaren Blockbuttons angeordnet.
- P01 und P05 mit Dropdown/Value-Map fuer Pumpen-Betriebsmodus ergaenzt.
- E01 EEV-Anpassungsmodus korrigiert: 0=Manuell, 1=Auto, 2=Smart.


V0.1.36:
- Mapping-Review: Beschreibungen/App-Werte nach bislang ungenutzten Zustandswerten durchsucht.
- Fehlende value_map-Dropdowns ergänzt, bestehende value_map-Einträge nicht überschrieben; nur fehlende Werte ergänzt.
- 1016 Manuelle Steuerung als Bitfeld-Beschreibung ergänzt.
- Fenstertitel auf FoxAir / Phnix Control V0.1.36 gesetzt.

V0.1.37:
- H30 korrigiert: Indoor Unit Type / Hydraulikmodul-Typ mit 0=None, 1=1st Type, 2=2nd Type, 3=3rd Type.
- A35 / 1031 korrigiert: Electric Heater Off Temp Diff, 0.5 °C Schritte, Standard 0 °C; falsches Indoor-Unit-Dropdown entfernt.
- Block T im Parameterfenster als Temperatur beschriftet.
- Fenstertitel auf FoxAir / Phnix Control V0.1.37 gesetzt.

V0.1.38:
- A-Block Video ausgewertet.
- App-Texte als app_label/app_values ergänzt, bestehende technische Namen geschützt.
- A29, A38, A39, A40 aus App-Video benannt.
- Neue Anzeige-Typen: BAR_X10, AMP_X2, FLOW_M3H_X10, MINUTES.
- Fenstertitel auf FoxAir / Phnix Control V0.1.38 geändert.

V0.1.39:
- F-Block und D-Block aus App-Video ergänzt (app_label/app_values, technische Namen bleiben erhalten).
- Autoconnect beim Appstart als Checkbox ergänzt, Host/Port/Autoconnect werden gespeichert.
- Parameter-Einstellungen Fenster startet größer.
- A40 Skalierung korrigiert: raw/10 = m³/h (5 = 0.5 m³/h).
- „Forum“ aus bekannten Parameternamen entfernt; Quelle bleibt in Info/source.

v0.1.40 Änderung:
- A40 / Nenn-Wasserdurchfluss Anzeige erneut korrigiert.
- Cache-/geladene Werte im Parameterfenster und Schnellschreiben-Dialog nutzen jetzt denselben Formatter wie Live-Werte.
- Damit wird A40 raw 5 als 0.5 m³/h angezeigt, nicht als 5.

V0.1.41 Änderung:
- UI-Cleanup: Register schreiben/lesen als Popup, Init-Lesen kompakt in der Seitenleiste.
- Timer-Editor zu Sonderfunktionen verschoben.
- Bus-Adressen als Popup.
- Offline Register-Browser hinzugefügt.
- Block-Spalte in Registerübersicht und Parameterfenster; Namen ohne H/A/Z/SG-Prefix.


V0.1.43:
- Dokumentations-/Protokoll-TXT-Dateien nach docs/ verschoben.
- requirements.txt bleibt im Hauptordner.
