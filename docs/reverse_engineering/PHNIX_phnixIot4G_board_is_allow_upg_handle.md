# PHNIX `phnixIot4G` – `board_is_allow_upg_handle()` vollständig zerlegt

Stand: 2026-08-22

Grundlage: statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`.

## Funktion

```text
board_is_allow_upg_handle @ 0x1BA04
```

Die Funktion verarbeitet die Mainboard-Antwort auf den OTA-„allow/upgrade status“-Pfad und steuert abhängig vom gemeldeten Status die weitere `board_ota_step`-State-Machine.

Wichtige Globals:

```text
otaDeviceInfo @ 0x933AC, 596 Byte
app           @ 0x988FC, 112 Byte
ota_info      @ 0x98A7C, 28 Byte
sys_para      @ 0x98820, 220 Byte
```

## 1. Eingangsargumente

Rekonstruierte Signatur:

```c
void board_is_allow_upg_handle(uint8_t *buf, uint16_t len_or_count)
```

Direkt am Anfang:

```text
0x1BA24..0x1BA38:
    otaDeviceInfo[0x251] = buf[3]

wenn arg1 != 0:
0x1BA48..0x1BA5C:
    otaDeviceInfo[0x252] = buf[1]
```

`otaDeviceInfo+0x252` ist derselbe Byteplatz, der im 0033-JSON-Pfad aus `ssid` befüllt wird und von `dtu_reply_recv_status()` als SSID verwendet wird.

`otaDeviceInfo+0x251` ist der eigentliche vom Mainboard gemeldete OTA-/Allow-Status.

Ein weiteres Byte:

```text
otaDeviceInfo+0x253
```

wird als vorheriger Status verwendet. Vor jeder eigentlichen Statusbehandlung:

```c
otaDeviceInfo[0x253] = otaDeviceInfo[0x251];
```

Der Debugstring bei VA `0x84654` lautet:

```text
otaDeviceInfo.is_allow_oat:%d,otaDeviceInfo.oat_sta:%d,ota_info.board.ota_step:%d
```

Damit ist die semantische Zuordnung sehr wahrscheinlich:

```text
+0x251 = is_allow_ota / aktueller Board-OTA-Status
+0x252 = ssid
+0x253 = ota_sta / gespeicherter letzter Status
```

## 2. Hauptdispatch nach `otaDeviceInfo+0x251`

Die Funktion behandelt die Werte 0..6. Andere Werte fallen ohne weitere Aktion zum Funktionsende durch.

### Status 0 oder 1

Codepfad ab `0x1BA84`.

Status 0 und 1 laufen zunächst in denselben Block.

```text
old = otaDeviceInfo[0x253]
cur = otaDeviceInfo[0x251]
step = get_board_ota_step()
DebugTrace(old, cur, step)
otaDeviceInfo[0x253] = cur
```

#### Status 1

Zusätzliche Bedingung:

```c
if (get_board_ota_step() == 12 || app[1] == 1) {
    ...
}
```

Adresse:

```text
0x1BB0C get_board_ota_step()
0x1BB14 compare 12
0x1BB1C load app+1
```

Wenn weder `board_ota_step == 12` noch `app+1 == 1`, wird der Status ohne Zustandswechsel ignoriert.

Wenn die Bedingung erfüllt ist und `len_or_count == 6`, werden `buf[4:5]` als Big-Endian-16-Bit-Wert interpretiert:

```c
uint16_t v = (buf[4] << 8) | buf[5];
if ((int16_t)v > 0)
    app[0x64] = v;
```

`app+0x64` ist der bereits bekannte OTA-Block-/Payload-Längenwert, standardmäßig 168 Byte.

Danach:

```text
0x1BBD4:
    app+0x44 = 3
```

Der chinesische Debugstring bei `0x846C4` bedeutet sinngemäß:

```text
„Mainboard hat neue Firmwareinformation vom Server erhalten und erlaubt Upgrade“
```

Damit ist Status 1 sehr klar der **Mainboard-„Upgrade erlaubt“-Status**.

#### Status 0

Status 0 durchläuft denselben Vorblock, besitzt aber keinen eigenen `set_board_ota_step()`-Aufruf. Er aktualisiert lediglich den gespeicherten Status und fällt anschließend aus der Funktion.

## 3. Status 2

Pfad ab `0x1BC28`.

```c
if (otaDeviceInfo[0x251] == 2) {
    if (app[1] == 1) {
        set_board_ota_step(6);
        app[0x4C] = 3;
        app[0x48] = 30;
        ota_info[0x16] = 1;
        app[1] = 0;
    } else {
        set_board_ota_step(1);
    }
}
```

Exakte Adressen:

```text
0x1BC50 set_board_ota_step(6)
0x1BC60 app+0x4C = 3
0x1BC70 app+0x48 = 30
0x1BC80 ota_info+0x16 = 1
0x1BC90 app+1 = 0

