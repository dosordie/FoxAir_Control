# PHNIX `phnixIot4G` – `down_board_ota_url_handle()` / 0033 Safety-Breakpoint

Stand: 2026-08-22

Ziel dieser Notiz: den eingehenden `OTA_GET`-Code `0033` so weit laufen zu lassen, dass JSON vollständig ausgewertet und `otaDeviceInfo` im RAM befüllt ist, aber sicher **vor** Persistenz, Dateilöschung, HTTP-Download und dem Übergang in die Board-OTA-State-Machine zu stoppen.

## 1. Adresskorrektur

Der angefragte Handler liegt in diesem ELF nicht bei `0x19474`, sondern bei:

```text
0x19688  down_board_ota_url_handle
```

`0x19474` liegt innerhalb von `ota_dtu_send_ota_Failed()`.

## 2. `down_board_ota_url_handle()` vollständig

Pseudocode:

```c
void down_board_ota_url_handle(const char *json)
{
    // ota_info @ 0x98A7C
    if (ota_info[0x16] == 1 || ota_info[0x0A] != 0) {
        DebugTrace("upgrade in progress <%d>\r\n", ota_info[0]);
        ota_info[0] = 0;
        return;
    }

    ota_device_set_ota_file_download_info(json);
}
```

Instruktionsrelevante Adressen:

```text
0x19698  load ota_info base 0x98A7C
0x196A0  LDRB ota_info+0x16
0x196A4  CMP  #1
0x196A8  BEQ  reject

0x196AC  load ota_info base
0x196B4  LDRB ota_info+0x0A
0x196B8  CMP  #0
0x196BC  BEQ  accept

0x196C0..0x196D8  reject/debug path
0x196DC..0x196E8  ota_info[0] = 0

0x196F0  load JSON argument
0x196F4  BL ota_device_set_ota_file_download_info @ 0x18DB8
0x196FC  return
```

Damit sind **alle Bedingungen vor** `ota_device_set_ota_file_download_info()` exakt:

```text
ota_info+0x16 != 1
AND
ota_info+0x0A == 0
```

Es findet hier **keine Versionsprüfung** statt.

## 3. Bedeutung von „OTA erlaubt“

Die Bedingung im 0033-Handler ist keine einzelne `isAllowed`-Variable, sondern eine Sperrlogik über `ota_info @ 0x98A7C`.

### `ota_info+0x16`

Dieses Byte ist ein Board-OTA-Aktiv-/Freigabe-/Handshake-Status.

Beobachtete Werte und Schreiber:

```text
0x19080  set = 2   direkt nach Annahme eines 0033-Metadatensatzes
0x1BC84  set = 1   in board_is_allow_upg_handle() nach positiver Board-Freigabe
0x1D7C8  set = 1   beim Übergang in aktiven Upgradepfad

0x1B5F4  clear = 0 bei Cancel-Rückmeldung
0x1BBFC  clear = 0 in Ablehnungs-/Fehlerpfad
0x1BE7C  clear = 0 nach Abschluss/Statusübergang
0x1BEF4  clear = 0 bei Fehler/Retry-Abbruch
0x1D994  clear = 0 bei Download-/State-Fehler
0x1DB58  clear = 0 bei Cancel/Abbruch
```

Für `down_board_ota_url_handle()` gilt nur: **Wert 1 blockiert einen neuen 0033-Downloadauftrag.** Wert 2 blockiert dort nicht über diese Bedingung.

### `ota_info+0x0A`

Dieses Byte wird in `down_board_ota_url_handle()` und `dev_otavercode_compare()` als Sperrbedingung gelesen.

Im untersuchten Applikationscode wurde kein isolierter direkter `strb`-Schreiber auf genau `ota_info+0x0A` gefunden. Der Wert kommt daher sehr wahrscheinlich aus einer ganzstrukturellen Initialisierung/Persistenzwiederherstellung von `ota_info` bzw. aus Code, der die Struktur als Block behandelt. Sicher beweisbar ist nur:

```text
ota_info+0x0A != 0  -> 0033 wird verworfen
```

Eine belastbare semantische Benennung dieses Bytes ist aus diesem Handler allein nicht möglich.

## 4. `ota_device_set_ota_file_download_info()` – Ablauf

Adresse:

```text
0x18DB8
```

Die Funktion parst JSON mit json-c und besitzt praktisch keine Feldvalidierung.

### 4.1 JSON-Hierarchie

```text
root = json_tokener_parse(json)
param = json_object_object_get(root, "param")
```

Danach werden aus `param` in dieser Reihenfolge gelesen:

```text
softwareCode
softwareVer
ssid
fileMD5
fileSize
otaFileDownloadAddr
```

### 4.2 Reihenfolge der RAM-Schreibvorgänge

`otaDeviceInfo` liegt bei:

```text
0x933AC
size = 596 bytes
```

Rekonstruiertes Layout:

```c
struct otaDeviceInfo_t {
    char     softwareCodeCloud[9];   // +0x000 .. +0x008
    char     softwareVerCloud[7];    // +0x009 .. +0x00F
    uint32_t fileSize;               // +0x010 .. +0x013
    char     fileMD5[33];            // +0x014 .. +0x034
    char     otaFileDownloadAddr[541]; // +0x035 .. +0x251
    uint8_t  ssid;                   // +0x252
    uint8_t  tail/padding;           // +0x253
}; // 596 bytes
```

Begründende Adressen:

```text
0x933AC = base
0x933B5 = base+0x09  softwareVerCloud
0x933C0 = base+0x14  fileMD5
0x933E1 = base+0x35  otaFileDownloadAddr
0x935FE = base+0x252 ssid
```

### 4.3 `softwareCode`

```text
json_object_object_get(param,"softwareCode")
json_object_get_string()
strlen()
memcpy(0x933AC, string, strlen)
```

Es gibt keinen Bounds-Check gegen 9 Byte.

### 4.4 `softwareVer`

`softwareVer` wird als String gelesen und anschließend sowohl kopiert als auch positionsbasiert zerlegt.

Die Funktion liest unter anderem Zeichen an festen Indizes `+1`, `+2`, `+3`. Aus diesen Zeichen wird ein numerischer/kompakter Versionswert gebildet; zusätzlich werden Bytes in `softwareVerCloud` geschrieben.

Es gibt **keine Längenprüfung** vor diesen Indexzugriffen.

### 4.5 `ssid`

`ssid` wird per `json_object_get_string()` als String behandelt. Aus festen Zeichenpositionen wird ein Byte berechnet und nach:

```text
otaDeviceInfo+0x252
```

geschrieben.

### 4.6 `fileMD5`

```text
json_object_object_get(param,"fileMD5")
json_object_get_string()
strlen()
memcpy(0x933C0, string, strlen)
```

Keine Prüfung auf exakt 32 Hex-Zeichen; keine Hex-Syntaxprüfung an dieser Stelle.

### 4.7 `fileSize`

```text
json_object_object_get(param,"fileSize")
json_object_get_int()
otaDeviceInfo.fileSize = result
```

Speicheradresse:

```text
0x933BC = otaDeviceInfo+0x10
```

`fileSize == 0` wird hier nicht verworfen.

### 4.8 `otaFileDownloadAddr`

```text
json_object_object_get(param,"otaFileDownloadAddr")
json_object_get_string()
strlen()
memcpy(0x933E1, string, strlen)
```

Kein Leerstring-/Schema-/URL-Check im Parser.

### 4.9 Ende des JSON-Teils

```text
0x1905C  r0 = root
0x19060  BL json_object_put
```

**Bis einschließlich `0x19060` ist JSON vollständig ausgewertet und `otaDeviceInfo` komplett im RAM befüllt.**

## 5. Exakter Übergang nach dem Parsing

Unmittelbar danach:

```text
0x19064  load sys/state base 0x988FC
0x1906C  r2 = 3
0x19070  [0x988FC+0x3C] = 3
```

