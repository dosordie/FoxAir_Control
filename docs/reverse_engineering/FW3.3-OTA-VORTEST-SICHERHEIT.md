# Mainboard-Firmware V3.3 – Sicherheit eines abbrechbaren OTA-Vortests

Stand: 23. August 2026

Diese Datei untersucht ausschließlich einen OTA-Vorhandshake, der **vor dem ersten C5A8-Firmwaredatenblock** abgebrochen wird. Es wurde keine Verbindung zu ser2net oder realer Hardware geöffnet und nichts gesendet.

## Harte Sicherheitsgrenze

Für den hier beschriebenen Vortest gilt:

```text
C5A8 darf niemals gesendet werden.
```

Solange kein C5A8 verarbeitet wurde, bleibt `OTA+0x1C == 0`. Genau dieses Flag ist der Guard, der beim C36A-Abbruch den Flash-Erase-Zweig aktiviert. Deshalb ist ein C36A vor jedem C5A8 ein anderer und deutlich sichererer Pfad als ein Cancel nach Firmwaredaten.

## Relevante Funktionen

| Funktion | VA | Rolle |
|---|---:|---|
| zentraler OTA/FC10-Dispatcher | `0x08097Cxx–0x080981xx` | C350/C357/C36A/C37B/C5A8 empfangen |
| C350-Erkennung | `0x08097CE4` | C350 RX |
| C357-Erkennung | `0x08097D30` | C357 RX |
| C36A-Erkennung | `0x08097D74` | Cancel RX |
| C37B-Erkennung | `0x08097EB6` | Status-ACK RX |
| Status-/Handshake-Worker | `0x0809899C` | C36E/C544/C36C/C371 senden |
| OTA-Retry/EEPROM-Control | `0x080A6470` | Timeouts, Retries, EEPROM-Recovery |
| C5A8-Worker | `0x080A8628` | Datenblock/Flash-Staging |
| C36A-Abbruchworker | `0x080A8D68` | Cancel, EEPROM-Clear, optional Staging-Erase |
| Boot-/Jumpworker | `0x080A9354` | Jump `0x08000000` / `0x08050000` |
| EEPROM Write | `0x08080C08` | I²C-EEPROM schreiben |
| EEPROM Read | `0x08080C5E` | I²C-EEPROM lesen |
| Flash Unlock | `0x080BD144` | Flash |
| Flash Page Erase | `0x080BD1C0` | Flash |
| Flash Program Word | `0x080BD2E4` | Flash |
| Flash Lock | `0x080BD190` | Flash |

# C350

Der direkte C350-RX-Handler kopiert nur in RAM und setzt ein Verarbeitungsflag. Er enthält keinen Flash- oder EEPROM-Zugriff.

Der 12-Byte-Fingerprint wird in zwei Teile verglichen:

```text
Bytes 0..7   Ziel-/Produktidentität
Bytes 8..11  Build-/Versionsanteil
```

## Identische V3.3-Kennung

Wenn beide Teile identisch sind:

```text
C36E Status 0
```

Auswirkungen:

- RAM: RX-/Handshakeflags werden kurz gesetzt/zurückgesetzt
- EEPROM: kein durch C350 ausgelöster Write gefunden
- Flash: kein Zugriff
- Jump/Reset: keiner
- normale Regelung: läuft weiter

## Inkompatibles Ziel

Wenn bereits Bytes 0..7 nicht passen:

```text
C36E Status 0
```

Auswirkungen entsprechen dem identischen Build: kein EEPROM-, Flash-, Jump- oder Resetpfad.

## Kompatibles Ziel, anderer Build

Wenn Bytes 0..7 passen und Bytes 8..11 abweichen:

```text
C36E Status 1
```

Die angebotene 12-Byte-Kennung wird in die OTA-RAM-Metadaten übernommen. In diesem Schritt wurde kein persistenter EEPROM-Write und kein Flashzugriff gefunden.

Damit ist C350 Status 1 allein weiterhin RAM-basiert.

# C357 ohne C5A8

C357 übernimmt:

```text
Dateilänge: Payload Bytes 3..5, 24 Bit Big Endian
MD5:        Payload Bytes 6..37, 32 ASCII-Hexzeichen
Maximal:    0x4B000 = 307200 Byte
```

Nach akzeptierten Metadaten:

```text
C36E Status 2
```

Zusätzlich wird erstmals ein persistenter Updatezustand geschrieben:

```text
EEPROM Offset 0x3F0
Byte 0 = 1
Byte 1..2 = CRC16 über Byte 0
```

