# WarmLink 3.0.4: PHNIX-Gerätefamilie 644

## Quelle und Evidenzstufen

Der Katalog in `cloud/warmlink_644_catalog.py` stammt aus den statisch lesbaren
Android-Ressourcen (`param_644_*`) der offiziellen **WarmLink 3.0.4**-App
(`com.phinx.Warmlink`, Build 2026-06-18). Er enthält exakt **254 Parameter** und
einen getrennten Katalog von **93 Fault-Bezeichnungen**.

Ein App-Ressourceneintrag beweist nur **App-known**. Er beweist weder, dass
`getDataByCode` den Code unterstützt, noch eine Modbus-Adresse oder
Schreibbarkeit. FoxAir Control hält deshalb vier Ebenen auseinander:

1. live/Firmware/Modbus-bestätigte vorhandene Metadaten,
2. vorhandenes Reverse Engineering,
3. offizielle App-Bezeichnung (`app_label_644`),
4. unbestätigte Kandidaten.

`merged_cloud_metadata()` ergänzt die App-Bezeichnung, lässt aber bestehende
Namen, `confidence`, Modbus-Adressen und zuvor bestätigte Schreibfreigaben
gewinnen. Beispiel: Für `A03` bleibt das bestätigte GL9-Mapping auf Register
1037 erhalten; die widersprechende App-Bezeichnung „Shutdown Ambient Temp.“ ist
parallel sichtbar. App-only-Codes sind immer read-only.

Die Android-Suffixe `D05_1`, `E03_1` … und `E07_1` … werden für Discovery auf
die bereits beobachtete Cloud-Schreibweise mit Bindestrich normalisiert. Beide
Varianten werden nicht doppelt angefragt.

## Discovery und generisches Auslesen

`WARMLINK_644_DISCOVERY_CODES` verbindet den bisherigen Cloud-Dump mit den
App-Kandidaten. Dazu gehören insbesondere die noch nicht live als Einzelcodes
bestätigten Ausgänge `O01`, `O03`–`O13`, `O21`–`O23` sowie Eingänge `S01`–`S07`
und `S10`. Gruppencodes wie `O01~023` und `S01~S10` bleiben unverändert erhalten.
Ein Kandidat ist keine Schreibfreigabe.

Große Reads erfolgen blockweise. Ein nicht unterstützter oder fehlerhafter
Block wird als leer/unsupported geführt und verhindert nicht die Auswertung der
anderen Blöcke. Erfolgreiche Antworten behalten `dataType`, `rangeStart` und
`rangeEnd`. Damit kann eine weitere Anlage derselben Familie mit dem erweiterten
read-only Katalog untersucht werden, ohne die GL9-Zuordnungen zu verändern.
Transport- und Authentifizierungsfehler werden dagegen nicht als „unsupported“
verschluckt oder durch Bisektion vervielfacht, sondern gehen in den normalen
Worker-Retry. `cloud_supported` ist nur ein Live-Ergebnis; das Vorhandensein
statischer Mapping-Metadaten wird separat als `cloud_hint_known` geführt.

Der vollständige Katalog wird nur im ersten Discovery-Lauf eines Workers
verwendet. Danach behält der Worker für diese Sitzung ausschließlich Codes, die
das konkrete Gerät mit einem Wert beziehungsweise Datentyp unterstützt hat.
Damit werden App-only-Kandidaten, die leer zurückkamen, nicht bei jedem
Dauer-Poll erneut übertragen. Ein neuer Test-, Poll- oder manueller Vollscan
startet einen neuen Worker und kann die Discovery bewusst wiederholen.

Die WarmLink-3.0.4-Produktliste ergänzt die bislang 30 bekannten IDs um
`1737029209242152961`. Ein konkreter Modellname ist nicht bekannt und wird nicht
behauptet.

## Geräte- und Account-Discovery

Aus dem unverschlüsselten Assistant-Bundle sind folgende Pfade bestätigt:

- `POST app/user/getUserInfo`
- `POST app/device/deviceList`
- `POST app/device/getMyAppectDeviceShareDataList`
- `POST app/device/updateDeviceNickName`

Der API-Client bietet `getUserInfo` und den Legacy-Share-Aufruf getrennt an.
Geräteantworten werden unverändert weitergereicht, sodass tatsächlich gelieferte
Felder wie `deviceId`, `deviceCode`, `productId`, `productionCode`,
`deviceNickName`, `deviceStatus`, `isFault` sowie vorhandene Firmwarefelder in
der bestehenden Diagnosetabelle erhalten bleiben.

