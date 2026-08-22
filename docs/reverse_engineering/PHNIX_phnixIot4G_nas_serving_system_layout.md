# PHNIX `phnixIot4G` – NAS Serving-System Cache

Stand: 2026-08-22

Diese Datei ergänzt die QMI/NAS-Analyse um das konkrete Layout der regelmäßig gepollten Serving-System-Daten.

## 1. Zwei getrennte NAS-Pollpuffer

`NasAPI_thread_handle()` aktualisiert alle fünf Sekunden zwei globale Strukturen:

```text
get_NetworkType(0x981B4)
nas_get_serving_system(0x97BD0)
sleep(5)
```

Der erste Cache (`0x981B4`) ist der kompakte, produktiv für Registration/Attach/RAT verwendete NetworkType-Cache.

Der zweite Cache (`0x97BD0`) enthält eine große vollständige NAS-Serving-System-Antwort und dient unter anderem als Quelle für MCC/MNC/LAC/Cell-ID-Getter.

## 2. `nas_get_serving_system()`

Funktion: `0x21C88`

Die Funktion sendet synchron:

```text
NAS Message-ID: 0x24
Requestgröße:   1 Byte
Responsegröße:  0x5E4 = 1508 Byte
Timeout:        10000 ms
```

Bei erfolgreichem QMI-Result wird der komplette 1508-Byte-Response nach dem vom Aufrufer gelieferten Puffer kopiert. Im Runtime-Thread ist dieser Puffer `0x97BD0`.

Damit ist `0x97BD0` kein PHNIX-eigenes kompaktes Mapping, sondern weitgehend eine gecachte Qualcomm-NAS-Response-Struktur.

## 3. Exakte Getter-Offets

Die vier öffentlichen Getter lesen direkt aus diesem Cache:

| Getter | Funktion | absolute Adresse | Offset ab `0x97BD0` | Typ |
|---|---:|---:|---:|---|
| `NasAPI_get_MCC()` | `0x1E2FC` | `0x98022` | `0x452` | `uint16_t` |
| `NasAPI_get_MNC()` | `0x1E328` | `0x98024` | `0x454` | `uint16_t` |
| `NasAPI_get_LAC()` | `0x1E354` | `0x98168` | `0x598` | `uint16_t` |
| `NasAPI_get_CELL_ID()` | `0x1E380` | `0x9816C` | `0x59C` | `uint32_t` |

Das ist statisch eindeutig aus den direkten Load-Instruktionen der Getter ablesbar.

## 4. Bedeutung

Damit können im VM-/Runtime-Lab später ohne erneute semantische Rekonstruktion genau diese vier Felder im gecachten NAS-Response beobachtet werden:

```text
MCC     = *(uint16_t *)(0x97BD0 + 0x452)
MNC     = *(uint16_t *)(0x97BD0 + 0x454)
LAC     = *(uint16_t *)(0x97BD0 + 0x598)
CELL_ID = *(uint32_t *)(0x97BD0 + 0x59C)
```

Die Feldlage bestätigt zugleich, dass die Firmware unterschiedliche technologiespezifische Teilstrukturen innerhalb der großen NAS-Antwort verwendet.

## 5. Getter sind im PHNIX-Applikationscode nicht produktiv aufgerufen

Für folgende Wrapper wurden im Executable keine internen Call-Sites gefunden:

```text
NasAPI_get_SignalStrength()
NasAPI_get_MCC()
NasAPI_get_MNC()
NasAPI_get_LAC()
NasAPI_get_CELL_ID()
```

Sie sind offenbar SDK-/Diagnose-API, die im aktuellen PHNIX-Programm nicht für MQTT-Startup oder OTA benötigt wird.

Das ist besonders bei Signalstärke relevant: der sichtbare Applikations-/LED-Fehlerpfad benutzt `AT_GetCSQ()`, nicht `NasAPI_get_SignalStrength()`.

## 6. Produktiv wichtig bleibt `registration_state`

Der produktiv verwendete Getter ist dagegen:

```text
NasAPI_get_registration_state()
```

und liest aus dem separaten kompakten NetworkType-Cache `0x981B4`.

`aliMqtt_handle_thread()` blockiert solange, bis dieser Wert `1` ist.

Damit sollte eine minimale QMI/NAS-Emulation für das Lab zuerst nur sicherstellen:

```text
get_NetworkType() erfolgreich
registration_state = 1
```

MCC/MNC/LAC/CELL_ID und der QMI-Signalstärkegetter sind für das Erreichen des MQTT-Startups nach statischem Stand nicht zwingend erforderlich.

## 7. Übergabe an Work

```text
NAS sync poll:
- msg 0x24
- response 1508 bytes
- full serving-system cache @ 0x97BD0

Fields:
- MCC     +0x452
- MNC     +0x454
- LAC     +0x598
- CELL_ID +0x59C

Startup-critical:
- registration_state comes from separate cache @ 0x981B4
- MCC/MNC/LAC/CELL_ID getters are not internally used in this build
```
