# Mainboard-Firmware V3.3 – OTA-, Flash- und Bootpfad

Stand: 23. August 2026

Diese Datei dokumentiert den statisch rekonstruierten OTA-Empfangs-, Flash- und Bootpfad der Mainboard-Firmware `82400644 / V3.3`.

Wichtig: Die Analyse basiert auf dem Mainboard-Binary. Der resident ausgeführte Loader/Bootloader im unteren Flashbereich ist nicht Bestandteil der untersuchten Datei. Aussagen zu persistenter Slot-Promotion und automatischem Rollback bleiben deshalb ausdrücklich offen.

## Bewertungsstufen

- **bestätigt** – direkt im Binary nachgewiesen
- **sehr wahrscheinlich** – Datenfluss weitgehend geschlossen, letzte Semantik fehlt
- **Hypothese** – plausible, aber noch nicht ausreichend belegte Interpretation

---

# 1. Gefundene OTA-Kommandos

Die Kommandos liegen in einem zusammenhängenden Kommunikations-/OTA-Block um `0x080978xx–0x08098Dxx`.

| Kommando | Fundstelle | Rolle |
|---|---:|---|
| `C544` | ca. `0x0809785E` / Sender `0x08098C24` | Build-/Firmware-Fingerprint, sehr wahrscheinlich |
| `C350` | `0x08097CE4` | Build-/Zielidentität vergleichen |
| `C357` | `0x08097D30` | Dateilänge + erwarteten MD5 übernehmen |
| `C5A8` | `0x08098108` | Firmware-Datenblock empfangen |
| `C36E` | Sender `0x08098BDC` | OTA-Status melden |
| `C371` | Sender `0x08098CE2` | Block-ACK melden |

Die Telegramme laufen als Modbus-RTU-Kommunikation; die normale Modbus-CRC16-Prüfung liegt bereits unterhalb dieser OTA-Handler.

---

# 2. Relevante RAM-Strukturen

```text
OTA-Basis:               0x200133F8
C5A8-RX-Buffer:          0x20013458 = OTA + 0x60
C5A8-Daten ab Header:    0x2001345E = OTA + 0x66
C5A8-Staging-RAM:        0x20013C6C
OTA-State:               0x20014434
Metadaten:               0x20016710
Commit-/Boot-Control:    0x2001660C
zweiter Slot-State:      0x20015D7C
```

---

# 3. C350 – Ziel-/Buildvergleich

Der FC10-Handler kopiert die Nutzdaten zunächst in RAM. Anschließend wird geprüft, dass ein Protokollbyte `0x63` enthält.

Der Verarbeitungsblock vergleicht zwölf empfangene Bytes mit einem zwölf Byte langen Fingerprint der laufenden Firmware.

Ergebnis:

- gleich: Ziel/Firmware entspricht der vorhandenen Kennung
- ungleich: die neue Kennung wird in die OTA-Metadaten übernommen und der Updatepfad aktiviert

**Bewertung:** Vergleich und Datenfluss bestätigt; Bezeichnung als Build-/Firmware-Fingerprint sehr wahrscheinlich.

---

# 4. C357 – Dateilänge und MD5

C357 überträgt die Metadaten des nachfolgenden Firmwareimages.

Bestätigtes Layout der gespeicherten Nutzdaten:

```text
Byte 0       unbekannt/reserviert
Byte 1       0x63
Byte 2       unbekannt/reserviert
Byte 3       Dateilänge Bit 23..16
Byte 4       Dateilänge Bit 15..8
Byte 5       Dateilänge Bit 7..0
Byte 6..37   erwarteter MD5 als 32 ASCII-Hexzeichen
```

Die Dateilänge wird also als 24-Bit Big Endian gebildet:

```text
length = b3 * 0x10000 + b4 * 0x100 + b5
```

Grenze:

```text
length <= 0x4B000 = 307200 Byte
```

Der erwartete MD5 wird als 32 Zeichen in die Live-Metadaten kopiert.

Nach akzeptierten Metadaten wird C36E Status 2 erzeugt.

**Bewertung: bestätigt.**

---

# 5. C5A8 – Datenblock empfangen

## 5.1 Empfang

Der normale eingehende Handler liegt bei `0x08098108`.

Er verwendet den allgemeinen FC10-RX-Helper `0x080AA100` und kopiert den empfangenen Registerblock zunächst nach:

```text
0x20013458
```

Danach werden nur Zustandsflags gesetzt. **Im Modbus-Handler selbst findet noch kein Flash-Schreibzugriff statt.**

Der eigentliche OTA-Worker beginnt bei:

```text
0x080A8628
```

## 5.2 C5A8-Header

Der Worker wertet aus:

```text
Byte 0/1   Session-/SSID-Feld; wird später in C371 unverändert zurückgespiegelt
Byte 2/3   Gesamt-/letzte Blocknummer, Big Endian
Byte 4/5   aktuelle Blocknummer, Big Endian
Byte 6..   Firmwaredaten
```

Die beiden Sessionbytes werden im gezeigten Blockpfad nicht kryptographisch geprüft. Sie dienen mindestens als Session-/Zuordnungskennung und werden im ACK zurückgesendet.

Der Firmwaredatenanteil, den der Worker pro Block übernimmt, beträgt exakt:

```text
0xA8 = 168 Byte
```

und wird nach:

```text
0x20013C6C
```

kopiert.

## 5.3 Blocknummer / Duplicate-Schutz

Aktueller Block:

```text
current = b4 * 256 + b5
```

Letzter bereits als geschrieben/committed geführter Block liegt im OTA-State bei `+0x7A2`.

Wenn:

```text
current == last_committed
```

wird der Block **nicht erneut geflasht**, sondern direkt erneut bestätigt.

Damit ist Retransmit-/Duplicate-Schutz innerhalb derselben laufenden OTA-Session bestätigt.

**Persistentes Resume nach Neustart ist damit noch nicht belegt**, weil der Blockzähler in RAM liegt.

---

# 6. C5A8 → Flash

Der Block wird zunächst aus dem RX-Buffer in den separaten 168-Byte-Stagingbuffer kopiert.

Erst die OTA-State-Machine programmiert Flash.

Der für den normalen 168-Byte-C5A8-Pfad relevante Zustand programmiert:

```text
42 × 32 Bit = 168 Byte
```

mit den Flashroutinen:

```text
Unlock:       0x080BD144
Program Word: 0x080BD2E4
Lock:         0x080BD190
```

Adressformel dieses Pfades:

```text
dst = 0x080A0F58 + current_block * 0xA8 + word_index * 4
```

Bei Blockzählung ab 1 beginnt Block 1 damit exakt bei:

```text
0x080A1000
```

Nach erfolgreicher Programmierung wird `current` als letzter committed Block gespeichert und der C371-ACK freigegeben.

**Bewertung: bestätigt.**

Hinweis: Im gleichen Worker existieren weitere Flash-Zustände mit anderen Adress-/Stride-Formeln. Diese gehören zu weiteren Update-/Kopierphasen und dürfen nicht mit dem normalen 168-Byte-C5A8-Blockpfad gleichgesetzt werden.

---

# 7. C371 – Block-ACK

C371 wird als FC10 gesendet:

```text
Unit:          0x63
Function:      0x10
Startregister: 0xC371
Quantity:      4 Register
Payload:       8 Byte
```

Payloadbuffer:

```text
0x20010B34
```

Bestätigtes Layout:

```text
Byte 0..1   C5A8 Session-/SSID-Feld unverändert zurückgespiegelt
Byte 2      in diesem Builder nicht belegt / normalerweise reserviert
Byte 3      konstant 1
Byte 4      in diesem Builder nicht belegt / normalerweise reserviert
Byte 5      ackB
Byte 6      Blocknummer High
Byte 7      Blocknummer Low
```

`ackB` ist damit **Byte 5**.

Bedeutung:

```text
ackB = 1   Block akzeptiert/geschrieben; weiterer Block erwartet
ackB = 2   letzter Block akzeptiert; Datenphase beendet
```

C371 wird erst nach erfolgtem Block-Commit ausgelöst. Bei einem bereits bekannten Duplicate-Block wird erneut bestätigt, ohne nochmals zu flashen.

Beim letzten Block werden außerdem der Last-Block-Zähler und der C5A8-Empfangszustand zurückgesetzt und die Gesamtimageprüfung gestartet.

**Bewertung: bestätigt.**

---

# 8. C36E – OTA-Status

C36E wird als FC10 gesendet:

```text
Unit:          0x63
Function:      0x10
Startregister: 0xC36E
Quantity:      2 Register
Payload:       4 Byte
```

Payloadbuffer:

```text
0x20010B30
```

Der Builder setzt sicher:

```text
Byte 1 = 0x63
Byte 3 = Status
```

Byte 0 und Byte 2 werden in diesem lokalen Builder nicht neu gesetzt und sind daher als reserviert/kontextabhängig zu behandeln.

Bisher rekonstruierte Statuswerte:

| Status | Bedeutung im V3.3-Binary | Bewertung |
|---:|---|---|
| 1 | C350-/Buildvergleich aktiviert Updatepfad | Verhalten bestätigt, genaue Herstellerbezeichnung offen |
| 2 | C357 Metadaten akzeptiert, Datenphase bereit | bestätigt |
| 3 | **Gesamtimage-MD5 erfolgreich** | bestätigt |
| 4 | **Gesamtimage-MD5 fehlgeschlagen** | bestätigt |
| 5 | später Commit-/Slot-Handoff erfolgreich | Bedingungen bestätigt, genaue Herstellerbezeichnung sehr wahrscheinlich |
| 6 | Descriptor-/Metadaten-CRC bzw. Copy-Verifikation fehlgeschlagen | bestätigt |