Noch immer gilt:

- keine Firmwaredaten werden in Flash geschrieben
- kein Staging-Flash wird beschrieben
- kein Candidate-Slot wird beschrieben
- kein Jump/Reset wird ausgelöst

Der C5A8-Worker wartet anschließend auf Daten. Sein Timeoutzähler erreicht bei:

```text
0x7530 = 30000 Worker-Aufrufen
```

den Timeoutpfad. Danach wird der aktive C5A8-Empfangszustand beendet und ein Re-Handshake/Recoverypfad angestoßen. Eine belastbare Umrechnung dieses Zählers in Sekunden ist aus der statischen Analyse noch nicht bewiesen und wird deshalb bewusst nicht angegeben.

# C36A / C36C – Cancel

C36A wird bei `0x08097D74` erkannt. Der RX-Handler setzt zunächst nur `OTA+0x1B = 1`.

Der Abbruchworker bei `0x080A8D68` verarbeitet das Flag:

1. `OTA+0x1B` wird wieder 0.
2. C5A8-/RX-Unterzustände werden beendet.
3. der aktive C5A8-Wartezustand wird gelöscht.
4. EEPROM `0x3F0` wird auf `Byte0=0` plus neue CRC gesetzt.
5. C36C wird als Cancel-Bestätigung vorbereitet.

## Entscheidend: Flash-Guard

Ein Flash-Erase wird nur aktiviert, wenn:

```text
OTA+0x1C == 1
```

Dieses Flag wird im C5A8-Worker erst bei `0x080A873E–0x080A8744` gesetzt, wenn:

```text
current_block >= total/last_block
```

also nachdem Firmwaredaten empfangen wurden und der letzte Block erreicht wurde.

Daraus folgt direkt:

```text
C36A vor jedem C5A8
→ OTA+0x1C = 0
→ kein Flash-Erase
```

## C36A nach Datenphase

Falls `OTA+0x1C == 1`, startet C36A eine Staging-Löschmaschine. Sie löscht den OTA-Descriptor und die Staging-Pages:

```text
0x080A0000
0x080A1000
0x080A2000
...
0x080EB000
```

also Descriptor plus 75 Datenpages à 4 KiB. Dieser Zweig ist für den hier definierten Vorhandshake nicht erreichbar, solange nie C5A8 gesendet wird.

## C36C

C36C wird als FC10 erzeugt:

```text
Unit          0x63
Function      0x10
Startregister 0xC36C
Quantity      2
Payload       00 63 00 01
```

Vollständiger erwarteter RTU-Frame inklusive CRC16:

```text
63 10 C3 6C 00 02 04 00 63 00 01 75 40
```

# C36E-Antworten des Vorhandshakes

C36E verwendet:

```text
Unit          0x63
Function      0x10
Startregister 0xC36E
Quantity      2
Payload       00 63 00 STATUS
```

Für die Vortest-relevanten Statuswerte ergeben sich:

```text
Status 0:
63 10 C3 6E 00 02 04 00 63 00 00 35 59

Status 1:
63 10 C3 6E 00 02 04 00 63 00 01 F4 99

Status 2:
63 10 C3 6E 00 02 04 00 63 00 02 B4 98
```

# C37B und fehlendes ACK

Der eingehende C37B-Handler bei `0x08097EB6` behandelt nur Status:

```text
3, 4, 5, 6 und 7
```

C36E Status 0, 1 und 2 benötigen in diesem Handler kein C37B-ACK.

Für Status 3–6 existiert ein Retrymechanismus:

```text
Retry-Schwelle: 0x7530 = 30000 interne Aufrufe
Retryanzahl:    bis 15
```

Ein fehlendes C37B erzeugt selbst keinen zusätzlichen Flashwrite; es führt zum erneuten Senden des jeweiligen Status. Dieser Pfad wird bei einem reinen C350/C357-Vortest nicht erreicht.

# Neustartverhalten

## nach C350

C350 allein hinterlässt nach bisherigem Nachweis keinen persistenten Updatezustand. Ein Neustart beginnt daher wieder aus dem normalen Role-2/Main-App-Zustand.

## nach C357

C357 hinterlässt den CRC-geschützten EEPROM-Record bei `0x3F0`. Beim nächsten Start wird dieser Record gelesen. Ein gültiger gesetzter Record stellt den OTA-/Re-Handshake-Zustand wieder her; er bewirkt aber keinen direkten Bootslot-Jump und keinen Flashwrite.

## nach C36A vor C5A8

