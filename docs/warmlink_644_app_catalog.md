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

Ein Live-Test mit einem Residence-Mitglied zeigt: `deviceList` kann leer sein,
während ein bekannter `deviceCode` über `getDataByCode` vollständig autorisiert
ist. Deshalb verwirft der Worker einen gespeicherten Code nicht mehr, sondern
validiert und nutzt ihn direkt. Ohne bekannten Code wird weiterhin ehrlich
gemeldet, dass keine automatische Discovery möglich war.

`getMyAppectDeviceShareDataList` (einschließlich des API-Tippfehlers „Appect“)
ist nach Live-Test **nur die ältere direkte Gerätefreigabe und nicht die neue
Residence-/House-Geräteliste**. Die App besitzt separate House-, Member-, Floor-
und Room-Funktionen, deren REST-Endpunkte wegen Jiagu jedoch unbekannt bleiben.
FoxAir Control erfindet daher keine `/house`- oder `/residence`-Pfade. Eine
dritte Discovery-Quelle „Residence/House“ bleibt offen.

## Fault-Namespace

`WARMLINK_644_APP_FAULTS` enthält alle 93 gelieferten App-Fehlertexte separat
von `WARMLINK_644_APP_PARAMETERS`. Dadurch bezeichnet beispielsweise Parameter
`F01` weiterhin „Fan Motor Type“, während Fault `F01` „Compressor Activation
Failure“ bedeutet. Die Fault-Texte sind App-Inventar, keine neuen Parameter-
oder Schreibcodes.

SG Ready, Tarife, Zonen, Kaskade, Timer, Statistik/PV und weitere sichtbare
App-Funktionen liefern ohne bekannte konkrete API keine zusätzliche Funktionalität.
Vorhandenes SG-Ready-Reverse-Engineering bleibt maßgeblich.