Ein Live-Test mit einem Residence-Mitglied zeigt: `deviceList` kann die eigene
Anlage liefern und trotzdem eine freigegebene Residence-Anlage auslassen.
WarmLink 3.0.5 machte die echten PHNIX-/Retrofit-Klassen im normalen DEX
sichtbar; daraus wurden die House-Endpunkte statisch rekonstruiert und am
2026-10-04 anschließend live bestätigt:

- `GET house/info/listOwnerHouses` (ohne Body)
- `POST houseRelDevice/v4/selectHouseToDeviceData` mit
  `{"appId": 16, "houseId": "<ID>", "level": 0}`

`listOwnerHouses` lieferte dabei sowohl das eigene als auch freigegebene Houses
anderer Creator. Beobachtet wurde `roleType=0` beim eigenen House und
`roleType=1` bei Mitgliedschaft/Freigabe. Das ist keine abschließende Enum-
Definition; unbekannte weitere Werte werden akzeptiert und `roleType` ist keine
Voraussetzung für Discovery. House-Geräte werden sowohl direkt aus
`data[].houseRelDeviceList[]` als auch aus
`data[].roomInfoResultList[].houseRelDeviceList[]` gelesen.

Damit gilt die bisher offene Residence-/House-Discovery praktisch als
geschlossen. Die normale Discovery priorisiert `deviceList`, danach
House/Residence und zuletzt manuelle Fallback-Codes. Deshalb können im
Cloud-Dialog weiterhin mehrere bekannte Gerätecodes ergänzt werden.
FoxAir Control prüft jeden Code vor dem Speichern mit einer kleinen, rein
lesenden `getDataByCode`-Abfrage (`MainBoard Version` und `code_version`) und
führt ihn anschließend mit `deviceList` zusammen. Cloud-Einträge haben bei
doppelten Codes Vorrang, sodass Nickname, IDs, Produktdaten und Status erhalten
bleiben. Die Codes werden als `warmlink_cloud.known_device_codes` in den
bestehenden Settings gespeichert und können im Dialog wieder entfernt werden.

Diese Eingabe umgeht **keine Berechtigung**: Ein Gerätecode allein ermöglicht
keinen Zugriff auf eine fremde Anlage. Der angemeldete Account muss in WarmLink
bereits Zugriff besitzen; FoxAir Control macht lediglich einen schon
autorisierten Code auswählbar, den die automatische Discovery nicht liefert.

`getMyAppectDeviceShareDataList` (einschließlich des API-Tippfehlers „Appect“)
ist nach Live-Test weiterhin nur die ältere direkte Gerätefreigabe. Die
manuelle Liste bleibt als Fallback für ältere Serverstände, Diagnose und
ungewöhnliche Share-Szenarien erhalten.

Normalisierte House-Geräte enthalten nur technisch benötigte Gerätefelder.
`deviceSecret`, ICCID, IMEI/MAC, Hausadresse und GPS-Koordinaten werden weder in
die Geräteliste übernommen noch persistiert oder geloggt.

## Fault-Namespace

`WARMLINK_644_APP_FAULTS` enthält alle 93 gelieferten App-Fehlertexte separat
von `WARMLINK_644_APP_PARAMETERS`. Dadurch bezeichnet beispielsweise Parameter
`F01` weiterhin „Fan Motor Type“, während Fault `F01` „Compressor Activation
Failure“ bedeutet. Die Fault-Texte sind App-Inventar, keine neuen Parameter-
oder Schreibcodes.

SG Ready, Tarife, Zonen, Kaskade, Timer, Statistik/PV und weitere sichtbare
App-Funktionen liefern ohne bekannte konkrete API keine zusätzliche Funktionalität.
Vorhandenes SG-Ready-Reverse-Engineering bleibt maßgeblich.

## Live-Test Familie 644 / Firmware 3.4

Auf einer weiteren realen Anlage (Gerätecode aus Datenschutzgründen hier
gekürzt) wurden `MainBoard Version = 644` und `code_version = 3.4` geliefert.
`Fault1` bis einschließlich `Fault10` wurden jeweils als `BINARY` /
`dataTypeAi=binary` zurückgegeben. Damit sind insbesondere die zuvor fehlenden
Cloudcodes `Fault9` und `Fault10` live bestätigt. Im beobachteten Zustand waren
alle Wörter null bis auf:

```text
Fault8 = 0000001000000000 = 0x0200 (Bit 9)
```

Die Bedeutung dieses Bits ist noch offen und wird nicht spekulativ benannt.
Die lokale Zuordnung ist für diese Gerätefamilie stark plausibel, wurde an der
fremden Anlage aber nicht gleichzeitig per Modbus gegengeprüft:

| Cloud | wahrscheinliches lokales Fehlerwort | Modbus |
|---|---:|---:|
| Fault1 … Fault6 | Fehlerwort 1 … 6 | 2085 … 2090 |
| Fault7 … Fault10 | Fehlerwort 7 … 10 | 2081 … 2084 |

Die Metadaten führen deshalb die Cloudunterstützung als live bestätigt, die
Registerzuordnung jedoch nur als `strongly-inferred-family-644`; daraus entsteht
weder ein bestätigtes Modbus-Mapping noch eine Schreibfreigabe.

Gleichzeitig wurde `O01~023 = 0000010000000000 = 0x0400` beobachtet, während der
physische Alarm-/Sammelstörungsausgang aktiv war. Damit ist Bit 10 dieses
gruppierten Ausgangsworts erneut live bestätigt. Die App-Ressource `O11 = Alarm`
bleibt als App-Wissen erhalten, aber die Einzelabfragen `O11` und `O011` kamen
auf diesem 644-/FW3.4-Gerät leer und sind nicht cloud-bestätigt.

Trotz `Fault8 = 0x0200` und aktivem `O01~023` Bit 10 meldete
`getDeviceStatus` gleichzeitig `isFault=false`; außerdem lieferte
`getFaultDataByDeviceCode` eine leere `objectResult`-Liste. Diese Status- und
Historienendpunkte sind daher keine alleinige Quelle für aktuelle rohe
Störungsbits. Der Worker wertet die unabhängig gelesenen `Fault1…Fault10`-Wörter
weiter aus und schließt aus `isFault=false` nicht auf einen störungsfreien
Rohzustand. Warum die Cloud diese Sichten unterschiedlich filtert, bleibt offen.

WarmLink 3.0.5 legte zusätzlich
`POST app/device/v2/getFaultDataByDeviceCode` offen. Live bestätigt ist das
Payload `{"deviceCodeList": ["<deviceCode>"]}`; das alte Singularfeld
`deviceCode` wird mit einer Validierungsfehlermeldung abgelehnt. Eine leere
erfolgreiche `objectResult`-Historie und `isFault=false` können gleichzeitig mit
aktiven `Fault1…Fault10`-Rohbits auftreten. Der v2-Endpunkt ist deshalb eine
Backend-Historien-/Eventsicht und überschreibt niemals die aktuellen Raw-
Faultwörter oder deren Decoder-Projektion.

## Mehrgeräteverwaltung und Cloud-Projektion

Mehrere manuell validierte Gerätecodes werden dauerhaft als deduplizierte Liste
`warmlink_cloud.known_device_codes` gespeichert und im Reiter **Geräte** separat
verwaltet. Die Auswahlliste bildet die Vereinigung aus `deviceList` und den
manuellen Codes; Metadaten aus `deviceList` haben Vorrang. Ein manueller Eintrag
kann ausgewählt oder entfernt werden, ohne automatisch gefundene Geräte zu
entfernen.

Ist **Cloud im Hauptfenster anzeigen** aktiv, werden alle sinnvoll auf lokale
Register projizierbaren Werte automatisch angezeigt – auch ohne vorherigen
Modbus-Read. Der frühere Schalter „Cloud-only-Zeilen“ entfällt; sein Setting wird
nur kompatibel eingelesen. Lokale Modbuswerte haben immer Vorrang und werden nie
mit Cloudwerten überschrieben. Fehler-, Kontakt- und Lastausgangdecoder verwenden
die getrennt gespeicherte Cloud-Projektion lediglich als Fallback.

Ein zentraler Translator nutzt `value_map` und `bit_map` aus
`data/foxair_phnix_registers.json`. Er liefert Rohwert, Hexdarstellung,
Anzeigetext und aktive Bits für `O01~023`, `S01~S10`, Fault-Wörter und normale
ENUM-Werte. Unbekannte aktive Bits bleiben ausdrücklich sichtbar.

