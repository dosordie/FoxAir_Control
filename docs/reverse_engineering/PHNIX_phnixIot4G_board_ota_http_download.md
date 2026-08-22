# PHNIX `phnixIot4G` – Board-OTA HTTP/libcurl-Dateipfad

Stand: 2026-08-23

Diese Notiz rekonstruiert ausschließlich den Downloadpfad der Mainboard-Firmware:

```text
board_ota_http_download() @ 0x1D520
  -> ota_download_device_otaFile() @ 0x19E70
  -> ota_check_device_otaFile_md5() @ 0x1A370
```

Ziel ist ein bytegenauer Guard-Punkt für isolierte Labortests und die Klärung, wann `/cache/phnixIot_device_OTA` erstmals verändert wird.

## 1. `board_ota_http_download()`

Disassembly:

```text
0x1D528  BL ota_download_device_otaFile
0x1D530  CMP r0,#0
0x1D534  BLT download_failed
0x1D538  BL ota_check_device_otaFile_md5
0x1D540  CMP r0,#0
0x1D544  BLT md5_failed
0x1D548  return 0

0x1D558  BL ota_device_send_ota_FirmwareDownloadFailed
0x1D55C  return -1

md5_failed:
0x1D550  return -1
```

Damit gilt:

```c
int board_ota_http_download(void)
{
    if (ota_download_device_otaFile() < 0) {
        ota_device_send_ota_FirmwareDownloadFailed();
        return -1;
    }

    if (ota_check_device_otaFile_md5() < 0)
        return -1;

    return 0;
}
```

Nur ein Transport-/curl-Fehler löst hier unmittelbar die Cloudmeldung `FirmwareDownloadFailed` aus. Ein MD5-Fehler wird lediglich als `-1` zurückgereicht; die weitere State-Machine behandelt den Fehler später.

---

## 2. Erstes Verändern der Firmwaredatei

`ota_download_device_otaFile()` beginnt mit:

```text
0x19E7C  r0 = "/cache/phnixIot_device_OTA"
0x19E84  r1 = "wb"
0x19E8C  BL fopen
```

`"wb"` bedeutet: Existiert die Datei bereits, wird sie bereits durch den erfolgreichen `fopen()`-Aufruf auf Länge 0 gekürzt.

Der **erste Dateieingriff ist daher nicht `curl_easy_perform()`, sondern `fopen(...,"wb")` selbst.**

### Letzter sicherer Breakpoint vor jeder Änderung an `/cache/phnixIot_device_OTA`

```gdb
b *0x19E8C
```

GDB hält vor Ausführung der `BL fopen`-Instruktion. Zu diesem Zeitpunkt:

- JSON und OTA-Metadaten können bereits verarbeitet sein,
- der Board-State kann bereits Step 3 sein,
- `/cache/phnixIot_device_OTA` wurde durch diesen Downloadpfad noch nicht geöffnet, angelegt oder gekürzt,
- noch kein libcurl-Handle wurde erzeugt,
- noch kein Netzwerktransfer fand statt.

Für einen Download-sicheren Guard ist `0x19E8C` damit genauer als der gröbere Breakpoint `0x1D860` vor `board_ota_http_download()`.

---

## 3. `ota_download_device_otaFile()` vollständig

### 3.1 Datei öffnen

```c
FILE *fp = fopen("/cache/phnixIot_device_OTA", "wb");
if (!fp) {
    debugTrace("can not create file /cache/phnixIot_device_OTA....\n");
    return -1;
}
```

Dateipfad-String: VA `0x084024`.
Modus-String `"wb"`: VA `0x083F30`.

### 3.2 curl-Handle

```text
0x19EB4  curl_easy_init()
```

Bei erfolgreichem Handle beginnt die Konfiguration. Auffällig ist der Fehlerpfad bei `curl_easy_init()==NULL`, siehe Abschnitt 7.

### 3.3 Exakte `curl_easy_setopt()`-Optionen

Die Funktion ignoriert die Rückgabewerte sämtlicher `curl_easy_setopt()`-Aufrufe.

