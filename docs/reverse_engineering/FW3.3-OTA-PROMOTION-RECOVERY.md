# Mainboard-Firmware V3.3 – OTA Promotion, Abbruch und Recovery

Stand: 23. August 2026

Diese Datei dokumentiert den aktuell belegbaren Promotions-, Abbruch- und Recoverypfad der Mainboard-Firmware `82400644 / V3.3` auf Basis der korrigierten Imagebasis `0x08050000`.

Wichtig: Ein separates Phase-A-/IAP-Image wird hier **nicht** mehr vorausgesetzt. Die bekannte 287598-Byte-Datei ist selbst für `0x08050000` gelinkt und wird vom originalen LTE-Prozess bytegenau als C5A8-Datenstrom übertragen.

## Bewertungsstufen

- **bestätigt** – direkt aus der bekannten V3.3-Firmware bzw. dynamisch belegt
- **stark abgeleitet** – Datenfluss und Architektur sprechen klar dafür, letzter fehlender Code liegt aber außerhalb des Images
- **offen ohne Loader-Dump** – nur der residente Code ab `0x08000000` kann die Frage endgültig beantworten

---

# 1. Relevante Funktionsadressen

| Funktion | Adresse | Rolle |
|---|---:|---|
| C350 RX | `0x08067CE4` | Ziel-/Buildangebot empfangen |
| C357 RX | `0x08067D30` | Dateilänge + MD5 empfangen |
| C36A RX | `0x08067D74` | Cancel empfangen |
| C37B RX | `0x08067EB6` | Status-ACK 3..7 |
| C350/C357-Verarbeitung | `0x08076A88` ff. | Zielvergleich / Metadaten |
| Commit-/Statusworker | `0x08076848` | EEPROM-Commit / C36E Status 5 |
| Promotion-/Copyworker | `0x080770EC` | Target-Erase, Descriptor-Copy, Image-Copy, MD5 #2 |
| C5A8-Worker | `0x08078628` | Blockempfang / Staging-Flash |
| Cancelworker | `0x08078D68` | C36A, EEPROM-Clear, optional Staging-Erase |
| Transitionworker | `0x08079040` | 600-Zyklen-Gates, Role/Loader-Transition |
| Jumpworker | `0x08079354` | Chain-Jump `0x08000000` / `0x08050000` |
| MD5 | `0x0807964C` | Gesamtimage-MD5 |
| VTOR-Setter | `0x0807A3E0` | `SCB->VTOR = 0x08050000` |
| EEPROM Write | `0x08050C08` | externer I²C-EEPROM |
| EEPROM Read | `0x08050C5E` | externer I²C-EEPROM |
| Role setzen | `0x080763E2` | Role 1/2 + CRC nach EEPROM `0x3D8` |
| Flash Unlock | `0x0808D144` | STM32 Flash |
| Flash Lock | `0x0808D190` | STM32 Flash |
| Flash Page Erase | `0x0808D1C0` | STM32 Flash |
| Flash Program Word | `0x0808D2E4` | STM32 Flash |

---

# 2. C350 und C36E Status 0

Der C350-RX-Pfad beginnt bei `0x08067CE4`. Die eigentliche Auswertung liegt um `0x08076A88`.

Die 12-Byte-Kennung wird in zwei Stufen verglichen:

```text
Bytes 0..7   Ziel-/Produktkennung
Bytes 8..11  Build-/Versionsanteil
```

Status 0 entsteht bei:

```text
Zielkennung ungleich
ODER
Zielkennung gleich + Build identisch
```

Der Pfad setzt lediglich die RAM-Status-/Sendeflags für C36E Status 0 und räumt diese anschließend wieder ab.

## Bestätigt

C350 -> Status 0 verursacht keinen Aufruf von:

```text
EEPROM Write      0x08050C08
Flash Erase       0x0808D1C0
Flash Program     0x0808D2E4
Jumpworker        0x08079354
```

Es wird auch kein späterer Boot-/Commitzustand in `0x2001660C` aktiviert.

Damit gilt:

```text
C350 + C36E Status 0
= RAM-basierter Ablehnungs-/Keine-Aktualisierungspfad
```

Status 0 ist aber **kein globaler OTA-Reset**. Bereits vorher vorhandene persistente OTA-Records werden dadurch nicht pauschal gelöscht.

Ein dedizierter verzögerter Flash-/EEPROM-Job nach Status 0 wurde nicht gefunden.

---

# 3. C350 Status 1 ohne C357