`Fault1` bis `Fault10` sind seit dem GL9-Test vom 2026-10-06 zentral mit
MAIN 2081 bis 2090 **bestätigt** und bleiben read-only. Die frühere
Family-644-Kandidatenzuordnung ist ersetzt; Details und Kurvenzuordnungen stehen
in [Polling und Readback](warmlink_polling_and_readback.md#v033-bestätigte-fault-reihenfolge-und-warmlink-305-kurve).

## SG-Pfade und Negativbefunde aus WarmLink 3.0.5

Der gemeinsame SG-Dialog verwendet bei `protocol == 773` die Codes `2119` und
`Switch2168`. Der GL9-/416-/644-Pfad verwendet dagegen `SG Status` → MAIN 2133
und `S01~S10` → MAIN 2034. Der vom Anwender bestätigte GL9-Livetest vom
2026-10-06 ergab gleichzeitig:

| Cloudcode | Antwort | Befund |
| --- | --- | --- |
| `S01~S10` | `0010110000000000` = `0x2C00` = 11264 | stimmt mit MAIN 2034 überein |
| `SG Status` | `3` | bestätigtes Mapping nach MAIN 2133 |
| `2119` | `DIGI1`, `0` | serverseitig akzeptiert, kein SG-Status-Alias für 644 |
| `Switch2168` | Wert und Datentyp leer | tested unsupported auf dieser GL9/644 |

`2119` darf insbesondere **nicht** auf MAIN 2119 projiziert werden:
das lokale Register ist der High-Anteil des Heiz-Wärmemengenzählers. Beide
773-Codes sind für Discovery dokumentiert und read-only, ohne `modbus_register`
und ohne Projektionsfreigabe. Historischer Testsupport bestätigt weder ein
Mapping noch den Support im aktuellen Scan. Unterstützte ungemappte Werte
bleiben in der Cloudansicht; es entstehen keine virtuellen MAIN-Adressen.

Die 14 CP-Codes und `Zone 2 Curve Offset` tragen explizites App-Wissen.
`CP1-4`, alle CP2-Punkte und der Zone-2-Mittelpunkt bleiben bewusst ungemappt.
`I28`, `H55`, `T100` und `T101` stammen aus `DeviceDetails923Activity` und
gehören weder zum 644-Discovery-Katalog noch zu dessen zentralen Mappings.

## Statischer Mapping-Audit und MAIN-Projektion

```bash
python tools/audit_cloud_mappings.py
python tools/audit_cloud_mappings.py --rows current_scan_rows.json
```

Der zweite Aufruf nimmt eine JSON-Liste normalisierter Datensätze eines
aktuellen Scans (`code`, `supported`, weitere Responsefelder optional).
Ohne diese Liste bleibt Laufzeitsupport unbekannt (`null`); es werden keine
Cloudanfragen ausgelöst. Der Bericht unterscheidet App-/Discovery-Wissen,
Hints, bestätigte MAIN-Mappings, fehlende und bewusst nicht vorhandene
Mappings. Nur fehlerhafte bestätigte Targets/Resolver führen zum Exitcode 1;
unbekannte Zuordnungen und bekannte Aliasse werden getrennt gemeldet.

Stand dieses Audits: **436 bekannte Discoverycodes**, davon 271 mit
App-Wissen; **278 bestätigte Codes für 275 MAIN-Register**. Für 147 Codes fehlt
eine bestätigte Zuordnung, 11 bleiben explizit bewusst ungemappt. Ohne aktuellen
Gerätescan ist deren Laufzeitsupport unbekannt.

Die parametrisierten GUI-Tests prüfen **jedes** bestätigte Mapping über
`_validated_cloud_modbus_register()` und `apply_cloud_rows_to_main()` sowohl
als Cloud-only-Zeile als auch als Overlay eines echten lokalen Registers.
Alle 278 bestehen; kein Mapping fällt wegen eines Code-Mismatchs heraus.
Lokaler Rawwert und Provenienz bleiben erhalten. Deshalb war kein Umbau des
Hauptlistenpfads erforderlich. Fault-/CP1-Mappings waren bereits auf `work`
vorhanden; CSV verwendet weiterhin zentral 51 Codes für 50 Registerplätze,
einschließlich der zehn Fault-Wörter.

Der Audit weist drei bestätigte Aliaspaare aus:

| MAIN | Cloudcodes |
| ---: | --- |
| 1206 | `1206`, `E03-3` |
| 1208 | `1208`, `E03-5` |
| 2029 | `2029`, `InputCurrent1` |

Alle Codes eines Paares sind gültig; pro MAIN entsteht eine Zeile. Im selben
Batch verwendet die bestehende Hauptliste die erste unterstützte Antwort in
Response-Reihenfolge. Ein späterer Einzelread des anderen Alias aktualisiert
dieselbe Zeile. CSV übernimmt den ersten frischen verfügbaren Aliaswert.
Kein Alias wird als Mappingfehler behandelt oder auf eine zweite Adresse
umgebogen; eine zusätzliche bevorzugte Codezuordnung war nicht erforderlich.