Alternativ:
0x1BC9C set_board_ota_step(1)
```

Interpretation:

- Wenn `app+1 == 1`, geht der Ablauf direkt in Transfer-State 6.
- Sonst wird auf State 1 zurückgesetzt und der Allow-/Handshake erneut angestoßen.

## 4. Status 3

Pfad `0x1BCA8..0x1BD00`.

```c
app[0] = 4;
app[1] = 0;
dtu_reply_recv_status(3);
```

Exakte Adressen:

```text
0x1BCBC app+0 = 4
0x1BCCC app+1 = 0
0x1BCDC dtu_reply_recv_status(3)
```

Danach nur Debug und Return.

Dieser Status erzeugt also unmittelbar ein lokales RS485-Statusreply über Register `0xC37B`.

## 5. Status 4

Pfad `0x1BD04..0x1BDFC`.

Zuerst:

```text
0x1BD18 dtu_reply_recv_status(4)
```

Dann wird `sys_para+0xD4` geprüft. Ist dieser Wert ungleich 0, wird ein Retryzähler `app+5` inkrementiert.

```c
if (sys_para[0xD4/4] != 0) {
    app[5]++;
    if (app[5] > 1) {
        app[1] = 0;
        sys_set_board_file_len(0);
    } else {
        app[1] = 1;
    }
}
```

Danach unabhängig davon:

```c
sys_set_board_file_offset(0);
set_board_ota_step(7);
app[2] = 1;
app[0x58] = 5;
app[0x54] = 5;
```

Adressen:

```text
0x1BDA0 sys_set_board_file_offset(0)
0x1BDA8 set_board_ota_step(7)
0x1BDB8 app+2 = 1
0x1BDC8 app+0x58 = 5
0x1BDD8 app+0x54 = 5
```

Der zugehörige String bei `0x8471C` lautet sinngemäß:

```text
„Firmware-Push ist zweimal fehlgeschlagen; diese Upgrade-Runde wird nicht weitergeführt“
```

Damit ist Status 4 eindeutig ein **Firmware-/Daten-Push-Fehlerpfad mit maximal zwei Versuchen**.

## 6. Status 5

Pfad `0x1BE00..0x1BE80`.

```c
dtu_reply_recv_status(5);
sys_set_board_file_offset(0);
sys_set_board_file_len(0);
app[1] = 0;

if (get_board_ota_step() == 12)
    set_board_ota_step(5);

ota_info[0x16] = 0;
```

Adressen:

```text
0x1BE30 dtu_reply_recv_status(5)
0x1BE38 sys_set_board_file_offset(0)
0x1BE40 sys_set_board_file_len(0)
0x1BE50 app+1 = 0
0x1BE58 get_board_ota_step()
0x1BE68 set_board_ota_step(5)   // nur falls vorher 12
0x1BE70 ota_info+0x16 = 0
```

Der String bei `0x84778` bedeutet:

```text
„Mainboard-Upgrade erfolgreich“
```

Damit ist Status 5 **Upgrade erfolgreich**.

Besonders wichtig:

```text
Board meldet Status 5
+ aktueller board_ota_step == 12
        ↓
set_board_ota_step(5)
        ↓
