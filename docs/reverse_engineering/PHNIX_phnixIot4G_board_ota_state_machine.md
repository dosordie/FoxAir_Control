# PHNIX `phnixIot4G` – `board_ota_step` State-Machine

Stand: 2026-08-22

Grundlage: statische Analyse des bereitgestellten ARM-ELF `phnixIot4G`. Schwerpunkt ist die Board-OTA-Zustandsmaschine in `dtu_upgrade_pro()` (`0x1D5C0`) sowie alle direkten `set_board_ota_step()`-Aufrufer.

## 1. Globale Zustandsvariable

`set_board_ota_step()` (`0x1D34C`) und `get_board_ota_step()` (`0x1D38C`) greifen auf:

```text
ota_info @ 0x98A7C
board_ota_step = ota_info + 0x18
```

also Byteadresse:

```text
0x98A94
```

Der Dispatcher `dtu_upgrade_pro()` arbeitet nur produktiv, wenn:

```text
get_dtu_run_step() == 11
```

ansonsten wird die Funktion sofort verlassen.

## 2. Tatsächlich verwendete `board_ota_step`-Werte

Im analysierten Build werden die Werte

```text
1, 3, 5, 6, 7, 8, 9, 10, 12
```

aktiv geschrieben oder abgefragt.

Für `0`, `2`, `4`, `11` gibt es in `dtu_upgrade_pro()` keinen eigenen Zustandsblock. `0` ist praktisch Initial-/Ruhezustand; `2`, `4`, `11` sind im untersuchten Pfad keine eigenständigen produktiven Zustände.

## 3. Gesamtablauf

Vereinfachte Hauptsequenz:

```text
Cloud/Board trigger
    ↓
step 1   Anfrage/Erlaubnis bei Cloud
    ↓
step 3   Firmwaredownload + MD5-Prüfung
    ↓
step 6   Firmwareblöcke via RS485 senden
    ↓
step 12  wartet auf Board-Ergebnis / Abschlusszustand
    ↓
step 5   Erfolg an Cloud melden
oder
step 10  Fehler an Cloud melden

Sonderpfade:
step 7   Cancel-/Abbruch-/Recovery-Pfad
step 8   Rollback-Anforderung/-Antwort
step 9   Rollback-Ergebnis an Cloud melden
```

## 4. `step 1` – Cloud-Erlaubnis / Upgrade-Anfrage

Block in `dtu_upgrade_pro()`:

```text
0x1D750 ... 0x1D81C
```

Ablauf:

```c
if (board_ota_step == 1) {
    if (board_request_upgrade() != 0)
        return;

    if (ota_info[0] == 0 && otaDeviceInfo.fileSize != 0) {
        board_ota_step = 3;
        ota_info[0] = 2;
        ota_info[0x16] = 1;
        ota_info[0x15] = 0;
        ota_info[0x10] = 0;
        other_ota_flags[5] = 0;
        other_ota_flags[4] = 0;
    }
}
```

`board_request_upgrade()` (`0x1D4E4`) ruft:

```text
ota_device_send_is_can_ota_to_phnix(otaDeviceInfo + 0x251)
```

auf.

Semantik: PHNIX-Cloud wird gefragt, ob das Board-Upgrade erlaubt ist. Bei erfolgreichem Publish und vorhandenem `fileSize` geht die State-Machine auf `step 3`.

## 5. `step 3` – Download der Board-Firmware

Block:

```text
0x1D820 ... 0x1D9D4
```

### 5.1 Sonderfall Flag `other_ota +0x68 == 1`

Bei:

```text
other_ota[0x68] == 1
```

wird sofort:

```text
board_ota_step = 7
other_ota[0x68] = 0
```

und der Durchlauf beendet.

### 5.2 Normaler Download

Ansonsten:

```text
0x1D860 -> board_ota_http_download()
```

`board_ota_http_download()`:

```text
ota_download_device_otaFile()
  -> Download nach /cache/phnixIot_device_OTA

wenn Download erfolgreich:
    ota_check_device_otaFile_md5()

wenn Download fehlschlägt:
    ota_device_send_ota_FirmwareDownloadFailed()
    return -1
```

Bei komplett erfolgreichem Download/MD5:

```text
sys_set_board_file_offset(0)
sys_set_board_file_md5(...)
sys_set_board_file_len(otaDeviceInfo.fileSize)
sys_set_dev_otavercode(...)
board_ota_step = 6
ota_info[0] = 0
other_ota[0x4C] = 3
```

Damit ist `step 3 -> step 6` der reguläre Übergang von Download zu RS485-Transfer.

### 5.3 Downloadfehler / Retry

Bei Fehler wird `ota_info+0x15` inkrementiert.

Solange:

```text
retry <= 2
```

