# FoxAir / PHNIX Firmware-Übersicht

Stand: 2026-08-30

Diese Seite soll die häufige Verwechslung zwischen **Mainboard-Firmware**, **Display-Firmware** und **LTE-/DTU-Firmware** vermeiden. Eine Versionsnummer wie `V1.7` oder `V3.4` ist **ohne den zugehörigen Software-/Gerätecode nicht eindeutig**.

> Kurz gesagt: **Display V1.7 ist nicht Mainboard V1.7.** Bei vielen FoxAir-Geräten läuft z. B. Display V1.7 zusammen mit Mainboard V1.2, V1.3, V3.3 oder V3.4.

## Welche Firmware gehört wohin?

| Komponente | Typischer Code | Updateweg | Beispiel |
|---|---|---|---|
| Mainboard / Hauptsteuerung | `82400644` | OTA über PHNIX/WarmLink/LTE-DTU | `V3.3`, `V3.4` |
| kleines DWIN/LCD-Display | `82400463` | SD-Karte / `DWIN_SET` | `V1.3`, `V1.7` |
| LTE-DTU / Kommunikationsmodul | `82400409` (beobachtet) | eigener DTU-OTA-Pfad | `V1.2` (beobachtet) |

Die Codes sind wichtiger als die reine Versionsnummer: PHNIX verwendet dieselbe Versionsnummern-Systematik für unterschiedliche Komponenten und Controllerfamilien.

---

## Mainboard / Hauptsteuerung

### FoxAir GL9 / GL9-1 – Controllerfamilie `82400644`

Für FoxAir GL9/GL9-1 ist die Mainboard-Familie mit Softwarecode **`82400644`** durch Forumsmeldungen und durch analysierte Original-Firmware bestätigt. Der Code scheint jedoch **nicht exklusiv FoxAir** zu sein: auch andere PHNIX-OEM-/Rebrand-Geräte verwenden `82400644`. Deshalb sollte man den Code eher als **PHNIX-Controller-/Softwarefamilie** verstehen.

| Mainboard-Version | Softwarecode | Zuordnung / Status | Knapper Änderungsstand |
|---|---|---|---|
| `V1.2` | `82400644` bzw. Code-Endung `644` | auf FoxAir GL-Serie beobachtet | ältere Basisversion; kein belastbares vollständiges Changelog bekannt |
| `V1.3` | `82400644` bzw. `644` | auf FoxAir GL9/GL9-1 beobachtet | ältere Basisversion; im Forum zusammen mit Display V1.7 beobachtet |
| `V2.4` | `82400644` | PHNIX-OEM/Rebrand-Handbücher, nicht als FoxAir-Release bestätigt | belegt, dass `82400644` über FoxAir hinaus als Controllerfamilie verwendet wird |
| `V2.6` | Mainboard-Nr. `644` beobachtet; vollständiger Code dort nicht sicher ausgelesen | PHNIX/WarmLink-Nutzer im Wärmepumpenforum | Zwischenstand derselben/nahen PHNIX-Plattform; nicht als FoxAir-GL9-Release gesichert |
| `V3.3` | **`82400644`** | FoxAir GL9 praktisch und im Original-Binary bestätigt | automatische Heizkreispumpenregelung; erweiterte Wannenheizungslogik; deutlich mehr Modbus-Parameter; SG-Ready-Parameter verfügbar |
| `V3.4` | **`82400644`** | Original-Binary analysiert; auch als Update im Forum gemeldet | AT-Kurve + Leistungstimer gleichzeitig; überarbeitete A34-Cold-Start-Vorheizung; neue dreiphasige Strombegrenzung; erweiterte SG/PV-Logik |

### V3.3 – wichtigste bekannte Änderungen

Im praktischen Betrieb wurde für V3.3 insbesondere berichtet:

- automatische Regelung der Heizkreispumpe auf die gewünschte Spreizung,
- beim Abtauen weiterhin hohe/volle Pumpendrehzahl,
- Wannenheizung kann nach dem Abtauen zeitlich begrenzt werden,
- zusätzliche Modbus-Register/Parameter, insbesondere im Bereich 1300–1400,
- SG-Ready-Steuerung wird über zusätzliche Parameter zugänglich.

### V3.4 – wichtigste bekannte Änderungen

Aus Forumshinweisen und unserem statischen Vergleich V3.3 → V3.4:

- **Außentemperatur-/Heizkurve kann gleichzeitig mit den Leistungstimern verwendet werden.**
- A34 / Kurbelgehäuse-/Ölsumpf-Vorheizung wurde für echte Kaltstarts robuster gestaltet; die normale 8/10-°C-Thermostatlogik der Kurbelgehäuseheizung bleibt davon getrennt.
- neuer dreiphasiger Soft-Strombegrenzer auf Basis des höchsten Eingangsstroms aus L1/L2/L3,
- erweiterte SG-/PV-State-Machine; zusätzlich zu klassischem SG Ready existiert ab V3.4 eine zweite 3-stufige SG/PV-Familie.

Technische Details dazu liegen bewusst im Reverse-Engineering-Bereich:

- [`reverse_engineering/firmware_v34.md`](reverse_engineering/firmware_v34.md)
- [`reverse_engineering/firmware_v34_sg_ready_8801.md`](reverse_engineering/firmware_v34_sg_ready_8801.md)

> **Wichtig:** Es ist derzeit **keine FoxAir/82400644-V3.5 öffentlich belastbar bestätigt**. Einzelne Erwartungen oder Ankündigungen ohne Firmwaredatei/Versionsnachweis werden hier nicht als bekannte Version geführt.

---

## Display-Firmware – kleines DWIN/LCD

Die Display-Firmware ist **eine separate Firmware** und hat mit der Mainboard-Version nichts zu tun.

Für die bei FoxAir häufig mitgelieferten kleinen Displays sind zwei englische Firmwarepakete dokumentiert:

| Display-Version | Display-/Softwarecode | Build-Kennung | Hinweis |
|---|---|---|---|
| `V1.3` | **`82400463`** | `202207212023` | englisches DWIN/LCD-Paket, ca. 54 MB |
| `V1.7` | **`82400463`** | `202311131429` | englisches DWIN/LCD-Paket, ca. 88 MB; häufig für Umstellung polnisch → englisch verwendet |

Updateweg: SD-Karte mit dem kompletten `DWIN_SET`-Ordner; das Display wird dabei unabhängig vom Mainboard aktualisiert.

Ein typischer realer Zustand ist daher völlig korrekt:

```text
Display:   82400463 / V1.7
Mainboard: 82400644 / V1.3
```

oder ebenso:

```text
Display:   82400463 / V1.7
Mainboard: 82400644 / V3.4
```

Die Aussage „ich habe Firmware 1.7“ ist deshalb ohne Zusatz **nicht ausreichend** – gemeint ist bei FoxAir häufig nur das Display.

Andere PHNIX-/OEM-Geräte können andere Displaycodes besitzen (z. B. `82400417`). Auch deshalb sollte beim Vergleichen immer **Code + Version** genannt werden.

---

## LTE-DTU / WarmLink-Kommunikationsmodul

Auch das LTE-DTU besitzt eine eigene Firmware und fragt selbst OTA-Updates ab.

Bei einem analysierten FoxAir-LTE-DTU wurde folgendes OTA-Identitätstelegramm beobachtet:

```text
DTU Hardwarecode: 82300225
DTU Softwarecode: 82400409
DTU Version:      V1.2
```

Diese Werte beschreiben **das LTE-/WarmLink-Modul**, nicht Mainboard oder Display. Die Zuordnung ist bisher an mindestens einem realen Modul bestätigt und sollte noch nicht als zwingend identisch für jede FoxAir-Generation verstanden werden.

