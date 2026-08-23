# PHNIX `phnixIot4G` – Abschluss des Board-OTA nach letztem C5A8-Block

Stand: 2026-08-23

Diese Notiz rekonstruiert den statischen Abschluss des Board-OTA nach dem letzten Firmwareblock. Schwerpunkt ist der Pfad `board_ota_step 6 -> 12 -> 5 -> Cloud-Code 0053`.

## 1. Ende des C5A8-Transfers

In `dtu_upgrade_pro()`:

```text
0x1D9D8  get_board_ota_step()
0x1D9E0  compare == 6
0x1D9E8  set_update_board_bin_by_485()
0x1D9F0  compare return == 0
0x1D9F8  set_board_ota_step(12)
```

Damit gilt:

```c
if (board_ota_step == 6) {
    if (set_update_board_bin_by_485() == 0)
        set_board_ota_step(12);
}
```

`0` bedeutet hier: kein weiterer Datenblock mehr zu senden / Datei ist vollständig abgearbeitet. Der Übergang auf Step 12 erfolgt also im Worker und nicht direkt im C371-ACK-Handler.

Wichtig für dynamische Tests: Nach dem ACK des letzten Blocks noch mindestens einen weiteren Worker-Durchlauf zulassen, damit `set_update_board_bin_by_485()` den EOF-Zustand erkennt und Step 12 setzt.

## 2. Step 12 ist ein Wartezustand

Step 12 erzeugt in `dtu_upgrade_pro()` keinen eigenen Abschlussreport und setzt nicht automatisch Step 5. Der Worker läuft weiter und wartet auf ein eingehendes Board-Statusframe, das über `board_is_allow_upg_handle()` verarbeitet wird.

Aus Sicht des LTE-Prozesses wird der Cloud-Erfolgsabschluss durch Board-Status
**5** ausgelöst. Die inzwischen analysierte V3.3-Mainboard-Firmware unterscheidet
aber zwei Erfolgsstufen: Nach der Gesamtimage-MD5-Prüfung sendet sie zunächst
Status **3**. Status **5** folgt erst nach dem späteren Descriptor-, Copy-/Slot-
und Commit-/Handoff-Pfad. Status 5 bedeutet daher nicht lediglich „MD5 OK“.

## 3. Eingehendes C36E Status 5

`unpack_mcu_modbus()` reicht für Register C36E nur den Datenbereich an

```text
board_is_allow_upg_handle() @ 0x1BA04
```

weiter.

Der Handler liest:

```text
data[1]   -> SSID low byte
\data[3]   -> Board-OTA-Status
\data[4:5] -> optionale Blockgröße, nur bei len == 6
```

Für SSID `0x0063`, Status `5`, Blockgröße `168` ist ein synthetisch gültiges vollständiges FC10-Frame:

```text
63 10 C3 6E 00 03 06 00 63 00 05 00 A8 24 D9
```

CRC-Drahtfolge ist wie bei den anderen Modbusframes Low/High:

```text
24 D9
```

Die Bytes `data[0]` und `data[2]` werden im Handler nicht ausgewertet. Das obige Frame ist daher für den Emulator funktional ausreichend; ob das reale Mainboard dort exakt `00` sendet, ist aus dem LTE-Binary allein nicht beweisbar.

Das reale V3.3-Mainboard baut C36E mit zwei Registern beziehungsweise vier
Nutzbytes. Die hier gezeigte synthetische Variante mit drei Registern und sechs
Nutzbytes wurde nur verwendet, um dem LTE-Handler zusätzlich die optionale
Blockgröße 168 zu übergeben; sie ist handler-kompatibel, aber kein behaupteter
Live-Mitschnitt.

## 4. Exakter Status-5-Pfad im Handler

Relevante Instruktionen:

```text
0x1BE08  load otaDeviceInfo+0x251
0x1BE0C  compare status == 5
0x1BE30  r0 = 5
0x1BE34  BL dtu_reply_recv_status
0x1BE38  r0 = 0
0x1BE3C  BL sys_set_board_file_offset
0x1BE40  r0 = 0
0x1BE44  BL sys_set_board_file_len
0x1BE48  app+1 = 0
0x1BE58  get_board_ota_step()
0x1BE60  compare == 12
0x1BE68  r0 = 5
0x1BE6C  BL set_board_ota_step
0x1BE70  ota_info+0x16 = 0
```

Semantisch:

```c
if (board_status == 5) {
    dtu_reply_recv_status(5);
    sys_set_board_file_offset(0);
    sys_set_board_file_len(0);
    app[1] = 0;

    if (board_ota_step == 12)
        set_board_ota_step(5);

    ota_info[0x16] = 0;
}
```

Damit ist Status 5 eindeutig der Board-Erfolgsabschluss.

Status 3 wird vom LTE-Prozess ebenfalls mit C37B/status 3 quittiert, löst aber
noch nicht den Cloudabschluss `0053` aus. Für einen Mainboard-nahen Emulator
sollte deshalb die reale Reihenfolge nachgebildet werden: finaler C371 mit
`ackB=2`, C36E/status 3 nach erfolgreicher Gesamt-MD5-Prüfung und erst nach dem
späteren Commit-/Handoff-Pfad C36E/status 5.

