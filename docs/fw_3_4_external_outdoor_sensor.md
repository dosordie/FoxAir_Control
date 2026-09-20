# FW 3.4: externer Außentemperaturfühler

Diese Seite dokumentiert die in Firmware 3.4 beobachtete Auswahl und
Fehlerbehandlung des zusätzlichen Außentemperaturfühlers sowie die Verwendung
der lokalen und der ausgewählten effektiven Außentemperatur in einzelnen
Regelpfaden.

## Registerübersicht

| Register / Bit | Deutscher Name | English name | Bedeutung |
| --- | --- | --- | --- |
| 1463 | Externer Außentemperaturfühler | External outdoor temperature sensor | `0`: normaler/interner T04; `1`: externer AT-Fühler aktiv |
| 2033 | Optionaler zweiter Außentemperaturfühler | Optional second outdoor temperature sensor | Messwert von Analogkanal 23 an Klemme 3/4; gültige Werte sind in °C skaliert, der Offenwert `409,1` ist jedoch keine Temperatur |
| 2034 Bit 5 | S06 Fernheizung/Kühlung | S06 Remote Heat-Cool | digitaler Eingang; eine mögliche Doppelnutzung bleibt unbestätigt |
| 2048 | Verwendete Außentemperatur | Outdoor temperature in use | von der Firmware nach Auswahl, Fallback und Aufbereitung tatsächlich verwendeter Wert |
| 2088 Bit 7 (`0x0080`) | Externer Außentemperaturfühler Fehler | External outdoor temperature sensor fault | externer Fühler fehlt oder liefert einen ungültigen Wert, während 1463 auf `1` steht |

## Auswahl und Fallback

Mit `1463 = 0` nutzt die Regelung den normalen/internen T04-Fühler. Mit
`1463 = 1` wird der neue externe AT-Eingang ausgewählt. Ist der externe
Messwert ungültig oder der Fühler offen beziehungsweise fehlerhaft, läuft die
Wärmepumpe weiter und fällt auf den normalen T04 zurück. Register `2048`
veröffentlicht die nach dieser Auswahl und Aufbereitung tatsächlich verwendete
Außentemperatur.

Der Selector befindet sich im analysierten Firmwarepfad bei `0x080B8C02`.
Seine Auswahl ersetzt den lokalen T04 nicht global: Einige Regelpfade rufen
T04 weiterhin direkt auf und ignorieren dort den externen Sensor.

Im Test mit `1463 = 1` und offenem externem Eingang wurde in Register 2033 der
Rohwert `409,1` beobachtet. Gültige Messwerte des Registers sind zwar in °C
skaliert, dieser Offen-/Fehlerwert ist jedoch keine Temperatur. Gleichzeitig
war Register 2088 Bit 7 gesetzt. Die Wärmepumpe lief normal weiter und
verwendete über den Fallback den normalen AT-Fühler.

## AT-Quellen der untersuchten Regelpfade

„Effektive AT“ bezeichnet die über Register 1463 ausgewählte Temperatur mit
T04-Fallback. „Lokaler T04“ bezeichnet einen direkten Zugriff auf den lokalen
Fühler, bei dem die externe Auswahl ignoriert wird.

| Register / Funktion | verwendete Temperaturquelle | Erkenntnis |
| --- | --- | --- |
| 1049 / A31 | effektive AT | E-Heizer-Einschaltschwelle |
| 1231 / R45 | effektive AT | E-Heizer ohne Verzögerung; Rückschaltung mit ungefähr `+2,0 K` Hysterese |
| 1464 / 1465 | effektive AT | zeitqualifizierte Zustands-/Freigabelogik; Funktion weiter erforschen |
| 1167–1172 / R29–R34 | lokaler T04 | AT-abhängige Wassertemperaturbegrenzung |
| 1229 / R43 und 1230 / R44 | lokaler T04 | maximale Heiz-Solltemperatur abhängig von AT |
| 1233 / R60 | lokaler T04 | Kühl-Frequenzbegrenzung nach AT |
| 1356 / H42 | lokaler T04 | Freigabe der Gehäuse-/Wannenheizung; Abschaltung mit ungefähr `+2,0 K` Hysterese |
| 1437 / D30 | über H42 an lokalen T04 gekoppelt | Nachlauf der Gehäuse-/Wannenheizung nach dem Abtauen; vollständige Zustandslogik weiter erforschen |

## Hardwarepfad des externen Fühlers

Register 2033 wird aus Analogkanal 23 gebildet. Der externe Fühler ist physisch
an Klemme 3/4 angeschlossen. Ein offener Eingang liefert den besonderen Rohwert
`409,1`, der trotz der °C-Skalierung gültiger Messwerte nicht als Temperatur
interpretiert werden darf.

Register 2034 Bit 5 bezeichnet **S06 Fernheizung/Kühlung / Remote Heat-Cool**.
Eine früher erwogene Zuordnung des externen AT-Eingangs zu DIN2 ist durch die
Zuordnung von Analogkanal 23 zu Klemme 3/4 überholt. Eine mögliche weitere
elektrische Doppelnutzung ist nicht bestätigt.

> **Status: Reverse Engineering.** Die physische Zuordnung des externen
> AT-Fühlers zu Klemme 3/4 ist bestätigt; eine mögliche weitere Doppelnutzung
> bleibt zu erforschen.