Wichtig: **Status 3 ist in dieser Firmware ein Erfolgspfad, kein Fehlerstatus.**

---

# 9. Prüfung nach letztem Block

Nach dem finalen C371-ACK wird die komplette gestagte Datei geprüft.

Aufruf um `0x080A8CB4`:

```text
MD5(
    base   = 0x080A1000,
    length = C357-Dateilänge,
    expect = C357-MD5-ASCII
)
```

Die MD5-Routine berechnet einen normalen MD5 über exakt die angegebene Dateilänge, formatiert ihn als 32 lowercase ASCII-Hexzeichen und vergleicht alle Zeichen.

Ergebnis:

```text
MD5 OK  → C36E Status 3
MD5 NOK → C36E Status 4
```

**Bewertung: bestätigt.**

---

# 10. Descriptor-/Commitprüfung nach MD5

Nach erfolgreichem MD5 wird ein Descriptor aufgebaut. Darin befinden sich unter anderem:

- Build-/Zielkennung
- Dateilänge
- erwarteter MD5
- weitere OTA-Metadaten

Über 61 Descriptorbytes wird eine CRC16 berechnet. Der Descriptor wird in einem Flash-Metadatenbereich um `0x080A0000` gespeichert und später erneut gelesen/verglichen.

Fehlschlag dieser Post-MD5-Prüfung erzeugt:

```text
C36E Status 6
```

Status 6 ist damit **kein normaler C5A8-Block-CRC-Fehler**, sondern ein später Fehler der Descriptor-/Commit-Verifikation.

**Bewertung: bestätigt.**

---

# 11. Zweiter ausführbarer Flashbereich `0x08050000`

Eine weitere OTA-/Slot-State-Machine verwendet:

```text
0x20015D7C
```

Sie enthält einen Kopierpfad:

```text
Quelle: 0x080A1000 + Offset
Ziel:   0x08050000 + Offset
```

Die Daten werden wortweise/chunkweise programmiert.

Anschließend wird auch der Bereich ab `0x08050000` nochmals über die gespeicherte Länge und den erwarteten MD5 geprüft.

Damit ist `0x08050000` eindeutig ein **ausführbarer Alternate-/Update-Bereich**, nicht nur ein beliebiger Backup-Datenbuffer.

**Bewertung: bestätigt.**

Noch nicht bestätigt ist, ob dieser Bereich aus Sicht des residenten Bootloaders als `candidate`, `backup`, `temporary updater` oder anders bezeichnet wird.

---

# 12. C36E Status 5

Status 5 entsteht erst nach der MD5-Datenphase in einer späteren Commit-/Handshake-Funktion um `0x080A6848`.

Voraussetzungen im Code:

1. ein Commit-Control-Zustand ist aktiv
2. ein 4-Byte-Controlframe wurde geladen
3. CRC16 über dessen zwei Nutzbytes stimmt mit den gespeicherten CRC-Bytes überein
4. `0x2001660C+0x2E == 1`
5. `0x2001660C+0x2F == 1`

Dann:

```text
OTA-Status = 5
Status-5-Sendeflag = 1
+0x2F wird zurückgesetzt
Control-CRC wird neu geschrieben
```

Die Flags `+0x2E/+0x2F` werden gemeinsam aus der separaten Slot-/Kopier-State-Machine gesetzt.

Damit ist Status 5 **eine spätere Commit-/Slot-/Handoff-Bestätigung und ausdrücklich nicht nur „MD5 OK“**.

**Bewertung:** Bedingungen bestätigt; Bezeichnung „Commit/Slot ready“ sehr wahrscheinlich.

---

# 13. Boot-/Jump-Verhalten

Eine periodische Funktion bei:

```text
0x080A9354
```

verarbeitet zwei verschiedene RAM-Flags in `0x2001660C`.

## Flag `+0x22` → Jump `0x08000000`

Die Routine prüft den Stackpointer am Vector Table `0x08000000` gegen den SRAM-Adressbereich.

Bei gültigem Vector Table:

- Peripherie wird heruntergefahren/deinitialisiert
- Interrupts werden deaktiviert
- MSP wird aus `[0x08000000]` geladen
- Reset Handler wird aus `[0x08000004]` geladen
- direkter `BLX` zum Loader

Das ist ein **Chain-Jump**, kein NVIC-Systemreset.

`0x08000000` ist damit der resident ausgeführte Loader-/Bootloaderbereich.