Bei passender Zielkennung und abweichendem Build wird die neue 12-Byte-Kennung in die OTA-RAM-Metadaten übernommen und C36E Status 1 gesendet.

Bis zu diesem Punkt:

```text
RAM      ja
EEPROM   nein
Flash    nein
Jump     nein
Reset    nein
```

## Timeout

In der Mainboard-V3.3 wurde **kein eigener C350->C357-Wartetimeout** gefunden.

Die bekannten `0x7530 = 30000`-Zähler gehören zu späteren Daten-/Status-/Retrypfaden und dürfen nicht als C350->C357-Timeout interpretiert werden.

Folge:

- normaler Regel-/Warmlinkbetrieb läuft weiter,
- der RAM-Handshakestate kann bis zu einem später eintreffenden C357 bestehen bleiben,
- ein Neustart verwirft diesen C350-only-Zustand, weil bis dahin keine Persistenz geschrieben wurde.

---

# 4. C357 – erste persistente OTA-Grenze

C357 übernimmt Dateilänge und erwarteten MD5.

Grenze:

```text
length <= 0x4B000 = 307200 Byte
```

Nach akzeptierten Metadaten:

```text
C36E Status 2
```

und erstmals ein persistenter Record:

```text
EEPROM 0x3F0
Byte 0     Ready/Pending
Byte 1..2  CRC16
```

Damit gilt:

```text
C350  -> nur RAM
C357  -> erstmals EEPROM
C5A8  -> erstmals Firmwaredaten in Flash
```

---

# 5. Letzter C5A8 und MD5 #1

Der C5A8-Worker `0x08078628` schreibt 168 Firmwarebytes pro Block linear in das Stagingimage ab:

```text
0x080A1000
```

Nach dem letzten gültigen Block wird das komplette Stagingimage über exakt die C357-Dateilänge geprüft:

```text
MD5(
    base   = 0x080A1000,
    length = C357.length
)
```

MD5-Funktion:

```text
0x0807964C
```

Ergebnis:

```text
MD5 OK  -> C36E Status 3
MD5 NOK -> C36E Status 4
```

**Status 3 ist bestätigt ein Erfolgspfad.**

---

# 6. Descriptor und Target-Promotion

Der Descriptor liegt zunächst bei:

```text
0x080A0000
```

und wird später nach:

```text
0x0804F800
```

kopiert.

Bestätigtes 64-Byte-Format:

```text
0        0x63
1..12    0x00
13..24   12-Byte Ziel-/Buildkennung
25..28   Dateilänge
29..60   MD5 ASCII[32]
61..62   CRC16 über 0..60
63       Steuer-/Reservebyte
```

Descriptor-Copy:

```text
Quelle  0x080A0000
Ziel    0x0804F800
Länge   64 Byte
```

ohne Transformation.

---

# 7. Target-Erase

Der Promotionworker `0x080770EC` enthält einen 124-Schritt-Erasepfad.

Bei Zähler `124..97` werden 4-KiB-Pages gelöscht:

```text
0x0809B000
...
0x08080000
```

Bei Zähler `96..1` werden 2-KiB-Pages gelöscht:

```text
0x0807F800
...
0x08050000
```

Zusätzlich wird die Descriptorpage `0x0804F800` gelöscht.

Damit betroffen:

```text
Descriptor: 0x0804F800..0x0804FFFF
Image:      0x08050000..0x0809BFFF
```

Die bekannte V3.3-Datei selbst reicht nur bis ungefähr `0x0809636D`.

---

# 8. Image-Copy

Der Copyworker liest direkt aus dem Stagingbereich und programmiert das Target:

```text
Quelle: 0x080A1000 + offset
Ziel:   0x08050000 + offset
```

Pro innerem Lauf:

```text
100 Words = 400 Byte
```

Maximal:

```text
768 * 400 = 307200 Byte = 0x4B000
```

Es existiert in diesem Pfad keine nachgewiesene:

- Relocation,
- Dekompression,
- Entschlüsselung,
- Pointerkorrektur,
- Headerentfernung.

Die Daten werden Word für Word kopiert.

---

# 9. MD5 #2

Nach der Kopie wird erneut geprüft:

```text
MD5(
    base   = 0x08050000,
    length = Descriptor.length
)
```

gegen denselben erwarteten MD5.

Damit schützt der OTA-Pfad getrennt gegen:

```text
LTE/RS485 -> Stagingfehler
und
Staging -> Target-Programmierfehler
```

