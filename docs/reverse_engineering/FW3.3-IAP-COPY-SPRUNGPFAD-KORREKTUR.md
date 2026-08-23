# Mainboard-Firmware V3.3 – korrigierte Linkbasis, IAP-, Copy- und Sprungpfad

Stand: 23. August 2026

Diese Datei dokumentiert eine erneute, bewusst unabhängige Analyse des IAP-, Copy- und Sprungpfads der Mainboard-Firmware `82400644 / V3.3`. Sie korrigiert eine wesentliche frühere Annahme: Die bekannte 287598-Byte-Datei ist **nicht für `0x08080000`, sondern für `0x08050000` gelinkt**.

## Kurzfassung

Bestätigt ist jetzt:

```text
phnixIot_device_OTA.bin
Größe: 287598 Byte = 0x4636E
Initial MSP:   0x2000EB90
Reset Handler: 0x080927D1
Linkbasis:     0x08050000
```

Der OTA-Pfad schreibt C5A8-Daten zunächst nach `0x080A1000`, prüft dort den MD5, kopiert anschließend wortweise und ohne Relocation nach `0x08050000`, prüft dort den MD5 erneut und springt schließlich über den Vector Table bei `0x08050000` in genau dieses Image.

Die frühere Hypothese, dass zuerst ein separates kleines Phase-A-/IAP-Image nach `0x08050000` übertragen werden müsse und die bekannte 287598-Byte-Datei erst in einer zweiten Phase nach `0x08080000` installiert werde, ist damit **widerlegt**.

Zusätzlich wurde die Transportseite dynamisch bestätigt: 1712 echte C5A8-Frames des originalen LTE-Prozesses rekonstruieren exakt die bekannte 287598-Byte-V3.3-Datei.

---

# 1. Bytegenauer Nachweis der Linkbasis

Die ersten beiden 32-Bit-Werte der Firmware sind:

```text
BIN +0x00 = 0x2000EB90
BIN +0x04 = 0x080927D1
```

Damit enthält die Datei eine normale Cortex-M-Vector-Table mit plausiblem SRAM-Stackpointer und Thumb-Resetvektor.

## Gegenprobe `0x08080000`

Wäre die Datei für `0x08080000` gelinkt, läge der Resetcode bei:

```text
0x080927D0 - 0x08080000 = Datei-Offset 0x127D0
```

Dort befindet sich jedoch kein Startupstub, sondern normale Anwendungs-/Regellogik.

## Gegenprobe `0x08050000`

Bei Basis `0x08050000` liegt der Resetcode bei:

```text
0x080927D0 - 0x08050000 = Datei-Offset 0x427D0
```

Dort befindet sich tatsächlich der Startupstub:

```asm
0x080927D0  LDR  R0, [PC,#4]
0x080927D2  BLX  R0
0x080927D4  LDR  R0, [PC,#4]
0x080927D6  BX   R0
```

Die referenzierten Ziele `0x080921B1` und `0x080927F9` liegen ebenfalls innerhalb desselben Images.

**Bewertung: bestätigt.**

---

# 2. Weitere unabhängige Belege

## Vector-Eintrag bei Datei-Offset `0xB0`

```text
BIN +0xB0 = 0x08053747
```

Mit Basis `0x08050000` liegt der Handler bei Datei-Offset ungefähr `0x3746` und damit sauber innerhalb der Datei.

Mit Basis `0x08080000` läge er vor dem Image.

## Build-/Fingerprintdaten

Der Stringblock:

```text
824006440033
```

liegt bei Datei-Offset `0x42780`.

Mit korrekter Basis:

```text
0x08050000 + 0x42780 = 0x08092780
```

Der OTA-/C544-Code referenziert genau `0x08092780` und `0x08092790` für die laufenden Build-/Fingerprintdaten.

Damit passen Vector Table, Startupcode und Builddaten konsistent nur zur Basis `0x08050000`.

---

# 3. Korrektur bisheriger Funktionsadressen

Die frühere Analyse wurde mit einer um `+0x30000` falschen Imagebasis durchgeführt. Dateioffsets und RAM-Adressen bleiben gültig; absolute Code-VAs aus dieser BIN müssen jedoch um `0x30000` reduziert werden.

Beispiele:

