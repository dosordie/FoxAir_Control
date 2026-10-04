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
Anlage liefern und trotzdem eine freigegebene Residence-Anlage auslassen,
obwohl deren bekannter `deviceCode` über `getDataByCode` vollständig autorisiert
ist. Deshalb können im Cloud-Dialog mehrere bekannte Gerätecodes ergänzt werden.
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
ist nach Live-Test **nur die ältere direkte Gerätefreigabe und nicht die neue
Residence-/House-Geräteliste**. Die App besitzt separate House-, Member-, Floor-
und Room-Funktionen, deren REST-Endpunkte wegen Jiagu jedoch unbekannt bleiben.
FoxAir Control erfindet daher keine `/house`- oder `/residence`-Pfade. Eine
dritte Discovery-Quelle „Residence/House“ bleibt offen.
Die manuelle Liste bekannter Gerätecodes ist bis zur Identifikation eines
bestätigten Residence-/House-Discovery-Endpunkts der sichere Fallback.

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

`Fault1` bis `Fault10` dürfen für die read-only Anzeige anhand der stark
abgeleiteten Family-644-Zuordnung projiziert werden. Ihre Modbus-Confidence bleibt
`candidate` beziehungsweise `strongly-inferred-family-644`; daraus entstehen
weder ein `confirmed`-Mapping noch Schreibrechte.