C36A setzt `0x3F0` wieder auf 0 plus gültige CRC. Damit ist der C357-Ready-Zustand persistent gelöscht. Ein anschließender Neustart startet wieder ohne diesen pending-Metadatenzustand.

# Normalbetrieb während des Vorhandshakes

Die OTA-Funktionen sind in den normalen Hauptscheduler eingebettet. C350/C357/C36A werden parallel zu den normalen Kommunikations- und Regelpfaden abgearbeitet.

Für C350 und C357 wurden keine direkten Writer gefunden, die:

- die Wärmepumpe stoppen
- die Verdichterfreigabe löschen
- die Regel-State-Machines deaktivieren
- auf Bootloader/IAP springen
- einen MCU-Systemreset auslösen

Bis zur eigentlichen Flash-/Promotionphase läuft die normale Main-App weiter. Auf dem gemeinsam genutzten RS485-Bus entstehen lediglich zusätzliche OTA-Telegramme.

# Erreichbare destruktive Funktionen und Guards

| Funktion | vor C5A8 erreichbar? | Guard |
|---|---|---|
| EEPROM `0x3F0` setzen durch C357 | ja | gültige C357-Metadaten |
| EEPROM `0x3F0` löschen durch C36A | ja | C36A |
| Staging-Flash schreiben | **nein** | C5A8-Datenworker |
| Staging-Flash löschen via C36A | **nein** | `OTA+0x1C == 1`, erst nach letztem C5A8 gesetzt |
| Candidate-Slot löschen/kopieren | **nein** | spätere MD5-/Commit-State-Machines |
| Jump `0x08050000` | **nein** | spätere Slot-/Bootflags |
| Jump `0x08000000` | **nein** | persistenter später Transition-/Role-State |
| Systemreset | kein normaler OTA-Vorhandshakepfad gefunden | – |

# Risikobewertung

| Test | Firmware-Flash | EEPROM | Jump/Reset | Risiko |
|---|---|---|---|---|
| C350 identische V3.3-Kennung | nein | nein | nein | **sehr niedrig** |
| C350 inkompatibles Ziel | nein | nein | nein | **sehr niedrig** |
| C350 kompatibel, anderer Build | nein | nein | nein | **niedrig**; OTA-RAM-State bleibt aktiv |
| C357 ohne C5A8 | nein | **ja, `0x3F0`** | nein | **niedrig bis moderat**; persistent pending bis Cancel/Recovery |

# Empfohlener minimaler ser2net-Vortest

## Stufe 1 – bevorzugt

Nur C350 mit der **identischen aktuellen 12-Byte-Kennung**, die zuvor passiv aus dem Protokoll/C544 bestimmt wurde.

Erwartung:

```text
C36E Status 0
```

Dann **sofort stoppen**. Kein C357, kein C36A erforderlich, kein C37B.

Dieser Test bleibt nach statischer Analyse vollständig RAM-basiert.

## Stufe 2 – Status-1-Test

C350 mit gleicher 8-Byte-Zielkennung und bewusst abweichendem 4-Byte-Buildteil.

Erwartung:

```text
C36E Status 1
```

Danach optional C36A zum expliziten Verlassen des OTA-Handshakes.

Erwartung:

```text
C36C payload 00 63 00 01
```

Da noch nie C5A8 gesendet wurde, ist der C36A-Flash-Guard nicht gesetzt.

## Stufe 3 – C357 nur wenn ausdrücklich gewünscht

C357 erzeugt erstmals einen persistenten EEPROM-Zustand. Deshalb nur testen, wenn anschließend zwingend C36A gesendet und C36C empfangen wird.

Ablauf:

```text
C350 kompatibel/anderer Build
→ C36E 1
C357 gültige Länge+MD5
→ C36E 2
KEIN C5A8
C36A
→ C36C
STOP
```

# Harte Stopbedingungen

Den Vortest sofort abbrechen und nichts Weiteres senden, falls:

- irgendein C5A8 auftaucht oder versehentlich vorbereitet wurde
- ein anderer C36E-Status als 0/1/2 erscheint
- C36C nach Cancel nicht erscheint
- das Gerät unerwartet rebootet
- reguläre Modbus-/Warmlink-Kommunikation aussetzt
- ein unbekanntes OTA-Kommando vom LTE-Modem eine weitere Phase startet
- die beobachtete 12-Byte-Kennung nicht exakt der zuvor passiv bestimmten Kennung entspricht

Für einen maximal konservativen ersten Test ist **C350 identisch → C36E 0 → STOP** die empfohlene Grenze.