| Adresse | Option | numerischer Wert | gesetzter Wert |
|---:|---|---:|---|
| `0x19EE4` | `CURLOPT_URL` | `10002 / 0x2712` | `otaDeviceInfo.otaFileDownloadAddr` (`0x933E1`) |
| `0x19F04` | `CURLOPT_WRITEFUNCTION` | `20011 / 0x4E2B` | `downLoadPackage @ 0x19A54` |
| `0x19F20` | `CURLOPT_WRITEDATA` | `10001 / 0x2711` | geöffnetes `FILE *fp` |
| `0x19F3C` | `CURLOPT_POST` | `47` | `0` |
| `0x19F58` | `CURLOPT_NOPROGRESS` | `43` | `0` (Progresscallback aktiv) |
| `0x19F78` | `CURLOPT_PROGRESSFUNCTION` | `20056 / 0x4E58` | `assetsManagerProgressFunc @ 0x19ACC` |
| `0x19F94` | `CURLOPT_PROGRESSDATA` | `10057 / 0x2749` | `NULL` |
| `0x19FB0` | `CURLOPT_NOSIGNAL` | `99` | `1` |

Nicht gesetzt werden in diesem Pfad unter anderem:

```text
CURLOPT_FOLLOWLOCATION
CURLOPT_CONNECTTIMEOUT
CURLOPT_TIMEOUT
CURLOPT_FAILONERROR
CURLOPT_PROTOCOLS / CURLOPT_REDIR_PROTOCOLS
CURLOPT_SSL_VERIFYPEER
CURLOPT_SSL_VERIFYHOST
CURLOPT_CAINFO
```

Folgen:

- Redirects werden vom Anwendungscode nicht explizit aktiviert.
- Es gibt hier keinen expliziten Connect-/Gesamttimeout.
- HTTP-Status >=400 wird nicht via `CURLOPT_FAILONERROR` zu einem curl-Fehler gemacht.
- Die URL wird ohne app-eigene Scheme-Whitelist an libcurl übergeben.
- Bei HTTPS werden die libcurl-Defaults für Zertifikatsprüfung verwendet; diese Funktion schaltet sie nicht ab und setzt keine eigene CA.

Die konkrete Menge erlaubter URL-Schemes hängt damit von der eingebauten libcurl-Version/Buildkonfiguration ab, nicht von einer PHNIX-Prüfung in diesem Handler.

---

## 4. URL-Herkunft

`CURLOPT_URL` erhält direkt:

```text
otaDeviceInfo + 0x35
VA 0x933E1
```

Das ist das aus `0033.param.otaFileDownloadAddr` kopierte Feld.

Vor `curl_easy_setopt(CURLOPT_URL, ...)` erfolgt in `ota_download_device_otaFile()` keine weitere Prüfung auf:

```text
leeren String
http://
https://
Hostname
Port
Pfad
Loopback/private IP
```

Damit ist die Download-URL aus Sicht dieses Pfades ein opaker libcurl-String.

---

## 5. Schreibcallback `downLoadPackage()` @ `0x19A54`

Rekonstruiert:

```c
size_t downLoadPackage(void *ptr, size_t size, size_t nmemb, FILE *fp)
{
    size_t n = size * nmemb;

    if (fp != NULL) {
        fwrite(ptr, size, nmemb, fp);
        return n;
    }

    debugTrace(...);
    return 0;
}
```

Wichtig: Der Rückgabewert von `fwrite()` wird **ignoriert**.

Der Callback meldet libcurl immer `size*nmemb` als erfolgreich verarbeitet, sofern `fp != NULL`, auch wenn `fwrite()` weniger Daten geschrieben hat.

Damit können lokale I/O-/Datenträgerfehler dem curl-Transport verborgen bleiben. Die spätere MD5-Prüfung ist der eigentliche Schutz gegen einen beschädigten/verkürzten Inhalt.

---

## 6. `curl_easy_perform()` und HTTP-Response-Code

```text
0x19FB8  curl_easy_perform(curl)
```

Bei `CURLE_OK` folgt:

```text
curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code)
```

`CURLINFO_RESPONSE_CODE` wird als `0x200002` übergeben.

Der Response-Code wird lediglich geloggt:

```text
received http/https Response Code: %d;
```

Es gibt danach **keine Prüfung auf 200, 2xx oder irgendeinen anderen Statusbereich**.