bleibt der Zustand in `step 3` und ein späterer Durchlauf versucht erneut.

Nach mehr als zwei Fehlversuchen:

```text
ota_info+0x16 = 0
ota_info+0x15 = 0
ota_info+0x10 = 0
ota_info[0] = 0
board_ota_step = 10
```

Damit wird nach drei fehlgeschlagenen Downloadversuchen in den Fehlerreport-Zustand gewechselt.

## 6. `step 6` – Board-Firmware via RS485 senden

Block:

```text
0x1D9D8 ... 0x1DA04
```

Ablauf:

```c
if (board_ota_step == 6) {
    if (set_update_board_bin_by_485() == 0)
        board_ota_step = 12;
    else
        return;
}
```

`set_update_board_bin_by_485()` (`0x1CE14`) ist damit der zentrale Übergang in den eigentlichen Firmwareblock-Transfer.

Die darunterliegende Routine `set_board_update_bin()` baut die RS485-OTA-Frames, liest die Firmwaredatei, berechnet CRC und schickt über:

```text
uart485_send_data_to_board()
```

Firmwareblöcke Richtung Mainboard.

Nach erfolgreichem Senden eines Transferabschnitts geht der Zustand auf `12`.

## 7. `step 12` – Warte-/Abschlusszustand

`step 12` besitzt in `dtu_upgrade_pro()` keinen eigenen großen Block. Stattdessen wird er durch eingehende Boardantworten und Handler weitergeschaltet.

Der wichtigste Übergang liegt in `board_is_allow_upg_handle()`:

```text
wenn aktueller step == 12
    -> board_ota_step = 5
```

Das bedeutet: `12` ist der Zustand nach Datenübertragung, während auf das Board-Ergebnis / die Bestätigung des Upgradeabschlusses gewartet wird.

## 8. `step 5` – Erfolg an Cloud melden

Block:

```text
0x1DA08 ... 0x1DA40
```

Ablauf:

```text
board_ota_rep()
  -> ota_device_send_ota_finish()
```

Bei erfolgreichem MQTT-Publish:

```text
board_ota_step = 12
```

Damit wird der Abschlussbericht einmal gesendet und danach wieder in den neutralen Abschluss-/Wartezustand gewechselt.

## 9. `step 10` – Upgradefehler an Cloud melden

Block:

```text
0x1D70C ... 0x1D74C
```

Ablauf:

```text
sys_set_board_file_offset(0)
board_upgrade_fail_rep()
  -> ota_device_send_ota_Failed()
```

Bei erfolgreichem Publish:

```text
board_ota_step = 12
```

`step 10` ist damit eindeutig der Fehlerreport-Zustand.

Dieser Zustand wird u. a. gesetzt:

- nach >2 fehlgeschlagenen HTTP-/MD5-Downloadversuchen,
- aus `board_is_allow_upg_handle()` bei bestimmten Boardfehlerantworten,
- aus dem Cancel-/Recovery-Pfad.

## 10. `step 7` – Cancel-/Abbruch-/Recovery-Pfad

Block:

```text
0x1DA44 ... 0x1DB98
```

Der Zustand wird gesetzt aus mehreren Quellen:

- `down_board_cancel_ota_handle()`
- `board_recv_cancel_upgrade_handle()`
- `board_is_allow_upg_handle()`
- Download-/Recovery-Sonderflag in `dtu_upgrade_pro()`

Im Hauptblock werden mehrere globale Cancel-/Retryflags ausgewertet.

### Cancel-Antwort aktiv

Wenn:

```text
other_ota[2] == 1
other_ota[0x54] == 0
```

und ein Retrycounter `other_ota[0x58]` noch >0 ist:

```text
counter--
other_ota[0x54] = 3
reply_cancel_upgrade(1)
```

Wenn der Counter 0 erreicht:

```text
other_ota[2] = 0
other_ota[0x58] = 0
other_ota[1] = 0
```

### Kein aktiver Cancel mehr

Wenn weder Cancelrequest noch Pending-Flag gesetzt ist:

```text
ota_info[0] = 0
ota_info+0x16 = 0
other_ota[5] = 0
other_ota[4] = 0
board_ota_step = 12
board_ota_step = 10
```

Die unmittelbare Doppelzuweisung bedeutet effektiv:

```text
finaler Zustand = 10
```

also Übergang zum Fehlerreport.

## 11. `step 8` – Rollback/Version-Backroll

Block:

```text
0x1DB9C ... 0x1DC5C
```

Dieser Zustand wird u. a. von `board_reply_verbackroll_handle()` gesetzt.

Der Block wertet `other_ota[3]`, `other_ota[0x50]` und `other_ota[6]` aus.

### Rollback-Kommandos

Je nach internem Resultcode wird:

```text
dtu_to_board(1)
```