Das ist der **erste Übergang zur Board-OTA-State-Machine** in diesem Pfad.

Danach:

```text
0x19074..0x19080  ota_info+0x16 = 2
0x19084..0x1909C  Statistikzähler 0x91B60+0x24 ++
0x190A0..0x190AC  [0x988FC+0x00] = 0
0x190B0..0x190BC  [0x988FC+0x01] = 0
0x190C0..0x190D8  ssid -> persistent/stat struct 0x91B60+0x7C
0x190DC             BL static_write_data
0x190E0..0x190E8    system("rm -f /cache/phnixIot_device_OTA ")
0x190EC..0x190F4    system("true > /data/phnixIot_device_OTA_INFO ")
return
```

Wichtig: **`ota_device_set_ota_file_download_info()` startet `board_ota_http_download()` nicht direkt.** Der Download wird später durch `dtu_upgrade_pro()` anhand der gesetzten State-Machine aktiviert.

## 6. Frühester Dateizugriff / Persistenz

### Erste dauerhafte Änderung überhaupt

```text
0x190DC  BL static_write_data
```

Dies ist die erste persistente Schreibfunktion nach dem JSON-Parsing.

### Erste Änderung an `/cache/phnixIot_device_OTA`

```text
0x190E8  BL system
```

mit String:

```text
rm -f /cache/phnixIot_device_OTA
```

### Danach

```text
0x190F4  BL system
```

mit:

```text
true > /data/phnixIot_device_OTA_INFO
```

## 7. Sicherster GDB-Breakpoint für einen synthetischen 0033-Test

Wenn JSON **vollständig ausgewertet** werden soll, aber garantiert noch kein State-Machine-Übergang, keine Persistenz, keine Dateiänderung, kein Download und kein RS485 ausgelöst werden soll, ist der beste Breakpoint:

```gdb
break *0x19064
```

Begründung:

```text
0x19060  json_object_put(root)   # Parsing fertig
0x19064  erster Befehl vor dem Setzen von board state = 3
```

Damit kann man am Halt bereits `otaDeviceInfo @ 0x933AC` vollständig inspizieren.

Beispiel:

```gdb
x/596bx 0x933ac
x/s 0x933ac
x/s 0x933b5
x/wx 0x933bc
x/s 0x933c0
x/s 0x933e1
x/bx 0x935fe
```

Wenn ausschließlich vor Dateiänderung/Persistenz gestoppt werden soll, aber der RAM-State-Übergang noch erlaubt wäre, wäre `0x190DC` der späteste Breakpoint vor Persistenz. Für den formulierten Sicherheitszweck ist **0x19064 klar besser**.

## 8. Wann startet der HTTP-Download?

Der Handler startet keinen Download direkt.

`board_ota_http_download()` liegt bei:

```text
0x1D520
```

und ruft als erstes:

```text
0x1D528 -> ota_download_device_otaFile() @ 0x19E70
```

Der Aufruf erfolgt später aus `dtu_upgrade_pro()`:

```text
0x1D860 -> BL board_ota_http_download
```

Damit ist die erste direkte Downloadkante:

```text
dtu_upgrade_pro + 0x2A0
0x1D860
```

## 9. Versionen: gleich, älter, leer, ungültig

`down_board_ota_url_handle()` und `ota_device_set_ota_file_download_info()` führen **keinen Versionsvergleich** gegen die aktuell installierte Board-Version durch.

Daher gilt:

- gleiche `softwareVer`: wird hier **nicht** garantiert verworfen;
- ältere `softwareVer`: wird hier **nicht** garantiert verworfen;
- leere `softwareVer`: kein sauberer No-op; wegen fester Indexzugriffe potenziell undefiniertes Verhalten;
- syntaktisch ungewöhnliche `softwareVer`: wird positionsbasiert verarbeitet und kann unsinnige Werte erzeugen.

Ein späterer Versionsvergleich existiert separat in `dev_otavercode_compare()` (`0x1BFB0`), aber **nicht als Vorbedingung des 0033-Metadatenparsers**.