---

## Gerätegenerationen und Zuordnung

### GL9 / GL9-1

Für die FoxAir **GL9/GL9-1** ist `82400644` als Mainboard-/Softwarefamilie gut belegt. Die analysierten V3.3- und V3.4-Binaries gehören eindeutig zu dieser Familie.

Da derselbe Mainboardcode `82400644` auch in PHNIX-OEM-/Rebrand-Unterlagen auftaucht, ist die wahrscheinlichste Einordnung:

```text
PHNIX Controller-/Softwarefamilie 82400644
        ↓
verschiedene OEM-/Rebrand-Geräte
        ↓
u. a. FoxAir GL9 / GL9-1
```

**Nicht ausreichend belegt** ist derzeit, ob wirklich jede GL-Leistungsstufe und jede Hardwaregeneration (z. B. GL15/GL19 usw.) exakt dieselbe Firmwarefamilie verwendet. Für solche Geräte sollte daher immer der tatsächlich ausgelesene Mainboardcode dokumentiert werden.

### Warum die Version allein nicht reicht

Beispiele aus PHNIX-/OEM-Quellen zeigen `82400644` auch mit Versionen wie V2.4; im Wärmepumpenforum wurde bei einem PHNIX/WarmLink-Gerät eine Mainboard-Nr. `644` mit V2.6 ausgelesen. Gleichzeitig existieren völlig andere Mainboardfamilien wie `82400416` in älteren/anderen PHNIX-Geräten.

Damit gilt für Vergleiche immer:

```text
Hersteller/OEM + Modell + Softwarecode + Firmwareversion
```

statt nur:

```text
Firmwareversion
```

---

## Quellen und Community-Nachweise

### Photovoltaikforum – FoxAir-Thread

- Displaypakete `82400463` V1.3 / V1.7:  
  https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=7
- GL9 mit Display V1.7 und Mainboard-Firmware getrennt betrachtet:  
  https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=12
- GL9 mit Mainboard V3.3; Pumpenregelung, Wannenheizung, neue Modbus-Parameter:  
  https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=48
- beobachtete Mainboard-Versionen V1.2/V1.3 und Hinweis auf V3.4:  
  https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=85
- klare Trennung Display V1.7 ↔ Mainboard V3.x:  
  https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=91

### Wärmepumpenforum – PHNIX / WarmLink

- Erfahrungsaustausch mit PHNIX/WarmLink, u. a. Mainboard-Nr. `644`, Version V2.6 und Register-/Firmwarevergleich:  
  https://www.waermepumpenforum.com/forum/thread/4752-suche-zwecks-erfahrungsaustausch-phnix-warmlink-nutzer/?pageNo=2
- ältere Timer-/Heizkurvenbeobachtung: Leistungstimer verlangte festen Temperatursollwert und verdrängte damit die Heizkurve – passend zum späteren V3.4-Fix:  
  https://www.waermepumpenforum.com/forum/thread/4752-suche-zwecks-erfahrungsaustausch-phnix-warmlink-nutzer/

### Ergänzende PHNIX-/OEM-Nachweise

Andere PHNIX-OEM-Unterlagen zeigen ebenfalls Mainboardcode `82400644`, z. B. mit Version V2.4. Das stützt die Einordnung als Controllerfamilie und nicht als FoxAir-exklusiven Code.

---

## Beim Melden einer neuen Firmware bitte immer angeben

Damit neue Funde eindeutig eingeordnet werden können, möglichst folgende Angaben zusammen notieren:

```text
Modell / Leistungsstufe:
Mainboard-Code:
Mainboard-Version:
Display-Code:
Display-Version:
DTU-Softwarecode / DTU-Version (falls bekannt):
Quelle / Foto / App-Anzeige / Registerdump:
```

Für Mainboard `82400644` können insbesondere Register/Device-Info aus FoxAir Control zur eindeutigen Identifikation genutzt werden.
