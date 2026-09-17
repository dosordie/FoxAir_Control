# FW 3.4: externer Außentemperaturfühler

Diese Seite dokumentiert die in Firmware 3.4 beobachtete Auswahl und
Fehlerbehandlung des zusätzlichen Außentemperaturfühlers. Die physische
Klemmenzuordnung ist **noch nicht abschließend bestätigt**.

## Registerübersicht

| Register / Bit | Deutscher Name | English name | Bedeutung |
| --- | --- | --- | --- |
| 1463 | Externer Außentemperaturfühler | External outdoor temperature sensor | `0`: normaler/interner T04; `1`: externer AT-Fühler aktiv |
| 2033 | bestehende Benennung im Registerverzeichnis | existing name in register map | Roh-/Messwert des optionalen zweiten Fühlers; die bestehende Benennung bleibt unverändert |
| 2034 Bit 5 | Remote Heat/Cool / DIN2 | Remote Heat/Cool / DIN2 | digitaler Eingang; mögliche Doppelnutzung siehe unten |
| 2048 | Verwendete Außentemperatur | Outdoor temperature in use | von der Firmware nach Auswahl, Fallback und Aufbereitung tatsächlich verwendeter Wert |
| 2088 Bit 7 (`0x0080`) | Externer Außentemperaturfühler Fehler | External outdoor temperature sensor fault | externer Fühler fehlt oder liefert einen ungültigen Wert, während 1463 auf `1` steht |

## Auswahl und Fallback

Mit `1463 = 0` nutzt die Regelung den normalen/internen T04-Fühler. Mit
`1463 = 1` wird der neue externe AT-Eingang ausgewählt. Ist der externe
Messwert ungültig oder der Fühler offen beziehungsweise fehlerhaft, läuft die
Wärmepumpe weiter und fällt auf den normalen T04 zurück. Register `2048`
veröffentlicht die nach dieser Auswahl und Aufbereitung tatsächlich verwendete
Außentemperatur.

Im Test mit `1463 = 1` und offenem externem Eingang wurde `2033 = 409,1 °C`
beobachtet. Gleichzeitig war Register 2088 Bit 7 gesetzt. Die Wärmepumpe lief
normal weiter und verwendete über den Fallback den normalen AT-Fühler.

## Reverse Engineering: DIN2 / Hardwarepfad

Register 2034 Bit 5 bezeichnet den digitalen Eingang **Remote Heat/Cool /
DIN2**. Bei aktiviertem externem AT (`1463 = 1`) wird derselbe Hardwarepfad
offenbar analog als Temperaturfühler ausgewertet.

> **Status: Reverse Engineering / noch nicht abschließend bestätigt.**
> Insbesondere ist daraus derzeit keine gesicherte physische
> Klemmenzuordnung abzuleiten.
