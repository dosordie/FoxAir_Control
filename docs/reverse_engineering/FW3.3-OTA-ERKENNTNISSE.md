# Mainboard-Firmware V3.3 – OTA-, Flash- und Bootpfad

Stand: 23. August 2026

Diese Datei dokumentiert den statisch und dynamisch rekonstruierten OTA-Empfangs-, Flash- und Bootpfad der Mainboard-Firmware `82400644 / V3.3`.

> **Wichtige Korrektur:** Die 287598-Byte-Datei ist **für `0x08050000` gelinkt**, nicht für `0x08080000`. Frühere Mainboard-Funktionsadressen, die mit Basis `0x08080000` berechnet wurden, lagen deshalb systematisch `+0x30000` zu hoch. RAM-Adressen, echte Flashzieladressen und RS485-Register sind davon nicht betroffen.

## Bewertungsstufen

- **bestätigt** – direkt im Binary oder dynamisch nachgewiesen
- **sehr wahrscheinlich** – Datenfluss geschlossen, Herstellerbezeichnung offen
- **offen** – hierfür fehlt Code oder ein externer Artefakt

---

# 1. Firmwarebasis und Vector Table

Referenzdatei:

```text
Größe:          287598 Byte = 0x4636E
MD5:            CEB6A4BF386FF644E23E410023E74673
SHA-256:        6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
Imagebasis:     0x08050000
Initial MSP:    0x2000EB90
Reset Handler:  0x080927D1
```

Die ersten beiden 32-Bit-Werte der BIN lauten:

```text
BIN+0x00 = 0x2000EB90
BIN+0x04 = 0x080927D1
```

Mit Basis `0x08050000` liegt der Reset Handler bei Datei-Offset:

```text
0x080927D0 - 0x08050000 = 0x427D0
```

und dort befindet sich tatsächlich der Startup-/Resetpfad.

Zusätzliche harte Belege:

- BIN-Offset `0xB0` enthält einen gültigen Vector-Eintrag `0x08053747`, passend zu Basis `0x08050000`.
- Der String `824006440033` liegt bei BIN-Offset `0x42780` und damit exakt bei `0x08092780`; genau diese Adresse verwendet C544.
- Die Firmware setzt `SCB->VTOR` auf `0x08050000`.

**Bewertung: bestätigt.**

---

# 2. Korrigierte wichtige Mainboard-Funktionsadressen

| Funktion | Korrekte VA |
|---|---:|
| C544-Erkennung/Senderbereich | `0x080678xx–0x08068Cxx` |
| C350 RX | `0x08067CE4` |
| C357 RX | `0x08067D30` |
| C36A RX | `0x08067D74` |
| C37B RX | `0x08067EB6` |
| C5A8 RX | `0x08068108` |
| C36E Sender | `0x08068BDC` |
| C371 Sender | `0x08068CE2` |
| Commitworker | `0x08076848` |
| Copy-/Eraseworker | `0x080770EC` |
| C5A8 Worker | `0x08078628` |
| Cancelworker | `0x08078D68` |
| Jumpworker | `0x08079354` |
| MD5-Funktion | `0x0807964C` |
| VTOR-Setter | `0x0807A3E0` |
| EEPROM Write | `0x08050C08` |
| EEPROM Read | `0x08050C5E` |
| Flash Unlock | `0x0808D144` |
| Flash Page Erase | `0x0808D1C0` |
| Flash Program Word | `0x0808D2E4` |
| Flash Lock | `0x0808D190` |

---

# 3. Relevante RAM-Strukturen

```text
OTA-Basis:               0x200133F8
C5A8-RX-Buffer:          0x20013458
C5A8-Daten ab Header:    0x2001345E
C5A8-Staging-RAM:        0x20013C6C
OTA-State:               0x20014434
Metadaten:               0x20016710
Commit-/Boot-Control:    0x2001660C
Copy-/Candidate-State:   0x20015D7C
```

Diese RAM-Adressen waren von der Rebasing-Korrektur nicht betroffen.

---

# 4. C350 – Ziel-/Buildvergleich

C350 vergleicht eine 12-Byte-Kennung:

```text
Bytes 0..7   Produkt-/Zielidentität
Bytes 8..11  Build-/Versionsanteil
```

Ergebnis:

```text
Ziel unpassend oder Build identisch → C36E Status 0
Ziel passend, Build verschieden    → C36E Status 1
```

C350 allein verändert nur RAM; kein Flash- oder EEPROM-Write wurde gefunden.

---

# 5. C357 – Dateilänge und MD5

Layout:

```text
Byte 0       reserviert/Kontext
Byte 1       0x63
Byte 2       reserviert/Kontext
Byte 3..5    Dateilänge, 24 Bit Big Endian
Byte 6..37   erwarteter MD5 als 32 ASCII-Hexzeichen
```

Grenze:

```text
length <= 0x4B000 = 307200 Byte
```

Nach akzeptierten Metadaten:

```text
C36E Status 2
EEPROM 0x3F0 = 1 + CRC16
```

Noch keine Firmwaredaten werden in Flash geschrieben.

---

# 6. C5A8 – Blockformat und Staging

Der normale eingehende Handler liegt bei `0x08068108`; der eigentliche Worker bei `0x08078628`.

C5A8 enthält:

```text
Byte 0..1   SSID/Session
Byte 2..3   Gesamt-/letzte Blocknummer, Big Endian
Byte 4..5   aktuelle Blocknummer, Big Endian
Byte 6..173 Firmwaredaten, 168 Byte
```

Die 168 Datenbytes werden zunächst nach RAM `0x20013C6C` kopiert und anschließend von der separaten State-Machine programmiert.

Flashziel:

```text
dst = 0x080A0F58 + current_block * 0xA8 + word_index * 4
```

Bei Blockzählung ab 1:

```text
Block 1 → 0x080A1000
Block 2 → 0x080A10A8
...
```

Pro Block werden exakt:

```text
42 × 32 Bit = 168 Byte
```

programmiert.

Duplicate-Schutz:

```text
current_block == last_committed
→ nicht erneut flashen
→ C371 erneut senden
```

---

# 7. Dynamisch bestätigter C5A8-Inhalt

Der originale LTE-Prozess wurde isoliert ausgeführt. Dabei wurden exakt:

```text
1712 C5A8-Frames
287598 rekonstruierte Nutzbytes
SHA-256 = 6C635D8E9A1E7246EA492B81ACFF5B748E85CC86C0FE0DEF35C2F0A597E4389A
```

beobachtet.

Damit ist dynamisch bestätigt:

> **Der C5A8-Datenstrom ist bytegenau die bekannte V3.3-BIN.**

Der letzte Block enthält 150 reale Bytes plus 18 × `0xFF` Padding.