---

# 10. Candidate-/Commit-State und Status 5

Nach erfolgreicher Candidateprüfung setzt der Promotionworker im RAM-Controlblock `0x2001660C`:

```text
+0x2E = 1
+0x2F = 1
```

Dazu wird ein CRC-geschützter EEPROM-Record geschrieben:

```text
EEPROM 0x3E8
```

Der Commitworker `0x08076848` liest diesen Record wieder ein und verlangt:

```text
CRC gültig
+0x2E == 1
+0x2F == 1
```

Dann entsteht:

```text
C36E Status 5
```

und der persistente Record wird weitergeschaltet, u. a. von:

```text
[1,1] -> [1,0]
```

mit neuem CRC.

Damit liegt Status 5 **hinter Copy, MD5 #2 und persistentem Candidate-/Commitstate**.

---

# 11. Role- und Transition-Persistenz

## EEPROM `0x3D8` – Role

Funktion:

```text
0x080763E2
```

`0x080763E2(1)` schreibt:

```text
Role = 1
+ CRC16
-> EEPROM 0x3D8
```

`0x080763E2(2)` entsprechend Role 2.

Die normale Applikation stellt Role 2 her bzw. erwartet sie.

**Stark abgeleitet:**

```text
Role 2 = normaler Appzustand
Role 1 = Loader/Promotion/Recovery
```

Die exakten PHNIX-Namen sind unbekannt.

## EEPROM `0x3E0` – Transition

Ein weiterer 4-Byte-Record speichert zwei Transitionbytes plus CRC.

Im Transitionworker wird dieser Record vor einem späteren Loader-Handoff aktualisiert.

---

# 12. Zwei getrennte 600-Zyklen-Gates

Im Transitionworker `0x08079040` wurden zwei getrennte Pfade gefunden.

## Gate A – Promotion-Erase freigeben

Wenn der zugehörige Zustand aktiv ist, läuft ein 16-Bit-Counter bis:

```text
0x258 = 600
```

Bei exakt 600:

```text
Stateflag wird gelöscht
Erasecounter = 0x7C = 124
```

Damit wird der oben dokumentierte Target-Erase des Promotionworkers gestartet.

## Gate B – Loader-Handoff

Ein anderer Transitionpfad zählt ebenfalls bis:

```text
600
```

Vor Ablauf werden unter anderem persistente Transitiondaten nach EEPROM `0x3E0` geschrieben.

Bei 600 passiert direkt:

```text
0x080763E2(1)      # Role 1 persistent nach EEPROM 0x3D8
Boot-Control +0x42 = 0
Boot-Control +0x22 = 1
```

`+0x22` ist der Eingang des Jumpworkers für `0x08000000`.

Das ist ein wichtiger neuer Beleg dafür, dass PHNIX vor mindestens einem kritischen OTA-Übergang bewusst:

1. Transition-State persistiert,
2. Role 1 persistiert,
3. anschließend den residenten Loader aktiviert.

---

# 13. Jumpworker

Der Jumpworker liegt bei:

```text
0x08079354
```

## `+0x22` -> `0x08000000`

Er prüft den initialen Stackpointer des Vector Tables auf SRAM-Plausibilität.

Dann:

```text
Peripherie deinitialisieren
Interrupts deaktivieren
MSP = [0x08000000]
PC  = [0x08000004]
BLX PC
```

Das ist ein direkter Chain-Jump, kein bestätigter AIRCR-Systemreset.

## `+0x23` -> `0x08050000`

Analog:

```text
MSP = [0x08050000]
PC  = [0x08050004]
BLX PC
```

Für V3.3:

```text
MSP = 0x2000EB90
PC  = 0x080927D1
```

---

# 14. VTOR, MSP, AIRCR

Die Funktion `0x0807A3E0` setzt im normalen Startup:

```text
SCB->VTOR = 0x08050000
```

Der OTA-Jumpworker setzt ausdrücklich MSP vor dem Chain-Jump.

Ein entsprechender OTA-Pfad über PSP wurde nicht gefunden.

`SCB->AIRCR` kommt im Binary vor, aber im bekannten OTA-Promotionpfad wurde **kein belegter SYSRESETREQ-Schreibzugriff** gefunden.

Damit erfolgt der bekannte Handoff per Chain-Jump.

---

# 15. Die verbleibende harte Unsicherheit: Ausführung während Target-Erase

Hier liegt der derzeit entscheidende Sicherheitsblocker.