oder

```text
dtu_to_board(2)
```

oder

```text
dtu_to_board(3)
```

aufgerufen.

Für Resultcode `2` oder `3` folgt:

```text
board_ota_step = 9
```

Damit ist `step 8` der aktive Rollback-/Version-Backroll-Steuerzustand.

## 12. `step 9` – Rollback-Ergebnis an Cloud melden

Block:

```text
0x1DC60 ... 0x1DC98
```

Ablauf:

```text
board_verbackroll_result_repo()
  -> ota_device_send_Initialization()
```

Bei erfolgreichem Publish:

```text
board_ota_step = 12
```

`step 9` ist daher eindeutig der Report-Zustand für das Rollback-/Initialisierungsergebnis.

## 13. Externe Zustandsübergänge aus RS485-Handlern

Die Boardantworten treiben die State-Machine wesentlich mit.

### `board_recv_cancel_upgrade_handle()`

Wenn ein Cancel-Reply vom Board erfolgreich erkannt wurde:

```text
board_ota_step = 7
```

### `board_reply_verbackroll_handle()`

Nach Empfang einer Rollback-Antwort:

```text
board_ota_step = 8
```

Der Board-Resultcode wird zusätzlich in einem globalen Byte gespeichert.

### `board_is_allow_upg_handle()`

Diese Funktion ist der wichtigste RS485-seitige Zustandsumschalter und kann setzen:

```text
step 10  -> Fehler
step 6   -> Datenübertragung
step 1   -> Cloud-Erlaubnis erneut/anforderbar
step 7   -> Cancel/Recovery
step 5   -> Erfolg melden (wenn vorher step 12)
```

Damit ist der Pfad nicht rein linear; Mainboard-Antworten können den Transfer wiederholen, abbrechen oder in Success/Error-Reporting überführen.

## 14. State-Tabelle

| Step | Bedeutung | Hauptaktion | Typischer Folgezustand |
|---:|---|---|---:|
| 0 | Idle / uninitialisiert | keine eigene Aktion | 1/3/... durch externen Trigger |
| 1 | Upgrade-Erlaubnis anfragen | `ota_device_send_is_can_ota_to_phnix()` | 3 |
| 3 | Firmware herunterladen + MD5 | `board_ota_http_download()` | 6 oder 10 |
| 5 | Upgrade-Erfolg melden | `ota_device_send_ota_finish()` | 12 |
| 6 | Firmware an Board übertragen | `set_update_board_bin_by_485()` | 12 |
| 7 | Cancel/Recovery | `reply_cancel_upgrade()` / Cleanup | 10 bzw. extern |
| 8 | Rollback/Backroll-Steuerung | `dtu_to_board(1/2/3)` | 9 |
| 9 | Rollback-Ergebnis melden | `ota_device_send_Initialization()` | 12 |
| 10 | Upgradefehler melden | `ota_device_send_ota_Failed()` | 12 |
| 12 | Wait/Done / auf Board-Ergebnis warten | keine direkte Hauptaktion | 5/8/... via RS485-Handler |

## 15. Wichtige Kontrollfluss-Adressen

```text
board_ota_step storage         0x98A94
set_board_ota_step()           0x1D34C
get_board_ota_step()           0x1D38C
dtu_upgrade_pro()              0x1D5C0

step 10 block                  0x1D70C
step 1 block                   0x1D750
step 3 block                   0x1D820
HTTP download call             0x1D860
step 3 -> 6                    0x1D8FC
step 6 block                   0x1D9D8
RS485 firmware-send call       0x1D9E8
step 6 -> 12                   0x1D9F8
step 5 block                   0x1DA08
step 7 block                   0x1DA44
step 8 block                   0x1DB9C
step 9 block                   0x1DC60
```

## 16. Wichtigste Schlussfolgerungen

1. `0033` allein startet nicht sofort RS485-Firmwareverkehr. Die Metadaten landen zunächst in `otaDeviceInfo`; der eigentliche Transfer wird erst über die State-Machine erreicht.
2. Der erste Datei-/Netzwerkaktive Zustand ist `step 3` (`board_ota_http_download()` bei `0x1D860`).
3. Der erste eigentliche Firmware-RS485-Transfer beginnt in `step 6` beim Call `set_update_board_bin_by_485()` bei `0x1D9E8`.
4. `step 12` ist kein klassischer Idle-State, sondern ein Abschluss-/Wartezustand, der durch eingehende Mainboardantworten weitergeschaltet wird.
5. Die State-Machine ist bidirektional: Cloud-OTA-Kommandos und RS485-Boardantworten verändern gemeinsam den Ablauf.
6. Downloadfehler werden bis zu drei Mal versucht; danach folgt `step 10` und ein Cloud-Fehlerreport.