| Funktion | alte VA | korrigierte VA |
|---|---:|---:|
| C350 RX | `0x08097CE4` | `0x08067CE4` |
| C357 RX | `0x08097D30` | `0x08067D30` |
| C36A RX | `0x08097D74` | `0x08067D74` |
| C37B RX | `0x08097EB6` | `0x08067EB6` |
| C5A8 RX | `0x08098108` | `0x08068108` |
| C36E Sender | `0x08098BDC` | `0x08068BDC` |
| C371 Sender | `0x08098CE2` | `0x08068CE2` |
| Commitworker | `0x080A6848` | `0x08076848` |
| Copy-/Eraseworker | `0x080A70EC` | `0x080770EC` |
| C5A8 Worker | `0x080A8628` | `0x08078628` |
| Cancelworker | `0x080A8D68` | `0x08078D68` |
| Jumpworker | `0x080A9354` | `0x08079354` |
| MD5-Routine | `0x080A964C` | `0x0807964C` |
| VTOR-Setter | `0x080AA3E0` | `0x0807A3E0` |
| EEPROM Write | `0x08080C08` | `0x08050C08` |
| EEPROM Read | `0x08080C5E` | `0x08050C5E` |
| Flash Unlock | `0x080BD144` | `0x0808D144` |
| Flash Page Erase | `0x080BD1C0` | `0x0808D1C0` |
| Flash Program Word | `0x080BD2E4` | `0x0808D2E4` |
| Flash Lock | `0x080BD190` | `0x0808D190` |

---

# 4. C5A8-Staging

Der eingehende C5A8-Block enthält einen 6-Byte-Header und 168 Firmwarebytes.

Die Firmwaredaten werden zunächst in RAM gepuffert und anschließend linear in den Stagingbereich geschrieben.

Für Blockzählung ab 1 gilt:

```text
Block 1 → 0x080A1000
Block 2 → 0x080A10A8
Block 3 → 0x080A1150
...
```

Adressformel:

```text
0x080A0F58 + block_no * 0xA8
```

Pro Block werden exakt:

```text
42 × 32 Bit = 168 Byte
```

programmiert.

Es findet in diesem Pfad keine Relocation, Dekompression, Entschlüsselung oder Pointeranpassung statt.

---

# 5. Dynamischer Gegenbeleg gegen ein separates Phase-A-Image

Der originale LTE-Prozess `phnixIot4G` wurde in einer isolierten QEMU-Umgebung bis zum C5A8-Datenpfad ausgeführt.

Dabei wurden:

```text
1712 C5A8-Frames
```

beobachtet. Die 168-Byte-Nutzdaten wurden blockweise rekonstruiert.

Ergebnis:

```text
rekonstruierte Nutzbytes: 287598
SHA-256: 6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

Damit ist dynamisch bestätigt:

> Das vom LTE-Modem als C5A8 übertragene Image ist exakt die bekannte V3.3-Datei.

Der letzte Block enthält 150 reale Bytes und 18 Byte `0xFF`-Padding.

**Bewertung: bestätigt.**

---

# 6. Descriptoren

## Stagingdescriptor `0x080A0000`

Der Descriptor umfasst 64 Byte:

```text
Offset 0       0x63
1..12          0x00
13..24         12-Byte Build-/Zielkennung
25..28         Dateilänge
29..60         MD5 als 32 ASCII-Hexzeichen
61..62         CRC16 über Bytes 0..60
63             Steuer-/Reservebyte
```

## Persistente Kopie `0x0804F800`

Der Descriptor wird später ohne Transformation kopiert:

```text
0x080A0000 → 0x0804F800
```

Kopiermenge:

```text
16 × 32 Bit = 64 Byte
```

---

# 7. Erase-Bereiche

Vor der Candidate-/Final-Copy wird der Zielbereich gelöscht.

Die Erase-State-Machine löscht zusammenhängend:

```text
0x08050000 … 0x0809BFFF
```

Dabei berücksichtigt die Adressarithmetik zwei Pagegrößen:

```text
unterhalb 0x08080000: 2 KiB
ab       0x08080000: 4 KiB
```

Der Wechsel bei `0x08080000` ist damit eine Flash-Bank-/Page-Grenze und **keine Linkbasis eines zweiten Mainimages**.

Zusätzlich wird die Descriptorpage `0x0804F800` separat gelöscht.

---

# 8. Image-Copy

Nach erfolgreicher erster MD5-Prüfung kopiert die Firmware direkt:

```text
Quelle: 0x080A1000 + offset
Ziel:   0x08050000 + offset
```

Die innere Schleife kopiert:

```text
100 × 32 Bit = 400 Byte
```

pro Chunk.

Maximal:

```text
0x300 = 768 Chunks
768 × 400 = 307200 Byte = 0x4B000
```

Damit entspricht das Copyfenster exakt der maximal von C357 akzeptierten Dateilänge.

Die Kopie ist eine direkte Word-for-Word-Kopie:

```c
word = *(uint32_t *)(0x080A1000 + offset);
flash_program_word(0x08050000 + offset, word);
```

Keine Relocation oder Transformation wurde gefunden.

---

# 9. MD5-Prüfungen

## MD5 #1 – Staging

Nach dem letzten C5A8-Block:

```text
MD5(base=0x080A1000, length=C357.length)
```

gegen den erwarteten MD5 aus C357.

```text
MD5 OK  → C36E Status 3
MD5 NOK → C36E Status 4
```

## MD5 #2 – Zielimage

Nach der Kopie:

```text
MD5(base=0x08050000, length=Descriptor.length)
```

gegen denselben erwarteten MD5.

Damit wird sowohl der Download als auch die Flash-Copy vollständig verifiziert.

---

# 10. Vector Table und Chain-Jump

Der Jumpworker liegt korrigiert bei ungefähr:

```text
0x08079354
```

Für den Pfad `0x08050000` prüft er zuerst den dort gespeicherten MSP auf einen plausiblen SRAM-Wert.

Mit der bekannten Datei:

```text
[0x08050000] = 0x2000EB90
[0x08050004] = 0x080927D1
```

Die Prüfung besteht.

Anschließend:

```text
MSP = 0x2000EB90
PC  = 0x080927D1
BLX PC
```

Da `0x080927D1` bei Basis `0x08050000` innerhalb derselben Datei liegt, startet exakt der Reset-/Startupcode des gerade kopierten Images.

Eine unveränderte Kopie nach `0x08050000` ist damit korrekt ausführbar.

---

# 11. VTOR

Die Firmware enthält einen Setter, korrigiert ungefähr bei:

```text
0x0807A3E0
```

Dieser setzt:

```text
SCB->VTOR = 0x08050000
```

und wird im normalen Initialisierungspfad aufgerufen.

Damit ist `0x08050000` nicht nur temporärer Datenspeicher, sondern die normale Vector-Table-Basis des Images.

**Bewertung: bestätigt.**

---

# 12. Direkte und indirekte Bootziele

## `0x08000000`

Ein eigener Chain-Jump liest MSP und PC aus dem Vector Table bei `0x08000000`. Das ist der residente Loader-/Recoverybereich.

## `0x08050000`

Ein zweiter eigener Chain-Jump liest MSP und PC aus `0x08050000`. Dieser Pfad startet das installierte Mainimage.

## `0x08080000`

Ein entsprechender Vector-/Bootjump auf `0x08080000` wurde nicht gefunden.

`0x08080000` ist innerhalb des bekannten Images lediglich eine interne Flash-Grenze.

---

# 13. C36E Status 3, 5 und 6

## Status 3

```text
Staging-MD5 über 0x080A1000 erfolgreich
```

## Status 5

Status 5 entsteht erst nach der späteren Candidate-/Commitphase. Dazu müssen CRC-geschützte Commit-/Candidatezustände gültig sein und die relevanten internen Commitflags gesetzt sein.

Interpretation:

```text
Candidate vollständig verifiziert / Handoff vorbereitet
```

Die Bedingungen sind bestätigt, die exakte Herstellerbezeichnung bleibt offen.

## Status 6

Status 6 gehört zu späteren Post-MD5-Fehlern, insbesondere Descriptor-, Copy-, Candidate- oder Commitverifikation.

---

# 14. EEPROM-Zustände

Bekannte CRC-geschützte Records:

```text
0x3D8  Role-State
0x3E0  Transition-/Recovery-State
0x3E8  Candidate-/Commit-State
0x3F0  C357/Download-Metadaten-ready
```

## Role

Es werden mindestens die Werte 1 und 2 verwendet.

Bestätigt ist, dass sie unterschiedliche Loader-/Normalzustände markieren.

Sehr wahrscheinlich:

```text
Role 1 = Update/Transition
Role 2 = normaler Main-App-Zustand
```

Die Herstellerbenennung bleibt offen.

---

# 15. Bewertung der früheren Zwei-Phasen-Hypothese

Frühere Hypothese:

```text
Phase A: kleines IAP-Image für 0x08050000
Phase B: 287598-Byte Mainimage für 0x08080000
```

Diese Hypothese entstand ausschließlich aus der falschen Annahme, die bekannte Datei sei für `0x08080000` gelinkt.

Die neue Analyse zeigt dagegen:

- bekannte BIN ist für `0x08050000` gelinkt
- C5A8 rekonstruiert dynamisch exakt diese BIN
- Copyziel ist `0x08050000`
- es gibt keine Relocation
- Vector Table passt exakt
- Reset Handler passt exakt
- VTOR wird auf `0x08050000` gesetzt
- kein Bootjump nach `0x08080000` wurde gefunden

**Entscheidung:** Ein separates Phase-A-/IAP-Image ist nicht erforderlich und in der bisher angenommenen Form **widerlegt**.

---

# 16. Was weiterhin offen bleibt

Trotz geklärter Linkbasis bleibt eine wichtige Architekturfrage offen:

Die Erase-/Copy-State-Machine liegt selbst innerhalb des bekannten Images. Wenn ein aktuell laufendes Image bei `0x08050000` seinen eigenen Zielbereich löscht, muss der destruktive Promotionpfad aus einem anderen sicheren Ausführungskontext heraus laufen.

Mögliche Kandidaten:

- residenter Loader bei `0x08000000`
- anderer persistenter Role-/Transition-Zustand
- temporärer Codekontext außerhalb des zu löschenden Bereichs

Ein vollständiger RAM-residenter Copyworker wurde in der bekannten BIN bislang nicht bestätigt.

Diese Frage betrifft den Recovery-/Promotionmechanismus, **nicht mehr die Linkbasis oder die Identität des übertragenen Images**.

---

# 17. Speicherkarte

```text
0x08000000
  residenter Loader / Recovery

