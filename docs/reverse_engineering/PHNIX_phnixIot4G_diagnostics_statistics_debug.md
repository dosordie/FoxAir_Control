# PHNIX `phnixIot4G` – Debug, Fehler, Statistik und Signal-Thread

Stand: 2026-08-23

Grundlage: weitere statische Analyse des ungestrippten ARM-ELF `phnixIot4G` (Build-ID `af4dcae12639bedce833ee5efa5da009777b6319`). Diese Datei vertieft die in `PHNIX_phnixIot4G_non_ota_architecture.md` identifizierten Nicht-OTA-Bereiche.

## 1. Debugschnittstelle `/dev/ttyGS0` ist real und aktiv initialisiert

`init_uart_debug()`:

```text
0x13C88
```

öffnet:

```text
/dev/ttyGS0
```

mit Flags `0x802` und ruft anschließend `set_opt()` mit:

```text
Baudrate 115200
Datenbits 8
Parity 'N'
Stopbits 1
```

also **115200 8N1**.

Der Debug-FD liegt global bei:

```text
0x920D8
```

`init_uart_debug()` wird beim regulären Programmstart aufgerufen (`main`-Startup-Pfad um `0xB440`).

### Debugausgabe

```text
Debugh()                  @ 0x13D70
DebugHex()                @ 0x13DA8
DebugTrace()              @ 0x13E20
DebugTrace_no_file_info() @ 0x13F34
```

`DebugTrace()` formatiert zunächst in einen lokalen Puffer, schreibt die Meldung auf die normale Prozessausgabe und zusätzlich mit `write()` auf den globalen `/dev/ttyGS0`-FD.

Das Präfix lautet:

```text
LOG_INFO---------- %s:%u %s:%s:\t
```

und der Build enthält:

```text
log.c
Nov 10 2022
17:26:01
```

**Praktischer Nutzen:** Wenn `/dev/ttyGS0` auf dem realen Modem erreichbar/gebunden ist, ist dies wahrscheinlich die wertvollste lokale Diagnosequelle, weil die Originalsoftware dort ihre internen Debugmeldungen live ausgibt.

Read-only Prüfung auf dem Modem:

```sh
ls -l /dev/ttyGS0
ps | grep '[p]hnixIot4G'
```

Wenn der Port auf USB nach außen geführt wird, kann passiv mit 115200 8N1 mitgelesen werden.

---

## 2. Wichtige Korrektur zu GPIO 50 / `Reset_All_DOG()`

`Reset_All_DOG()` selbst liegt bei:

```text
0xB400
```

und pulst GPIO 50:

```c
EAT_WriteGpio(50, 1);
sleep(2);
EAT_WriteGpio(50, 0);
```

Die OTA-State-Machine ruft diese Funktion nicht direkt auf. **Trotzdem wird GPIO 50 während eines langen Mainboard-OTA sehr wahrscheinlich weiter periodisch gepulst**, weil ein parallel laufender Signal-/LED-Thread aktiv bleibt.

### Indirekter Pfad

`led_thread_handle()`:

```text
0x17F8C
```

ruft in seiner Dauerschleife immer wieder:

```text
AT_GetCSQ() @ 0xC500
```

auf.

`AT_GetCSQ()` ruft in seiner Retryschleife unmittelbar:

```text
Reset_All_DOG() @ 0xB400
```

auf.

Damit gilt:

```text
led_thread_handle
 -> AT_GetCSQ
 -> Reset_All_DOG
 -> GPIO 50 High
 -> sleep(2)
 -> GPIO 50 Low
```

Der LED-Thread läuft parallel zum Board-OTA weiter.

**Folgerung:** Die frühere Aussage „GPIO 50 wird während eines zwölfminütigen C5A8-Transfers nicht bedient“ ist zu präzisieren: Der OTA-Thread bedient GPIO50 nicht, der unabhängig weiterlaufende Signalthread tut es aber indirekt über `AT_GetCSQ()`.

Die elektrische Bedeutung von GPIO50 bleibt ohne Schaltplan/RootFS-/Hardwarebeobachtung offen; für einen echten Transfer ist aber deutlich weniger wahrscheinlich, dass ein reiner „fehlender DOG-Feed während OTA“ nach einigen Minuten zum Reset führt.

---

## 3. Signal-LED-Schwellen

`led_thread_handle()` wertet den von `AT_GetCSQ()` gelieferten Wert aus.

Bestätigte Schwellwerte:

```text
CSQ 20..31  -> high LED an
CSQ 15..31  -> middle LED an
CSQ 1..31   -> weak LED an
CSQ <=0 oder >31 -> entsprechende Signal-LEDs aus
```

Zusätzlich wird bei gültigem CSQ `1..31` Error-Bit 4 gelöscht; bei ungültigem Wert wird Error-Bit 4 gesetzt.