## 10. Fehlende/ungültige Felder

Der Parser macht praktisch keine Defensive Checks.

### Fehlendes `param`

`json_object_object_get(root,"param")` kann NULL liefern. Danach werden weitere json-c-Aufrufe mit diesem Wert gemacht. Es gibt keinen expliziten sauberen Fehlerpfad.

### Fehlendes Stringfeld

Bei `softwareCode`, `softwareVer`, `ssid`, `fileMD5`, `otaFileDownloadAddr` wird typischerweise:

```text
json_object_object_get(...)
json_object_get_string(...)
strlen(...)
```

verwendet.

Wenn daraus NULL entsteht, kann spätestens `strlen(NULL)` crashen. Ein garantierter nebenwirkungsfreier Return existiert nicht.

### `fileSize=0`

Wird gespeichert. Keine Ablehnung im Parser.

### leere URL

Wird als leere Zeichenkette akzeptiert; keine Ablehnung im Parser.

### ungültige MD5

Wird roh kopiert; keine Längen-/Hexprüfung im Parser. Die eigentliche MD5-Prüfung erfolgt erst nach dem späteren Download in `ota_check_device_otaFile_md5()`.

## 11. Metadaten-Persistenz

Ja: Metadaten werden **vor Download und vor MD5-Prüfung** persistent gemacht.

Reihenfolge:

```text
JSON parse
RAM otaDeviceInfo
board state = 3
ota_info+0x16 = 2
Statistik / ssid aktualisieren
static_write_data()        <-- Persistenz
rm -f cached firmware
truncate OTA_INFO file
(später) dtu_upgrade_pro()
(später) HTTP download
(später) Größen-/MD5-Prüfung
```

Damit werden Metadaten nicht erst nach erfolgreicher Firmwarevalidierung dauerhaft gespeichert.

## 12. Rückgabewerte / Fehlerpfade

Beide Funktionen sind semantisch `void`-Handler.

### `down_board_ota_url_handle()`

Pfade:

```text
blocked -> DebugTrace, ota_info[0]=0, return
accepted -> call ota_device_set_ota_file_download_info(), return
```

Es wird kein definierter Erfolgs-/Fehlercode an den Aufrufer zurückgegeben.

### `ota_device_set_ota_file_download_info()`

Explizit behandelter Fehler:

```text
json_tokener_parse() == NULL
 -> DebugTrace
 -> return
```

Danach fehlen systematische Feldprüfungen. Fehler in Einzelwerten werden nicht über Rückgabecodes propagiert.

Auch die Rückgabewerte von:

```text
static_write_data()
system("rm ...")
system("true > ...")
```

werden in diesem Handler nicht ausgewertet.

## 13. Sicherheitsrelevante Adressen für Work

```text
0x19688  down_board_ota_url_handle
0x196F4  call ota_device_set_ota_file_download_info

0x18DB8  ota_device_set_ota_file_download_info
0x19060  json_object_put(root) / Ende JSON-Auswertung
0x19064  BESTER SAFE BREAKPOINT
0x19070  erster Board-State-Write (=3)
0x19080  ota_info+0x16 = 2
0x190DC  erste Persistenz: static_write_data()
0x190E8  erste Änderung /cache/phnixIot_device_OTA
0x190F4  truncate/create /data/phnixIot_device_OTA_INFO

0x1D520  board_ota_http_download
0x1D528  call ota_download_device_otaFile
0x1D860  erster dtu_upgrade_pro-Aufruf von board_ota_http_download
```

### Empfohlener Test-Halt

```gdb
b *0x19064
```

Dieser Halt lässt den `0033`-JSON-Payload vollständig durch json-c und in `otaDeviceInfo` laufen, stoppt aber vor:

- Board-State-Machine-Änderung,
- Persistenz,
- `/cache`-Änderung,
- OTA_INFO-Dateiänderung,
- HTTP-Download,
- RS485-OTA-Transfer.
