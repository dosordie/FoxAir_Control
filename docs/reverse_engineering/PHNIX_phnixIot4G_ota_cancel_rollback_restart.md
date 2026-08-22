# PHNIX `phnixIot4G` – OTA Cancel, Rollback und Neustart-/Resume-Verhalten

Stand: 2026-08-23

Grundlage: statische ARM-Analyse des bereitgestellten `phnixIot4G`.

## 1. Cloud-Cancel (`0073`) -> Step 7

`down_board_cancel_ota_handle()` liegt bei `0x19764`.

Die Funktion setzt unmittelbar:

```text
app base                = 0x988FC
app+0x02                = 1      ; cancel pending
app+0x58                = 5      ; cancel retry budget
app+0x01                = 0
app+0x4C                = 0
app+0x68                = 1
app+0x6C                = 60
board_ota_step          = 7
```

Der Übergang zu Step 7 erfolgt bei:

```text
0x197D4  mov r0,#7
0x197D8  bl set_board_ota_step
```

Damit ist Step 7 der aktive Board-Cancel-/Recovery-Zustand.

## 2. Step 7 in `dtu_upgrade_pro()`

Der Step-7-Block beginnt bei `0x1DA44`.

Aktiver Cancel-Versand nur wenn:

```text
app+0x02 == 1
app+0x54 == 0          ; kein Cancel-Timer aktiv
```

Danach:

```text
if (app+0x58 != 0) {
    app+0x58--;
    app+0x54 = 3;
    reply_cancel_upgrade(1);
    return;
}
```

Die eigentliche Sendestelle ist:

```text
0x1DACC -> reply_cancel_upgrade(1)
```

Wenn das Retrybudget bereits 0 ist, wird der Cancel-Versuch beendet:

```text
app+0x02 = 0
app+0x58 = 0
app+0x01 = 0
```

und Step 7 bleibt bis zum weiteren Recoverypfad bestehen.

## 3. Cancel-RS485-Request

`reply_cancel_upgrade()` liegt bei `0x1AFA4`.

Er baut ein Modbus-FC10-Telegramm auf Register:

```text
0xC36A
```

mit:

```text
Slave      0x63
FC         0x10
Register   0xC36A
Quantity   0x0002
ByteCount  0x04
SSID       uint16 big-endian
Status     uint16 big-endian
CRC        vom lokalen crc16()
```

Für den aus Step 7 aufgerufenen Fall ist `Status = 1`.

Der SSID-Wert kommt aus `sys_get_board_ota_ssid()` und damit aus persistentem Systemparameter-Speicher.

## 4. Board-Cancel-Antwort (`C36C`)

`board_recv_cancel_upgrade_handle()` bei `0x1B51C` wird nur ausgewertet, solange:

```text
app+0x02 != 0
```

Der Handler erhält bereits nur den Datenbereich des Modbus-FC10-Pakets (`frame+7`).

Ausgewertet werden:

```text
buf[1] -> otaDeviceInfo+0x252 = SSID low byte/statusnahe Kennung
buf[3] -> otaDeviceInfo+0x251 = Board-Status
```

Nur wenn:

```text
otaDeviceInfo+0x251 == 1
```

wird der Cancel als bestätigt behandelt.

Dann:

```text
app+0x02 = 0
app+0x58 = 0
```

Anschließend gibt es zwei Pfade:

```text
if (app+0x01 != 0)
    app+0x3C = 3;
else {
    board_ota_step = 7;
    ota_info+0x16 = 0;
}
```

Das heißt: die C36C-Bestätigung beendet den aktiven Cancel-Request, führt aber nicht automatisch auf Idle/Step 12; sie übergibt an den Recoveryzustand.

## 5. Cloud-Rollback (`0103`) -> Step 8

`down_board_ver_bcakroll_handle()` liegt bei `0x197F4`.

Er macht nur:

```text
app+0x03 = 1
board_ota_step = 8
```