Der Thread besitzt einen 16-Bit-Zähler und aktualisiert ungefähr alle 50 Schleifendurchläufe mehrere Signalstatistiken.

---

## 4. `statistic_para` – große Teile des 128-Byte-Formats jetzt benannt

Persistenz:

```text
/data/phnixIot_device_statisic
statistic_para @ 0x91B60
Größe 128 Byte
```

`Upload_bord_log()` baut aus den Feldern explizit benannte Statistikwerte. Dadurch lassen sich zahlreiche Offsets sicher zuordnen:

| Offset | Name im Herstellerlog | Bedeutung |
|---:|---|---|
| `0x00` | `Strongest Net csq` | stärkster beobachteter CSQ |
| `0x04` | `Weakest Net csq` | schwächster beobachteter CSQ |
| `0x08` | `Online time` | Online-Zeit |
| `0x0C` | `Device-change-t` | Device-Wechselzähler |
| `0x10` | `On-Off-line-t` | Online/Offline-Wechselzähler |
| `0x14` | `Work time` | Betriebszeit |
| `0x18` | `Up-D-t` | Upload-Zähler |
| `0x1C` | `Down-D-t` | Download-Zähler |
| `0x20` | `Ota-dtu-t` | DTU-OTA-Zähler |
| `0x24` | `Ota-dev-t` | Mainboard-/Device-OTA-Zähler |
| `0x28` | `Power-Reset-t` | Power-Reset-Zähler |
| `0x2C` | `Active-Reset-t` | aktiver/Software-Reset-Zähler |
| `0x38` | `Api-t` | API-Zähler |
| `0x3C` | `Average Net csq` | berechneter Durchschnitts-CSQ |
| `0x40` | `Day-Up-D-t` | Tages-Upload/Download-Zähler |
| `0x44` | `Current Work time` | aktuelle Betriebszeit |
| `0x48` | `Current Online time` | aktuelle Online-Zeit |
| `0x4C` | `Current Net csq` | letzter/aktueller CSQ |

Weitere Felder ab `0x50` werden für Logupload-/Tageswechsel-/Timingzustände verwendet und sind noch nicht alle semantisch benannt.

### Durchschnitts-CSQ

Der Signalthread akkumuliert:

```text
statistic_para+0x58 += current_csq
statistic_para+0x5C += 1
```

Vor dem Logupload wird daraus:

```text
Average Net csq = (+0x58) / (+0x5C)
```

berechnet und nach `+0x3C` geschrieben.

### Startverhalten

`static_read_data(1)` liest 128 Byte und setzt beim normalen Prozessstart mehrere „current/day/runtime“-Felder wieder auf 0, während Langzeitzähler und Min/Max-Werte erhalten bleiben.

**Praktischer Nutzen:** `/data/phnixIot_device_statisic` kann read-only dekodiert werden und liefert interne Langzeitdaten, die Warmlink nicht unbedingt anzeigt.

---

## 5. Automatischer Statistik-/Logupload

`TimerHandler()` läuft im Sekundentakt und verändert zahlreiche `statistic_para`-Felder.

Unter anderem:

```text
Work time (+0x14) wächst fortlaufend
Current Work time (+0x44) wächst fortlaufend
bei aktivem Aliyun-Link wachsen Online time (+0x08) und Current Online time (+0x48)
```

`Check_upload_log() @ 0x11748` berechnet einen Zeit-/Tagesindex und kann bei Wechseln folgende Felder setzen:

```text
+0x60
+0x64
+0x54
```

Danach ruft `TimerHandler()` abhängig von diesen Zuständen `Upload_bord_log()` auf.

Der Dienst besitzt also eine eigenständige periodische Hersteller-Telemetrie/Diagnosestatistik zusätzlich zum normalen Warmlink-Datenstrom.

---

## 6. Fehlerbitmap `ErrorStatue`

Global:

```text
ErrorStatue @ 0x93124  // 32 Bit Bitmap
ErrorTag    @ 0x9312B
```

Setzen/Löschen erfolgt bitweise:

```c
set_Error_Flag(n):   ErrorStatue |=  (1U << n)
Clear_Error_Flag(n): ErrorStatue &= ~(1U << n)
```

`Get_ErrorStatue()` liefert das komplette Bitmap.

### Auffälliger Bug in `Get_Error_Flag()`

`Get_Error_Flag(n) @ 0x178F0` verwendet im analysierten Build:

```c
(1U << n) | ErrorStatue
```

statt des erwarteten:

```c
(1U << n) & ErrorStatue
```

und prüft anschließend nur, ob das Ergebnis >0 ist.

Für normale Bitnummern ergibt die Funktion dadurch praktisch immer `1`.