...

0x0804F800
  persistenter 64-Byte-Image-Descriptor

0x08050000
  Vector Table der bekannten V3.3
  Hauptimage
  Größe 0x4636E
  Ende bei 0x0809636D

0x08080000
  interne Flash-Bank-/Page-Grenze innerhalb desselben Images

0x0809AFFF
  Ende des maximalen 0x4B000-Candidatefensters

0x0809B000..0x0809BFFF
  zusätzliche Erase-Page

0x080A0000
  Staging-Descriptor

0x080A1000
  Staging-Firmware
  max. 0x4B000 Byte

0x080EBFFF
  Ende des maximalen Stagingfensters
```

---

# 18. Sicherheitsbewertung für C5A8

Die frühere Aussage:

```text
Die bekannte Mainfirmware darf nicht als erstes C5A8-Image gesendet werden,
weil sie für 0x08080000 gelinkt sei.
```

ist **widerlegt**.

Strukturell ist die bekannte Datei sehr wahrscheinlich genau das erwartete C5A8-Image.

Zusätzlich ist dies durch den originalen LTE-Prozess dynamisch bestätigt: Die 1712 C5A8-Blöcke rekonstruieren exakt diese Datei.

Das bedeutet jedoch **nicht**, dass ein echter Schreibtest automatisch sicher ist. Vor einem realen OTA bleiben insbesondere Loader-/Recovery- und Power-Loss-Verhalten kritisch.

---

# 19. Noch benötigte Artefakte

Für die Frage „welches Image sendet C5A8 und wo läuft es?“ sind keine wesentlichen Artefakte mehr offen.

Für die letzten Recoveryfragen wären weiterhin wertvoll:

1. residenter Loader-/Bootloaderdump ab `0x08000000`
2. vollständiger realer OTA-Mitschnitt bis nach C36E Status 5 und Handoff
3. Flash-/EEPROM-Zustand unmittelbar vor und nach einem Herstellerupdate

---

# 20. Dokumentationskorrekturen

Durch die korrigierte Linkbasis müssen ältere Mainboard-OTA-Dokumente überprüft werden auf:

- Code-VAs, die mit Basis `0x08080000` berechnet wurden
- Aussagen „Mainimage ist für 0x08080000 gelinkt“
- Aussagen „0x08050000 enthält ein separates kleines Phase-A-/IAP-Image“
- Aussagen „die bekannte 287598-Byte-Datei darf nicht als erstes C5A8-Image gesendet werden“
- Aussagen über einen zwingenden zweiten Mainimage-Transfer nach `0x08080000`

Die RAM-Adressen, Wireframes, C5A8-Blockdaten, EEPROM-Offets und physischen Flashziele `0x080A0000`, `0x080A1000`, `0x0804F800`, `0x08050000` bleiben davon unberührt.
