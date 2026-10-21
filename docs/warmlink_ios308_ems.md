# WarmLink iOS 3.0.8 und GoHeating-Pro-EMS-Erkenntnisse

Quellen: [#176](https://github.com/dosordie/FoxAir_Control/issues/176),
[#177](https://github.com/dosordie/FoxAir_Control/issues/177),
[#178](https://github.com/dosordie/FoxAir_Control/issues/178),
[#179](https://github.com/dosordie/FoxAir_Control/issues/179) und
[#180](https://github.com/dosordie/FoxAir_Control/issues/180).
Basis: work ffe6f194217702c1da204b677acc8baac0ac5dd6. Keine Versionserhöhung.

## Bestätigte Registersemantik

Warmlink-Serviceeingänge auf Slave 0x63 werden getrennt von MAIN, User-SG-Ready
und internen Firmwarepuffern behandelt. Alle 8001–8010 bleiben ohne
Schreibfreigabe. Bestehende 8021–8028 und 8055 wurden nicht geändert.

| Warmlink | MAIN-Spiegel | Bestätigte Bedeutung |
| --- | --- | --- |
| 8001 | 2151 | Übernommener EMS-/Remote-Modus 0..4; 0 kein Modus, Namen 1..4 offen |
| 8002 | 2153 | Electricity_Price; Einheit/Skalierung offen |
| 8003 | 2156 | Battery_Power; signed RAW, Einheit/Polarität offen |
| 8004 | 2154 | OnGrid Power; signed int16, Einheit/Polarität offen |
| 8005 | 2155 | Battery_SoC; RAW, keine bestätigte Prozentdarstellung |
| 8006 | kein gleichnummerierter Spiegel | Synchronisations-/Generation-Token |
| 8007 | 2157 | Neutraler EMS-Rohwert |
| 8008 | 2158 | Neutraler EMS-Rohwert |
| 8009/8010 | unbekannt | Lesbare Rohwerte ohne erfundene Bedeutung |

MAIN2152 ist ein u16-Bitfeld, kein direktes 800x-Datenregister:
Bits 0–2 sind thermische Vergleichszustände (Abschalt-/Überschussseite,
Hystereseband, Bedarfsseite). Nach V3.5-Abgleich vom 15.10.2026: Bit3 greift
in thermische Sollwert-/Hysteresepfade ein; Bit4 aktiviert den Frequenzcap-Pfad
über MAIN1422; Bit5 beeinflusst ein internes Flag, dessen physische Wirkung
offen bleibt; Bit6 entspricht MAIN2139 Bit9 (Mode 4); Bit7 ist der
30-min-Runtime-Qualifier. Bei Kommunikationssperre kann ein bereits gesetztes
Bit7 trotz Zählerrücksetzung vorübergehend stehen bleiben. OEM-Namen der
Bits3/5 bleiben offen; Status und messbare Regelwirkung sind zu unterscheiden.
MAIN1427 ist der separate lokale Schwellwert, User8801 bleibt SG-Ready.
Interne MAIN169x-Puffer sind keine bestätigten User-Schreibadressen.

MAIN2139 nutzt die zentrale BITFIELD-Anzeige mit bestätigten Bits 0, 1, 2, 3, 4, 5,
6, 8, 9 und 10. Bits0/2 heißen neutral thermische Regelzustände; für ihren
internen State1 ist ein Frequenz-Hold auf MAIN2071/T30 bestätigt, State2 und
OEM-Namen bleiben offen. Bit9 entspricht MAIN2152 Bit6. Auch unbekannte gesetzte Bits bleiben als HEX/Binärmaske sichtbar;
sie erhalten keine erfundenen Namen. Die bestehende Niederdruck-/PWM-RE-Notiz
bleibt erhalten. Die 21 OEM-Strings stehen als app_label_goheating_pro mit
Quellenmetadaten in der Registerdatei. Präzisere deutsche Namen, insbesondere
Softwarecode (MAIN2105, lokal bestätigt 644), bleiben bestehen.

## Beobachtete Codes und offene Livevalidierung

Vorher: 397 ALL-Codes, 436 Discovery-Codes. Die exakte 108er-Liste aus #178
enthält 14 bereits vorhandene Discovery-Kandidaten. Nach additiver Vereinigung:
505 ALL-Codes und 530 Discovery-Codes, ohne Duplikate oder verlorene Altcodes.
S01~S11 und O25~O27 sind dabei wörtliche protocalCodes, keine Bereiche.

Neue appbeobachtete Codes erhalten keine automatische MAIN-Adresse, Einheit,
Skalierung oder Schreibfreigabe. Bestehende bestätigte CP1-Mappings bleiben
stärker als die jüngere Appbeobachtung; für CP2 werden keine festen
Heizkurvennamen behauptet. H36 war bereits confirmed, MAIN1236 und schreibbar
und wurde nicht verändert. Batching, Token und App-Heartbeat bleiben erhalten.

Leere und nullhaltige Antworten unterscheiden sich von numerischem/stringförmigem
0. Für leere App-Kandidaten bleibt cloud_supported unbekannt statt dauerhaft
False. Separate retry_codes halten sie für spätere Reads offen, ohne eine
lokale Mappingklasse zu behaupten. Unbekannte Nicht-App-Codes behalten die
vorherige Behandlung.

Der Mitschnitt vom 10.10.2026 erfolgte mit ausgeschalteter WP. Der Folgetest
vom 14.10.2026 **bei aktiver WP ist erledigt**: T_PWM_Out2, T_PWM_IN2_1 und
T_PWM_IN2_2 liefern weiterhin keine Daten. Die Cloud-PWM-Forschung ist vorerst
geparkt; keine zusätzliche Pumpenrückmeldung, Prozent-/Hz-Skalierung oder
dauerhafte Unsupported-Klassifikation daraus ableiten. Zeitgleiche lokale
Kompressor-/Pumpenwerte wurden im Livetest nicht separat protokolliert.

Bestätigte Cloud-Aliasse sind implementiert: T49→2065 (°C), T50→2066 (K),
T51→2067 (K); die lokalen T-Diag1/2/3-Codes bleiben bestehen. Cloudwerte sind
bereits Engineering-Werte, lokale TEMP1-Rohwerte werden durch 10 geteilt.
T14→2050, T57→2023, H41→1346, R40/R41→1193/1194 sowie 1250/CP1-1 und
1256–1269 bleiben erhalten und sind auch lokal mit Cloud-Provenienz versehen.
Die alte 1250-Metadatenbezeichnung ist kein neuer Beleg für einen Systemzeit-Schalter.

T58=0 ist ein gültiger DIGI1-Wert mit offener Bedeutung. T52–T56 lieferten keine
Daten bzw. mindestens einen nicht genauer zugeordneten Nullwert. T06_1,
T100–T109 und T112–T120 bleiben ungemappte Zusatzcodes; fehlende Daten sind kein
dauerhafter Unsupported-Nachweis. Die alten Off-Werte sind historische
Beobachtungen, keine zusätzliche Semantik. Snapshot-Historie und AI-/SG-API bleiben
außerhalb des Scopes. Details und Primärbelege: [Register-Audit](register_audit_2026-10-15.md).

## OTA-Prüfvorlage

Die Vorlage befüllt POST app/device/ota/judgeUpgradeList?lang=de mit
appId als editierbarem beobachtetem iOS-String 16 und dem ausgewählten
deviceCode. Sie sendet nichts automatisch, startet kein OTA und lädt keine
Firmware. getDataByCode bleibt als Vorlage erhalten. Der generische Debugger
und seine unveränderte HTTP-404-Antwortdarstellung bleiben die Grundlage.

## SIM / LTE-Vertragsstatus

Manuelles Read-only-POST dtuIccId/getInfoByIccId mit dem vorhandenen
dtuIccid des aktuell ausgewählten Geräts. Die bestehende Haus-/Gerätediscovery
liefert dieses Feld; keine manuelle ICCID-Eingabe und kein 30-s-SIM-Poll.
Ohne ICCID wird kein Request gesendet. expireDays/expireTime und die optionalen
Zeitfelder werden roh angezeigt; unbekannte Status-Enums bleiben Rohwerte.

Die kompakte Statusanzeige zeigt die bekannten Vertrags-/Statusfelder. Zusätzlich
zeigt eine Rohdatentabelle im Debug-Tool alle vom SIM-Endpunkt gelieferten Felder
nach Entfernung echter Authentifizierungsgeheimnisse; Gerätekennungen und weitere
Cloud-Metadaten bleiben dort bewusst unmaskiert sichtbar. SIM-Rohdaten werden
weiterhin nicht automatisch geloggt oder in normale Cloud-Exporte übernommen.
Bekannte fremdsprachige Klartexte werden übersetzt und zusammen mit dem Original
angezeigt, z. B. "IoT-SIM-Karte (物联卡)".

Geräte-, Account- oder ICCID-Wechsel leert den Status und verwirft alte
Antworten und Tokens. Der manuelle Worker nutzt die vorhandenen Credentials,
WarmLinkCloudApi und den MAIN-Einzelread-Schließguard. Polling wird nicht
gestoppt. Es gibt keine SMS-, Zahlungs-, Coupon-, Bestell- oder Verlängerungsfunktion.