Im bisher untersuchten Kontrollfluss wurde jedoch kein direkter Aufrufer dieser Funktion gefunden; der Bug scheint daher im aktuellen Build weitgehend toter/ungenutzter Altcode zu sein.

---

## 7. Hersteller-Fehlertexte

`Upload_bord_log()` baut Fehlerarrays anhand einer Bitmap auf. Sicher sichtbare Texte sind:

```text
bit 0 -> 485 connected error
bit 1 -> Address error
bit 3 -> No PK
bit 4 -> No Three-Element-mqtt
bit 5 -> Cloud connected error
bit 6 -> WF_double_error
bit 7 -> Crc error
```

Bit 2 wird in diesem konkreten Fehlerstring-Block übersprungen; andere höhere Error-Bits werden im Programm ebenfalls gesetzt und scheinen für interne LED-/Subsystemzustände benutzt zu werden.

Beispiele direkter Setter im Gesamtprogramm:

```text
Bit 4  -> ungültiger CSQ / Signalproblem
Bit 8  -> UART485-Initialisierungs-/Startproblem
Bit 10 -> Cloud-/Laufzeitpfade
```

Die vollständige Zuordnung aller 32 Bits bleibt noch offen, aber der Hersteller-Logblock 0..7 ist weitgehend rekonstruiert.

---

## 8. Fehler-LED codiert Fehlerbits als Blinkanzahl

`ChangeBlinkTime() @ 0x17960` scannt Error-Bits und setzt abhängig vom gesetzten Bit einen Blinkwert.

Für die unteren Fehlerindizes werden u. a. folgende Werte gewählt:

```text
Error 1 -> BlinkTime 2
Error 2 -> BlinkTime 4
Error 3 -> BlinkTime 6
Error 4 -> BlinkTime 8
Error 5 -> BlinkTime 10
Error 6 -> BlinkTime 10
Error 8 -> BlinkTime 12
Error 9 -> BlinkTime 14
Error 10 -> BlinkTime 16
```

`ChangeErrorLedStatue()` zählt anschließend Blink-/Pause-Zustände herunter und schaltet GPIO 76.

Damit ist die Fehler-LED keine einfache An/Aus-Anzeige, sondern kodiert den aktiven Fehlerzustand über Blinkfolgen.

---

## 9. GPIOs der LEDs

Aus dem LED-Pfad ist mindestens GPIO 76 eindeutig als Fehler-LED-Ausgang sichtbar:

```text
EAT_WriteGpio(76, 1/0)
```

Signal- und Kommunikations-LEDs besitzen getrennte Wrapper (`led_high_*`, `led_middle_*`, `led_weak_*`, `led_communication_*`); deren konkrete GPIO-Nummern können bei Bedarf separat aufgelöst werden.

---

## 10. Praktisch nächste Tests am realen LTE-Modem

Ohne irgendeine Änderung am Gerät sind besonders wertvoll:

### Debug-Port prüfen

```sh
ls -l /dev/ttyGS0
```

und passiv beobachten, ob auf der USB-Gadget-Serial-Schnittstelle 115200-8N1 Debugmeldungen erscheinen.

### Statistik sichern

```sh
ls -l /data/phnixIot_device_statisic
cp /data/phnixIot_device_statisic /cache/phnixIot_device_statisic.copy
```

Noch konservativer per ADB direkt vom Host:

```sh
adb pull /data/phnixIot_device_statisic .
```

### GPIO50 nur passiv beobachten

Keine GPIO-Schreibtests nötig. Für die DOG-Frage genügt zunächst zu beobachten, ob die parallel laufende Originalsoftware während längerer Laufzeit/Offline-Phasen stabil bleibt; der statische Pfad zeigt bereits den periodischen `AT_GetCSQ -> Reset_All_DOG`-Aufruf.

---

## 11. Wichtigste neue Schlussfolgerungen

1. `/dev/ttyGS0` ist nicht nur ein zufälliger String: der Port wird beim normalen Start als **115200 8N1 Debug-UART** geöffnet.
2. `DebugTrace()` schreibt sowohl auf normale Prozessausgabe als auch auf diesen Debug-FD.
3. GPIO50 wird während Mainboard-OTA indirekt durch den weiterlaufenden Signalthread bedient; die DOG-Risikoabschätzung muss entsprechend korrigiert werden.
4. `phnixIot_device_statisic` enthält viele klar benannte Hersteller-Langzeitmetriken und ist eine neue wertvolle Diagnosequelle.
5. Der Dienst misst Signal-Min/Max/Mittelwert selbst und speichert sie persistent.
6. Die Fehler-LED codiert interne Error-Bits als Blinkmuster.
7. `Get_Error_Flag()` enthält einen OR-vs-AND-Bug, scheint aber im aktuellen Pfad unbenutzt zu sein.