Siehe [`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md).

---

# 8. C371 – Block-ACK

C371 wird als FC10 gesendet:

```text
Unit:          0x63
Function:      0x10
Startregister: 0xC371
Quantity:      4 Register
Payload:       8 Byte
```

Payload:

```text
Byte 0..1   SSID/Session
Byte 2..3   ackA, erwartet 1
Byte 4..5   ackB
Byte 6..7   Blocknummer
```

Bedeutung:

```text
ackB = 1   weiterer Block erwartet
ackB = 2   letzter Block erfolgreich verarbeitet
```

C371 wird erst nach dem lokalen Block-Commit ausgelöst.

---

# 9. MD5-Prüfung des Stagingimages

Nach dem letzten Block:

```text
MD5(
  base   = 0x080A1000,
  length = C357.length
)
```

Vergleich gegen den C357-MD5.

```text
MD5 OK  → C36E Status 3
MD5 NOK → C36E Status 4
```

**Status 3 ist ein Erfolgspfad.**

---

# 10. Descriptoren `0x080A0000` und `0x0804F800`

Der 64-Byte-Descriptor ist bytegenau:

```text
Offset 0       0x63
Offset 1..12   0
Offset 13..24  12-Byte Ziel-/Buildkennung
Offset 25..28  Dateilänge, 32 Bit Big Endian
Offset 29..60  32 ASCII-MD5-Zeichen
Offset 61..62  CRC16 über Offset 0..60
Offset 63      Steuer-/Reservebyte
```

Er wird zunächst bei:

```text
0x080A0000
```

angelegt und später direkt nach:

```text
0x0804F800
```

kopiert.

Kopiergröße:

```text
16 × 32 Bit = 64 Byte
```

Keine Transformation oder Relocation.

---

# 11. Erase- und Copy-Bereich

Die große Erase-State-Machine löscht zusammenhängend:

```text
0x08050000 … 0x0809BFFF
```

und zusätzlich die Descriptorpage bei:

```text
0x0804F800
```

Die Adressarithmetik berücksichtigt 2-KiB- und 4-KiB-Flashpages sowie die Grenze bei `0x08080000`.

Wichtig:

> `0x08080000` ist **keine Imagebasis**, sondern eine Flash-/Page-Grenze innerhalb des Updatefensters.

Danach wird kopiert:

```text
Quelle: 0x080A1000 + offset
Ziel:   0x08050000 + offset
```

Chunkgröße:

```text
100 × 32 Bit = 400 Byte
```

maximal:

```text
768 × 400 = 307200 Byte = 0x4B000
```

Die Schleife ist eine direkte Word-for-Word-Kopie. Es gibt in diesem Pfad keine Dekompression, Relocation, Pointerkorrektur oder Headerentfernung.

---

# 12. Zweite MD5-Prüfung

Nach der Copy-Phase wird geprüft:

```text
MD5(
  base   = 0x08050000,
  length = descriptor.length
)
```

gegen denselben erwarteten MD5.

Damit schützt die Firmware zusätzlich gegen Fehler bei Erase/Program/Copy.

---

# 13. Warum die bekannte BIN bei `0x08050000` ausführbar ist

Nach der Copy enthält `0x08050000` unverändert:

```text
[0x08050000] = 0x2000EB90
[0x08050004] = 0x080927D1
```

Der Jumpworker bei `0x08079354`:

1. prüft den ersten Vector-Wert auf plausiblen SRAM-MSP,
2. deinitialisiert Peripherie/Interrupts,
3. lädt MSP aus `[0x08050000]`,
4. lädt PC aus `[0x08050004]`,
5. springt per `BLX`.

Für die bekannte BIN ergibt sich:

```text
MSP = 0x2000EB90
PC  = 0x080927D1
```

Der PC liegt innerhalb derselben Datei bei Offset `0x427D1` und führt in den echten Reset-/Startupcode.

**Damit ist der direkte Chain-Jump konsistent und benötigt keine Relocation.**

---

# 14. VTOR

Die Firmware setzt im normalen Initialisierungspfad:

```text
SCB->VTOR = 0x08050000
```

über den Setter bei `0x0807A3E0`.

Auch das bestätigt `0x08050000` als tatsächliche Vector-/Imagebasis.

---

# 15. C36E Status 5 und 6

## Status 5

Der Commitworker bei `0x08076848` prüft CRC-geschützte Commitzustände und interne Flags `0x2001660C+0x2E/+0x2F`.

Erst nach erfolgreicher Candidate-/Copy-/MD5-/Commitphase wird:

```text
C36E Status 5
```

erzeugt.

**Bewertung:** bestätigt als später Handoff-/Commit-Erfolg; genaue Herstellerbezeichnung offen.

## Status 6

Wird in späteren Fehlerpfaden verwendet, insbesondere bei Descriptor-/Copy-/Candidate-/Commit-Verifikation.

```text
C36E Status 6 = Post-Copy-/Commitfehler
```

---

# 16. EEPROM-Zustände

## `0x3F0`

Metadaten-/Download-ready:

```text
C357 akzeptiert → 1 + CRC
C36A Cancel      → 0 + neue CRC
```

## `0x3E8`

Candidate-/Commitrecord, zwei Statusbytes plus CRC; erfolgreicher Pfad enthält `[1,1]`, später Übergang auf `[1,0]`.

## `0x3E0`

Transition-/Recoveryrecord, ebenfalls CRC-geschützt.

## `0x3D8`

Role-State mit erlaubten Werten 1/2 plus CRC.

**Bestätigt:** persistent und OTA-relevant. Exakte Herstellerbezeichnungen für Role 1/2 bleiben offen.

---

# 17. Direkte Sprungziele

Gefunden:

```text
0x08000000   residenter Loader-/Recoverybereich
0x08050000   installierte V3.3-App / Vector Table
```

Nicht gefunden:

```text
0x08080000   kein bestätigter Boot-/Vector-Jump
```

`0x08080000` ist daher kein zweiter Appslot in diesem nachgewiesenen Pfad.

---

# 18. Bewertung der früheren Zwei-Phasen-Hypothese

Frühere Hypothese:

```text
Phase A: separates kleines IAP nach 0x08050000
Phase B: bekannte 287598-Byte-Mainfirmware nach 0x08080000
```

Diese Hypothese beruhte auf der falschen Binärbasis und ist in dieser Form **widerlegt**.

Heute bestätigt:

```text
C5A8-Datenstrom
= exakt bekannte 287598-Byte-V3.3-BIN
= Imagebasis 0x08050000
```

Ein separates Phase-A-Image ist daher **nicht erforderlich und nicht belegt**.

---

# 19. Noch offener Architekturpunkt

Der resident ausgeführte Loader bei `0x08000000` liegt nicht als separates Binary vor. Deshalb bleiben folgende Punkte offen:

- Power-Loss-Policy während einer destruktiven Promotion
- genaue Role-1/Role-2-Bedeutung beim Boot
- Recovery bei ungültigem Candidate
- eventuelle Wiederaufnahme nach unterbrochenem Copy/Erase

Das ist inzwischen der wesentliche verbliebene Sicherheitsblocker; die Link-/Copy-Frage selbst ist geklärt.

---

# 20. Sicherheitsfazit

Die bekannte V3.3-Datei ist strukturell genau der Image-Typ, den der nachgewiesene C5A8→Staging→Copy→`0x08050000`-Pfad erwartet.

Daraus folgt:

- **„V3.3 kann nicht als C5A8-Image dienen, weil sie für `0x08080000` gelinkt ist“ → widerlegt.**
- **„Die bekannte V3.3 ist wahrscheinlich genau das C5A8-Image“ → bestätigt durch dynamische Rekonstruktion.**
- **„Ein selbst ausgelöster echter OTA ist deshalb risikolos“ → nicht bestätigt.**

Für einen echten Schreibtest fehlen weiterhin die vollständige Recovery-/Bootloaderanalyse und ein klarer Hardware-Recoveryweg.