dtu_upgrade_pro() meldet Erfolg zur Cloud
```

## 7. Status 6

Pfad `0x1BE84..0x1BFA8`.

Zuerst:

```text
0x1BE98 dtu_reply_recv_status(6)
```

Wenn `sys_para+0xD4 != 0`, wird Retryzähler `app+4` inkrementiert.

```c
if (sys_para[0xD4/4] != 0) {
    app[4]++;
    if (app[4] > 1) {
        ota_info[0x16] = 0;
        sys_set_board_file_len(0);
        app[1] = 0;
    } else {
        app[1] = 1;
    }
}
```

Danach immer:

```c
sys_set_board_file_offset(0);
app[2] = 1;
app[0x58] = 5;
set_board_ota_step(7);
app[0x54] = 5;
```

Exakte Adressen:

```text
0x1BF30 sys_set_board_file_offset(0)
0x1BF40 app+2 = 1
0x1BF50 app+0x58 = 5
0x1BF58 set_board_ota_step(7)
0x1BF68 app+0x54 = 5
```

String bei `0x847D0`:

```text
„Mainboard-Upgrade fehlgeschlagen“
```

Status 6 ist damit **Upgrade fehlgeschlagen**, ebenfalls mit maximal zwei Versuchen.

## 8. Status-Tabelle

| Mainboard-Status (`otaDeviceInfo+0x251`) | Bedeutung | Hauptaktion |
|---:|---|---|
| 0 | neutral/kein Allow | Status speichern, keine direkte State-Änderung |
| 1 | Upgrade erlaubt | Blockgröße ggf. aus `buf[4:5]`; `app+0x44=3` |
| 2 | Transfer/Handshake-Fortsetzung | Step 6 wenn `app+1==1`, sonst Step 1 |
| 3 | Board-Status 3 | lokales `dtu_reply_recv_status(3)` |
| 4 | Firmware-/Daten-Push fehlgeschlagen | Retry; Step 7 / Recovery |
| 5 | Upgrade erfolgreich | Step 12 -> Step 5; OTA busy löschen |
| 6 | Upgrade fehlgeschlagen | Retry; Step 7 / Recovery |

## 9. `dtu_reply_recv_status()`

Funktion:

```text
dtu_reply_recv_status @ 0x1AD30
```

Sie baut ein Modbus-FC10-Telegramm zum Board auf.

Fest:

```text
slave = 0x63
fc    = 0x10
reg   = 0xC37B
ssid  = otaDeviceInfo+0x252
```

Der Funktionsparameter (3/4/5/6) wird als Statuswert in das Telegramm eingebaut. Damit bestätigt die DTU dem Board den empfangenen OTA-Status explizit zurück.

## 10. Relevante App-Felder

`app @ 0x988FC` ist ein 112-Byte-globaler Applikationszustand. Im OTA-Pfad werden mindestens diese Offsets verwendet:

| Offset | Nutzung in `board_is_allow_upg_handle()` | Interpretation |
|---:|---|---|
| `+0x00` | bei Status 3 auf 4 gesetzt | interner OTA-/TX-State |
| `+0x01` | Gate/Retry-Flag | zentraler „erneut senden / Transfer aktiv“-Marker |
| `+0x02` | bei Fehlerpfaden auf 1 | Recovery-/Retry-Trigger |
| `+0x04` | Fehlerzähler Status 6 | Upgrade-Fehler-Retrycount |
| `+0x05` | Fehlerzähler Status 4 | Push-Fehler-Retrycount |
| `+0x44` | bei Allow=1 auf 3 | OTA-Unterstate |
| `+0x48` | bei Status 2 auf 30 | Timer/Timeout |
| `+0x4C` | bei Status 2 auf 3 | Retry-/Statecounter |
| `+0x54` | Fehlerpfad auf 5 | Timer/Timeout |
| `+0x58` | Fehlerpfad auf 5 | Timer/Timeout |
| `+0x64` | Blockgröße | Default 168; Board kann bei Status 1 neuen Wert melden |

Die genaue Benennung einzelner Counter ist noch nicht über DWARF abgesichert, die Verwendung ist aber instruktionsseitig eindeutig.

## 11. Kritische Zustandsübergänge

### Allow

```text
Board Status 1
  + (board_ota_step == 12 oder app+1 == 1)
      ↓
optional Blockgröße aus buf[4:5]
      ↓
app+0x44 = 3
```

### Erfolg

```text
Board Status 5
  ↓
ACK Status 5 nach C37B
  ↓
file offset/length = 0
  ↓
falls Step 12: Step 5
  ↓
ota_info+0x16 = 0
```

### Fehler

```text
Board Status 4 oder 6
  ↓
ACK nach C37B
  ↓
Retrycounter erhöhen
  ↓
maximal zwei Versuche
  ↓
Step 7 / Recovery
```

## 12. Wichtige Korrektur zum bisherigen `otaDeviceInfo`-Layout

Die letzten Bytes der 596-Byte-Struktur sind nun genauer auflösbar:

```text
0x933AC + 0x251 = 0x935FD  aktueller is_allow_ota / Board-OTA-Status
0x933AC + 0x252 = 0x935FE  SSID
0x933AC + 0x253 = 0x935FF  gespeicherter ota_sta / letzter Status
```

Die frühere vereinfachte Darstellung, nach der `+0x253` nur ein unbenanntes Tail-Byte sei, ist damit überholt.

## 13. Kurzfazit

`board_is_allow_upg_handle()` ist die zentrale Mainboard-Rückmeldelogik der OTA-State-Machine. Der wichtigste semantische Befund ist:

```text
1 = Upgrade erlaubt
4 = Push/Transfer fehlgeschlagen
5 = Upgrade erfolgreich
6 = Upgrade fehlgeschlagen
```

Status 5 ist der Übergang von `board_ota_step=12` zu `board_ota_step=5` und damit der direkte Trigger für die spätere Erfolgsrückmeldung zur Cloud. Status 4/6 führen in Step 7 und besitzen getrennte Retryzähler mit effektiv maximal zwei Versuchen.