Damit kann beispielsweise ein HTTP-404-Transfer auf curl-Ebene als erfolgreich behandelt werden, sofern libcurl selbst `CURLE_OK` liefert. Ob die Datei später akzeptiert wird, entscheidet dann die MD5-Prüfung.

Auch ein Fehler von `curl_easy_getinfo()` wird als Downloadfehler behandelt, weil dessen Rückgabewert den lokalen `result` überschreibt.

Bei `curl_easy_perform()!=CURLE_OK`:

```text
curl_easy_strerror(result)
debugTrace("Exec http/https failed: %s\n", ...)
```

Danach Cleanup und Rückgabe `-1`.

---

## 7. Auffälliger `curl_easy_init()==NULL`-Fehlerpfad

Wenn `curl_easy_init()` NULL liefert:

```text
0x19EC4  BEQ 0x1A084
```

`0x1A084` ist jedoch der gemeinsame „succeed downloading package“-Pfad:

```text
debugTrace("succeed downloading package /cache/phnixIot_device_OTA")
fflush(fp)
fsync(fileno(fp))
fclose(fp)
return 0
```

Das bedeutet tatsächlich:

```c
fp = fopen(...,"wb");      // Datei wird geleert/angelegt
curl = curl_easy_init();
if (curl == NULL) {
    // BUG: wird als Erfolg behandelt
    fflush(fp);
    fsync(fileno(fp));
    fclose(fp);
    return 0;
}
```

`board_ota_http_download()` ruft danach trotzdem die MD5-Prüfung auf. Bei normalem `fileSize > 0` sollte die leere Datei den erwarteten MD5 nicht bestehen, aber der Downloadteil selbst meldet irrtümlich Erfolg.

---

## 8. Datei-Sync nach erfolgreichem curl-Pfad

Wenn der lokale `result == CURLE_OK`, wird nach `curl_easy_cleanup()` ausgeführt:

```text
0x1A090  fp
0x1A094  fflush(fp)
0x1A09C  fileno(fp)
0x1A0A8  fsync(fd)
0x1A0B0  fclose(fp)
0x1A0B4  return 0
```

Damit wird ein curl-erfolgreicher Download explizit bis zum Dateisystem synchronisiert, bevor die MD5-Prüfung beginnt.

Bei curl-Fehler wird dagegen nur `fclose(fp)` ausgeführt; kein `fflush()+fsync()`-Block.

---

## 9. Progresscallback

`assetsManagerProgressFunc() @ 0x19ACC` berechnet:

```text
percent = (dlnow / dltotal) * 100
```

Nur bei exakt:

```text
25
50
75
100
```

wird ein OTA-Fortschritts-Publish ausgelöst.

Bei `ota_info[0] == 2` (Board-OTA) wird:

```text
ota_device_send_ota_progress(percent)
```

aufgerufen.

Der Callback gibt immer `0` zurück und bricht den Transfer daher nicht selbst ab.

`CURLOPT_PROGRESSDATA` ist NULL; der Callback entscheidet anhand globaler OTA-Zustände.

---

## 10. `ota_check_device_otaFile_md5()` – tatsächliche Größen-/MD5-Prüfung

Die Funktion benutzt:

```text
otaDeviceInfo.fileSize @ +0x10
otaDeviceInfo.fileMD5  @ +0x14 (VA 0x933C0)
```

Ablauf:

```c
expected = otaDeviceInfo.fileSize;
buf = malloc(expected + 1);
memset(buf, 0, expected + 1);
fp = fopen("/cache/phnixIot_device_OTA", "rb");

if (fp && buf) {
    nread = fread(buf, 1, expected, fp);
    fclose(fp);

    MD5Init(&ctx);
    MD5Update(&ctx, buf, expected);   // NICHT nread
    MD5Final(...);

    computed_md5 = uppercase_hex(...);
    expected_md5 = uppercase(otaDeviceInfo.fileMD5);

    if (memcmp(computed_md5, expected_md5, strlen(expected_md5)) == 0)
        return 0;
}
return -1;
```

### Wichtige Konsequenz: keine echte Dateilängenprüfung

Die Funktion loggt zwar `nread` und `expected`, prüft aber **nicht**:

```c
nread == expected
```

Weil der Puffer vorher genullt wird und `MD5Update()` immer `expected` Bytes hasht, gilt:

- Datei kürzer als `fileSize`: fehlende Bytes werden effektiv als `0x00` gehasht.
- Datei länger als `fileSize`: nur die ersten `fileSize` Bytes gehen in den MD5 ein; angehängte Daten werden ignoriert.

Damit ist die früher vereinfachte Formulierung „Dateigröße + MD5 werden geprüft“ zu korrigieren:

**Im Board-OTA-Pfad ist `fileSize` die Länge des MD5-Fensters, aber die tatsächliche Datei-Länge wird nicht explizit mit `fileSize` verglichen.**

Für eine normale Firmwaredatei muss der MD5 über exakt die erwarteten `fileSize` Bytes stimmen. Ein gewöhnlich verkürzter oder falscher Download fällt deshalb trotzdem durch, aber nicht aufgrund einer separaten Längenprüfung.

---

## 11. Erwarteter MD5-Vergleich

Der berechnete 16-Byte-Digest wird als 32-stelliger Hexstring aufgebaut und anschließend auf Uppercase gebracht.

Auch der erwartete String aus `otaDeviceInfo.fileMD5` wird vor dem Vergleich auf Uppercase gebracht.

Der Vergleich ist damit case-insensitive bezüglich der hexadezimalen Buchstaben.

Es findet keine Signatur-, Zertifikats-, Firmwareheader- oder Softwarecodeprüfung in dieser Funktion statt.

---

## 12. Fehler-/Erfolgsmatrix

| Ereignis | Datei bereits verändert? | Rückgabe `ota_download_device_otaFile` | MD5 danach? |
|---|---:|---:|---:|
| `fopen("wb")` schlägt fehl | nein | `-1` | nein |
| `fopen` OK, `curl_easy_init` NULL | ja, leer/neu | **`0` (Bug)** | ja |
| `curl_easy_perform` Fehler | ja/teilweise | `-1` | nein |
| HTTP 404, curl sonst OK | ja | `0` | ja |
| `curl_easy_getinfo` Fehler | ja | `-1` | nein |
| curl OK, falscher Inhalt | ja | `0` | ja -> `-1` |
| curl OK, MD5 stimmt | ja | `0` | ja -> Erfolg |

---

## 13. Relevante Breakpoints für Work

Für einen streng beobachtenden, dateisicheren Test:

```gdb
b *0x1D860   # vor board_ota_http_download()
b *0x19E8C   # LETZTER Punkt vor fopen("/cache/phnixIot_device_OTA","wb")
b *0x19FB8   # vor curl_easy_perform(); Datei ist zu diesem Zeitpunkt bereits geleert/angelegt
b *0x1A370   # Beginn MD5-Prüfung; Download und fsync sind bereits abgeschlossen
```

Der wichtigste Guard ist:

```gdb
b *0x19E8C
```

Wenn dort angehalten und nicht fortgesetzt wird, kann dieser Downloadpfad garantiert weder die Firmwaredatei verändern noch einen Netzwerkdownload starten.

---

## 14. Zusammenfassung für den isolierten Labortest

Der Pfad ist einfacher und zugleich etwas weniger streng als zunächst angenommen:

```text
Step 3
 -> fopen("/cache/phnixIot_device_OTA", "wb")  [erste Mutation]
 -> curl_easy_init
 -> URL direkt aus 0033
 -> GET-artiger Standardtransfer (POST explizit 0)
 -> fwrite-Callback
 -> HTTP-Code nur loggen
 -> fflush + fsync
 -> MD5 über exakt fileSize Bytes
 -> Vergleich gegen 0033.fileMD5
 -> erst bei Erfolg weiter zu Step 6
```

Nicht vorhanden sind in diesem Pfad:

```text
explizite Redirect-Freigabe
HTTP-2xx-Prüfung
echte Dateilängenprüfung
Firmwareheaderprüfung
SoftwareCode-/Versionprüfung am Binärinhalt
Signaturprüfung
app-eigene URL-Scheme-Whitelist
```

Für Work ist damit der präziseste Sicherheitsanker vor einem synthetischen lokalen Download `0x19E8C`.