Der Promotionworker selbst liegt bei:

```text
0x080770EC
```

also in der Page:

```text
0x08077000..0x080777FF
```

Diese Page gehört zum Target-Erasebereich `0x08050000..0x0809BFFF`.

Auch die verwendeten Flash-Helfer liegen innerhalb des zu löschenden Bereichs:

```text
0x0808D144  Unlock
0x0808D190  Lock
0x0808D1C0  Erase
0x0808D2E4  Program Word
```

also in der Page `0x0808D000..0x0808DFFF`, die vom 4-KiB-Erasepfad ebenfalls gelöscht wird.

Würde dieser Worker während des kompletten Erase direkt aus der aktuell laufenden `0x08050000`-Imageinstanz ausgeführt, würde er zunächst seine Flash-Helfer und später sogar seinen eigenen Code löschen.

Das kann nicht der vollständige reale Ausführungskontext sein.

## Suche nach RAM-Ausführung

Gezielt gesucht wurde nach:

- Kopie des Promotionworkers nach SRAM,
- RAM-Funktionspointer,
- `BLX` auf `0x200xxxxx`,
- Startup-Copy-Tabelle für diesen Worker,
- RAM-Kopie der Flash-Helfer.

Im bekannten V3.3-Binary wurde dafür **kein belastbarer Nachweis** gefunden.

Der normale Scheduler ruft `0x080770EC` direkt per `BL` auf.

---

# 16. Aktuell stärkste Architekturinterpretation

Die zwei 600-Zyklen-Gates, die persistente Role-Funktion und der direkte Loader-Jump liefern jetzt einen stärkeren Hinweis als zuvor:

```text
Transition-State -> EEPROM 0x3E0
Role 1          -> EEPROM 0x3D8
Boot-Control +0x22
        ↓
Chain-Jump 0x08000000
```

**Stark abgeleitet:** Der residente Loader bei `0x08000000` ist Teil des sicheren Promotion-/Recoverykontexts und wertet die persistenten Role-/Transition-/Candidatezustände aus.

Was weiterhin **nicht** aus dem Mainimage beweisbar ist:

- ob der Loader selbst den kompletten Target-Erase ausführt,
- ob er denselben State-Algorithmus in eigener Implementierung besitzt,
- ob er eine unterbrochene Copy neu beginnt oder fortsetzt,
- ob er vor Boot zwingend Commit/MD5/Descriptor verlangt.

Ein separater Phase-A-/IAP-Download ist dafür nicht erforderlich und wird nicht angenommen; es geht ausschließlich um residenten Loadercode im bereits vorhandenen Bereich `0x08000000`.

---

# 17. Power-Loss-Matrix

| Zeitpunkt | Belegbarer Zustand | Risiko | Ohne Loader-Dump offen |
|---|---|---|---|
| vor Target-Erase | altes `0x08050000`-Image noch intakt, neues Staging vollständig | niedrig bis mittel | Bootet Loader alt oder setzt Promotion anhand EEPROM fort? |
| während Erase | Target teilweise/komplett gelöscht, Staging bleibt vorhanden | **hoch** | Erkennt Loader Pending-State und startet sicheren Re-Erase/Re-Copy? |
| während Copy | Target teilweise geschrieben, Staging vollständig | **hoch** | Verhindert Loader Boot nur anhand Vector Table und verlangt Commit/MD5? |
| nach Copy, vor MD5 #2 | Target wahrscheinlich vollständig, noch nicht final validiert | mittel bis hoch | Bootpolicy für uncommitted Candidate |
| nach MD5 #2, vor Commit | Target validiert, persistenter Commit evtl. noch alt | mittel | Recovery bei gültigem Image ohne aktualisierten Commitrecord |
| nach Commit, vor Handoff | Image validiert + Commit persistent | relativ niedrig | genaue Loaderinterpretation der Transitionrecords |
| nach Status 5, vor Jump | Candidate validiert und Commitpfad abgeschlossen | relativ niedrig | Verhalten bei ungeplantem Power-Cycle statt Chain-Jump |

---

# 18. Was direkt bewiesen ist