Der Step-8-Block beginnt bei `0x1DB9C`.

## 6. Rollback-Request vom DTU zum Board

Wenn:

```text
board_ota_step == 8
app+0x03 == 1
app+0x50 == 0
```

setzt der Code:

```text
app+0x50 = 3
```

und sendet:

```text
dtu_to_board(1)
```

Sendestelle:

```text
0x1DBF4 -> dtu_to_board(1)
```

`dtu_to_board()` liegt bei `0x1B214` und sendet Modbus-FC10 an Register:

```text
0xC375
```

Format:

```text
63 10 C3 75 00 02 04 SS SS 00 XX CRC...
```

`SS SS` = persistierte OTA-SSID.

Für den Initialrequest ist `XX = 01`.

## 7. Board-Rollback-Antwort (`C378`)

`board_reply_verbackroll_handle()` liegt bei `0x1B600`.

Der Handler wird nur verarbeitet, solange:

```text
app+0x03 != 0
```

Er liest aus dem übergebenen Datenpuffer:

```text
buf[1] -> otaDeviceInfo+0x252
buf[3] -> otaDeviceInfo+0x251
```

Danach:

```text
app+0x06 = otaDeviceInfo+0x251
app+0x03 = 0
board_ota_step = 8
```

Statusauswertung:

```text
app+0x06 == 1:
    app+0x03 = 2

app+0x06 == 2:
    ota_info+0x17 = 1

app+0x06 == 3:
    ota_info+0x17 = 0
```

Damit ist Status 1 ein weiterer Rollback-Handshake-Zustand; Status 2/3 setzen das eigentliche Rollback-Ergebnisflag.

## 8. Step 8 -> Step 9

Nach der C378-Verarbeitung schaut `dtu_upgrade_pro()` auf `app+0x06`.

Wenn:

```text
app+0x06 == 2
```

sendet der DTU nochmals:

```text
dtu_to_board(2)
```

und setzt:

```text
board_ota_step = 9
```

Adressen:

```text
0x1DC14 -> dtu_to_board(2)
0x1DC28 -> set_board_ota_step(9)
```

Wenn:

```text
app+0x06 == 3
```

sendet er entsprechend:

```text
dtu_to_board(3)
```

und setzt ebenfalls Step 9:

```text
0x1DC48 -> dtu_to_board(3)
0x1DC5C -> set_board_ota_step(9)
```

Damit ist Step 9 der Cloud-Report-Zustand nach abgeschlossenem Rollback-Handshake.

## 9. Step 9: Rollback-Ergebnis an Cloud

Bei:

```text
board_ota_step == 9
```

wird:

```text
board_verbackroll_result_repo()
```

aufgerufen.

Diese Funktion ruft:

```text
ota_device_send_Initialization()
```

auf.

Nach erfolgreichem Publish:

```text
board_ota_step = 12
```

Adressen:

```text
0x1DC70 -> board_verbackroll_result_repo()
0x1DC90 -> set_board_ota_step(12)
```

## 10. Neustart und Resume: was wirklich persistent ist

Wichtig: `board_ota_step` selbst liegt in:

```text
ota_info+0x18 @ 0x98A94
```

`set_board_ota_step()` schreibt nur dieses RAM-Byte. Die Funktion ruft **keine Persistenzfunktion** auf.

Damit ist der aktuelle Step 1/3/6/7/8/9/12 für sich genommen nicht dauerhaft gespeichert.

Persistent gespeichert werden dagegen separat:

```text
board file MD5       sys_para + 0xA5
board file offset    sys_para + 0xD4
board file length    sys_para + 0xD8
board OTA SSID       sys_para + 0x7C
OTA SoftwareCode/Ver separate sys_para-Felder
```

Die Setter rufen `sys_flash_erase_write()` auf, wenn sich der Wert geändert hat.

Besonders der Transferoffset ist damit rebootfest:

```text
sys_set_board_file_offset()
 -> sys_para+0xD4
 -> sys_flash_erase_write()
```

und beim Transfer wird er wieder über:

```text
sys_get_board_file_offset()
```

verwendet.

## 11. Was nach Neustart nicht automatisch wiederhergestellt wird

Statisch ist kein Codepfad gefunden, der beim Programmstart den vorherigen `board_ota_step` aus persistentem Speicher restauriert.

Das bedeutet:

```text
Transferfortschritt (Offset/Len/MD5/SSID) -> persistent
aktueller State-Machine-Step              -> RAM-only
```

Ein Neustart mitten in Step 6 verliert daher den unmittelbaren Step-6-Zustand, aber nicht den bestätigten Firmwareoffset.

Für echtes Resume muss der State-Machine-Handshake anschließend erneut in einen Transferzustand gebracht werden. Sobald `set_update_board_bin_by_485()` erneut läuft, benutzt es den persistierten Offset und setzt mit dem nächsten bestätigten Block fort.

Das ist ein wichtiges Architekturmerkmal: **Resume ist datei-/offsetbasiert, nicht durch Persistenz des State-Machine-Steps.**

## 12. Neustart während Download (Step 3)

Während des HTTP-Downloads existiert noch kein fortgeschriebener Transferoffset. Nach erfolgreichem Download wird explizit:

```text
sys_set_board_file_offset(0)
sys_set_board_file_md5(...)
sys_set_board_file_len(fileSize)
```

gesetzt, bevor Step 6 beginnt.

Ein Prozessabbruch **vor** erfolgreichem Ende von `board_ota_http_download()` hinterlässt daher keine sauber abgeschlossene Download->Transfer-Transition.

Da Step 3 selbst nicht persistent ist, startet der Prozess nicht automatisch wieder in `board_ota_http_download()`.

## 13. Neustart während C5A8-Transfer (Step 6)

Nach jedem bestätigten C371-ACK mit `ackB==1` wird der File-Offset persistent erhöht.

Daher gilt:

```text
Block N erfolgreich bestätigt
 -> Offset für Block N+1 persistent
 -> Crash/Restart
 -> State Step 6 verloren
 -> Offset bleibt erhalten
```

Wenn ein neuer OTA-/Resume-Handshake den Code wieder nach Step 6 bringt, wird mit:

```text
fseek(file, persisted_offset, SEEK_SET)
```

weitergemacht.

Ein Block, der gesendet, aber noch nicht bestätigt wurde, erhöht den persistenten Offset nicht und wird nach Resume erneut gesendet. Das ist die sichere Retry-Semantik.

## 14. Cancel vs. Resume

Cloud-Cancel setzt unter anderem:

```text
app+0x68 = 1
app+0x6C = 60
```

und Step 7.

Im Step-3-Pfad wird `app+0x68==1` ebenfalls geprüft und führt unmittelbar zu Step 7, bevor `board_ota_http_download()` aufgerufen wird.

Damit kann ein Cancel auch einen noch nicht gestarteten bzw. erneut anstehenden Download zuverlässig in den Recoverypfad umlenken.

Die persistenten File-Metadaten/Offsets werden durch `down_board_cancel_ota_handle()` selbst jedoch nicht sofort gelöscht.

## 15. Wesentliche Schlussfolgerung

Der OTA-Pfad besitzt zwei unterschiedliche Formen von Zustand:

```text
flüchtig:
  board_ota_step
  Retry-/Timerflags
  Cancel-/Rollbackflags

persistent:
  OTA SSID
  SoftwareCode/Version
  Datei-MD5
  Dateilänge
  bestätigter Datei-/Transferoffset
```

Dadurch ist ein robustes Transfer-Resume möglich, ohne den kompletten State-Machine-Step persistent zu speichern. Nach einem Neustart muss aber der Protokollzustand erneut aufgebaut werden.