## Flag `+0x23` → Jump `0x08050000`

Dasselbe Verfahren existiert separat für den Vector Table bei:

```text
0x08050000
```

Auch hier werden MSP und Reset Handler direkt aus diesem Vector Table geladen und per `BLX` angesprungen.

**Bewertung: bestätigt.**

---

# 14. Resume, Retry und Abbruch

## Bestätigt

- Duplicate-/Retransmit-Erkennung über `current_block == last_committed`
- bereits committed Block wird nicht nochmals geschrieben, sondern erneut bestätigt
- Empfangs-/Timeoutcounter für C5A8 existieren
- ein Retrypfad zählt bis fünf Versuche
- ein Langzeittimeout setzt den laufenden C5A8-Empfang zurück und aktiviert einen Recovery-/Fehlerpfad
- mehrere OTA-Zustände können einen Jump zum residenten Loader bei `0x08000000` auslösen

## Nicht bestätigt

- persistentes Resume nach kompletter Spannungsunterbrechung
- persistentes Journal der zuletzt geschriebenen Blocknummer
- automatischer Boot-Retryzähler für ein fehlerhaftes neues Image
- atomare persistente Slot-Promotion
- automatischer Rollback auf das vorherige Anwendungsimage

Der bisher gefundene `last_committed`-Block liegt in RAM. Deshalb darf **Resume über Power Loss derzeit nicht angenommen werden**.

---

# 15. Integritätsstufen

Der OTA-Pfad besitzt mehrere voneinander unabhängige Prüfungen:

1. Modbus-RTU-CRC16 pro Telegramm
2. Blocknummer-/Duplicate-Prüfung für C5A8
3. C357-Dateilängengrenze `<= 0x4B000`
4. Gesamt-MD5 des Stagingimages ab `0x080A1000`
5. CRC16 des Post-MD5-Descriptors
6. erneute MD5-Prüfung des Bereichs ab `0x08050000`
7. CRC16 eines kleinen Commit-Controlframes vor Status 5
8. Vector-Table-/Stackpointer-Plausibilitätsprüfung vor jedem direkten Jump

Ein zusätzlicher eigenständiger Applikations-CRC innerhalb jedes C5A8-Datenblocks wurde bisher nicht gefunden; die Transportintegrität wird dort mindestens durch Modbus-RTU-CRC16 geschützt.

---

# 16. Offener Architekturpunkt / Sicherheitsblocker

Die untersuchte V3.3-Datei ist für:

```text
0x08080000
```

gelinkt.

Der OTA-Code verwendet aber zusätzlich:

```text
0x080A0000   Metadaten/Stagingbereich
0x080A1000   Stagingdaten
0x08050000   ausführbarer Alternate-/Update-Bereich
0x0804F800   weiterer Slot-/Descriptorbereich
0x0801F000   weiterer vom Slot-State verwendeter Flashbereich
```

`0x080A1000` liegt formal innerhalb des Adressbereiches der analysierten, ab `0x08080000` gelinkten Anwendung. Das bedeutet, dass ein noch nicht vollständig erklärter Ausführungs-/Loaderkontext existieren muss oder dass die OTA-Nutzdatei nicht einfach 1:1 mit dem untersuchten Binary gleichgesetzt werden darf.

Solange der Loader bei `0x08000000` nicht analysiert ist, lässt sich die endgültige Promotion-/Rollback-Policy nicht sicher beweisen.

---

# 17. Bewertung für einen ersten echten OTA-Test

Die V3.3-Firmware besitzt **mehrere gute Schutzschichten**:

- RAM-Puffer vor Flash-Commit
- Block-Duplicate-Schutz
- vollständiger MD5 vor weiterer Promotion
- Descriptor-CRC
- zweite MD5-Prüfung eines anderen Flashbereiches
- Vector-Table-Prüfung vor Jump
- residenten Loader bei `0x08000000`

Trotzdem ist ein unbeaufsichtigter erster OTA-Test derzeit **nicht als sicher bestätigt**.

Vor einem echten Test sollten mindestens vorhanden sein:

1. vollständiger Flash-Dump, insbesondere `0x08000000…0x0807FFFF`
2. Analyse des residenten Loaders bei `0x08000000`
3. Backup der Bereiche um `0x0801F000`, `0x0804F800`, `0x08050000`, `0x080A0000` und der aktiven Anwendung
4. funktionsfähiger Hardware-Recoveryweg per SWD/ST-Link oder gleichwertig
5. idealerweise ein realer OTA-RS485-Mitschnitt, um das exakte C5A8-Wireformat inklusive Quantity ohne Annahmen zu bestätigen

Erst mit dem Loaderdump lässt sich belastbar beantworten, ob ein Power Loss während Promotion automatisch auf einen gültigen alten Slot zurückfällt.