- C350 Status 0 schreibt weder Flash noch EEPROM.
- Status 0 ist kein globaler OTA-Reset.
- C350 Status 1 ist RAM-only.
- Es existiert kein belegter C350->C357-Wartetimeout.
- C357 ist der erste persistente Handshakeschritt (`0x3F0`).
- C5A8 schreibt das komplette Image nach `0x080A1000`.
- MD5 #1 prüft das Stagingimage.
- Status 3 = MD5 #1 erfolgreich.
- Descriptor wird von `0x080A0000` nach `0x0804F800` kopiert.
- Targetbereich `0x08050000..0x0809BFFF` wird gelöscht.
- Image wird direkt von `0x080A1000` nach `0x08050000` kopiert.
- MD5 #2 prüft das kopierte Target.
- Candidate-/Commit-Control wird CRC-geschützt nach EEPROM `0x3E8` geschrieben.
- Status 5 liegt hinter Copy, MD5 #2 und Commit.
- `0x080763E2(1)` setzt Role 1 persistent in EEPROM `0x3D8`.
- Ein 600-Zyklen-Pfad setzt danach `Boot-Control +0x22`.
- `+0x22` führt zum Chain-Jump `0x08000000`.
- `+0x23` führt zum Chain-Jump `0x08050000`.
- VTOR wird auf `0x08050000` gesetzt.
- kein belegter OTA-SYSRESETREQ-Pfad im Mainimage.
- Promotionworker und Flash-Helfer liegen selbst im Target-Erasebereich.

---

# 19. Was stark abgeleitet ist

Der residente Loader `0x08000000` ist sehr wahrscheinlich der sichere Ausführungskontext für mindestens einen Teil der kritischen Promotion-/Recoverysequenz.

Die stärksten Belege dafür sind:

1. persistenter Transition-State `0x3E0`,
2. persistente Role 1 `0x3D8`,
3. unmittelbar danach gesetztes Loader-Jumpflag `+0x22`,
4. direkter Chain-Jump auf `0x08000000`,
5. Unmöglichkeit, den vollständigen gefundenen Erasepfad ausschließlich aus dem gerade zu löschenden Targetimage auszuführen.

---

# 20. Was ausschließlich ein Loader-Dump entscheiden kann

Ein Dump und die Analyse von `0x08000000...` müssen noch beantworten:

1. Welche EEPROM-Records liest der Loader beim Power-on?
2. Welche Bedeutung haben Role 1/2 exakt?
3. Prüft der Loader `0x3E0`, `0x3E8`, `0x3F0`?
4. Führt er selbst Target-Erase/Copy aus?
5. Wie reagiert er auf einen teilweise gelöschten Targetbereich?
6. Wie reagiert er auf ein teilweise kopiertes Image?
7. Reicht ein plausibler Vector Table zum Boot oder ist Commit/MD5 Pflicht?
8. Wird eine unterbrochene Promotion vollständig wiederholt?
9. Gibt es Retry-/Bootattempt-/Watchdogzähler?
10. Existiert ein expliziter Recoverymodus bei beschädigtem Target?

---

# 21. Sicherheitsentscheidung für einen vollständigen echten OTA

Transport und Imageformat sind heute weitgehend geklärt. Die bekannte V3.3-Datei ist das korrekte `0x08050000`-Image und wurde dynamisch als vollständiger C5A8-Strom bestätigt.

Der verbleibende Blocker ist **nicht mehr das OTA-Wireformat oder die Imagebasis**, sondern ausschließlich die Recoverygarantie während der destruktiven Promotion.

Insbesondere kann ohne Loader-Dump nicht bewiesen werden, dass ein Stromausfall:

```text
während Target-Erase
oder
während Target-Copy
```

zuverlässig aus dem residenten Loader wiederhergestellt wird.

Darum gilt weiterhin:

> Ein echter vollständiger OTA-Test bis einschließlich Promotion/Boot ist ohne Loader-Dump oder gleichwertig sicheren Hardware-Recoveryweg nicht als ausfallsicher bewiesen.

Ein Vorhandshake bis C350/C357 ist davon getrennt zu bewerten und benötigt diesen Loader-Nachweis nicht.

## Verwandte Dokumente

- [`FW3.3-OTA-ERKENNTNISSE.md`](FW3.3-OTA-ERKENNTNISSE.md)
- [`FW3.3-OTA-VORTEST-SICHERHEIT.md`](FW3.3-OTA-VORTEST-SICHERHEIT.md)
- [`FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md`](FW3.3-IAP-COPY-SPRUNGPFAD-KORREKTUR.md)
- [`PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md`](PHNIX_OTA_DYNAMISCHE_VALIDIERUNG.md)
- [`PHNIX_OTA_WORKCHAT_UEBERGABE.md`](PHNIX_OTA_WORKCHAT_UEBERGABE.md)