## 5. DTU-Antwort auf Status 5: Register C37B

`dtu_reply_recv_status()` bei `0x1AD30` baut ein FC10-Frame an Register `C37B`.

Layout:

```text
63 10 C3 7B 00 02 04
SSID_HI SSID_LO
STATUS_HI STATUS_LO
CRC_LO CRC_HI
```

Für SSID `0x0063` und Status `5` ergibt sich vollständig:

```text
63 10 C3 7B 00 02 04 00 63 00 05 34 69
```

CRC:

```text
34 69
```

Damit sollte ein Emulator nach seinem C36E Status-5-Frame genau dieses DTU->Board-ACK sehen.

Zum Vergleich:

```text
Status 3: 63 10 C3 7B 00 02 04 00 63 00 03 B4 6B
Status 4: 63 10 C3 7B 00 02 04 00 63 00 04 F5 A9
Status 5: 63 10 C3 7B 00 02 04 00 63 00 05 34 69
Status 6: 63 10 C3 7B 00 02 04 00 63 00 06 74 68
```

## 6. Step 5 -> Cloud-Erfolgsreport

In `dtu_upgrade_pro()`:

```text
0x1DA08  get_board_ota_step()
0x1DA10  compare == 5
0x1DA18  BL board_ota_rep
0x1DA20  compare return == 0
0x1DA34  r0 = 12
0x1DA38  BL set_board_ota_step
```

`board_ota_rep()` ist nur ein Wrapper um:

```text
ota_device_send_ota_finish() @ 0x191C0
```

Der JSON-String im Binary lautet:

```json
{"cmd":"CMD_OTA","code":"0053","param":{"deviceCode":"<redigiert>","progress":"100","ssid":"0063"}}
```

Formatstring im Binary:

```text
{"cmd":"CMD_OTA","code":"0053","param":{"deviceCode":"%s","progress":"100","ssid":"%04x"}}
```

Gesendet wird über `ali_mqtt_push_OTA_msg()` auf dem Board-OTA-Topic `/<productKey>/<deviceName>/user/OTA_UPDATE`.

Wenn der Publish-Aufruf nicht negativ zurückkehrt, liefert `board_ota_rep()` Erfolg und der Worker setzt Step 12.

Endzustand:

```text
C36E status 5
 -> C37B ACK status 5
 -> board_ota_step 12 -> 5
 -> ota_info+0x16 = 0
 -> next worker iteration
 -> code 0053 / progress 100 to OTA_UPDATE
 -> board_ota_step 5 -> 12
```

## 7. Für den laufenden Work-Test

Empfohlene kontrollierte Abschlusssequenz:

```text
1. C5A8 block 1712 empfangen und bytegenau prüfen
2. C371 ACK-Art 2 für block 1712 senden; LTE-Endoffset muss 287598 werden
3. DTU mindestens einen weiteren Worker-Durchlauf geben
4. beobachten: board_ota_step 6 -> 12
5. C36E Status 3 senden und C37B Status-3-ACK beobachten
6. erst nach simuliertem Commit-/Handoff-Pfad C36E Status 5 senden
7. DTU muss C37B Status-5-ACK senden
8. beobachten: board_ota_step 12 -> 5
9. auf MQTT OTA_UPDATE muss Code 0053 / progress 100 erscheinen
10. danach board_ota_step 5 -> 12
```

Wichtig: C36E Status 5 **vor** Step 12 räumt zwar Offset und Dateilänge auf und quittiert Status 5, setzt aber wegen der expliziten `if (board_ota_step == 12)`-Bedingung nicht Step 5. Für einen sauberen Emulatorlauf sollte Status 5 daher erst nach beobachtetem Transferende / Step 12 kommen.

## 8. Sinnvolle Breakpoints

```gdb
b *0x1D9E8   # set_update_board_bin_by_485()
b *0x1D9F8   # unmittelbar vor Step 6 -> 12
b *0x1BE30   # Status-5-Pfad erkannt, vor C37B-ACK
b *0x1BE6C   # unmittelbar vor Step 12 -> 5
b *0x1DA18   # vor Cloud-Erfolgsreport
b *0x19250   # unmittelbar vor ali_mqtt_push_OTA_msg() für 0053
```

## 9. Evidenzgrad

**Hoch / statisch direkt bewiesen:**

- Step 6 -> 12 bei Return 0 von `set_update_board_bin_by_485()`
- Status 5 ruft `dtu_reply_recv_status(5)` auf
- Status 5 löscht persistent Offset und Dateilänge
- nur bei aktuellem Step 12 wird Step 5 gesetzt
- Step 5 publiziert OTA-Code 0053 / progress 100
- danach Rückkehr auf Step 12
- C37B-Frameaufbau und CRC
- V3.3-Mainboardpfad: Status 3 nach Gesamt-MD5, Status 5 erst nach späterem Commit-/Handoff-Pfad

**Synthetisch, aber handler-kompatibel:**

- C36E-Status-5-Frame mit `data[0]=0`, `data[2]=0` und Blockgröße 168. Diese beiden reservierten Bytes sind im Handler nicht semantisch geprüft.
