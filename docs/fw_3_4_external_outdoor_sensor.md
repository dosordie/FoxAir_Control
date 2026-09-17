# FW 3.4: externer Außentemperaturfühler

Diese Seite dokumentiert die in Firmware 3.4 beobachtete Auswahl und
Fehlerbehandlung des zusätzlichen Außentemperaturfühlers. Die physische
Klemmenzuordnung ist **noch nicht abschließend bestätigt**.

## Registerübersicht

| Register / Bit | Deutscher Name | English name | Bedeutung |
| --- | --- | --- | --- |
| 1463 | Externer Außentemperaturfühler | External outdoor temperature sensor | `0`: normaler/interner T04; `1`: externer AT-Fühler aktiv |
| 2033 | bestehende Benennung im Registerverzeichnis | existing name in register map | Roh-/Messwert des optionalen zweiten Fühlers; die bestehende Benennung bleibt unverändert |
| 2034 Bit 5 | S06 Fernheizung/Kühlung | S06 Remote Heat-Cool | digitaler Eingang; DIN2 und eine mögliche Doppelnutzung sind nur Vermutungen, siehe unten |
| 2048 | Verwendete Außentemperatur | Outdoor temperature in use | von der Firmware nach Auswahl, Fallback und Aufbereitung tatsächlich verwendeter Wert |
| 2088 Bit 7 (`0x0080`) | Externer Außentemperaturfühler Fehler | External outdoor temperature sensor fault | externer Fühler fehlt oder liefert einen ungültigen Wert, während 1463 auf `1` steht |

## Auswahl und Fallback

Mit `1463 = 0` nutzt die Regelung den normalen/internen T04-Fühler. Mit
`1463 = 1` wird der neue externe AT-Eingang ausgewählt. Ist der externe
Messwert ungültig oder der Fühler offen beziehungsweise fehlerhaft, läuft die
Wärmepumpe weiter und fällt auf den normalen T04 zurück. Register `2048`
veröffentlicht die nach dieser Auswahl und Aufbereitung tatsächlich verwendete
Außentemperatur.

Im Test mit `1463 = 1` und offenem externem Eingang wurde in Register 2033 der
Mess-/Anzeigewert `409,1` beobachtet; seine Einheit ist für diesen Fehlerwert
nicht bestätigt. Gleichzeitig war Register 2088 Bit 7 gesetzt. Die Wärmepumpe lief
normal weiter und verwendete über den Fallback den normalen AT-Fühler.

## Reverse Engineering: DIN2 / Hardwarepfad

Register 2034 Bit 5 bezeichnet **S06 Fernheizung/Kühlung / Remote Heat-Cool**.
Die Zuordnung zu DIN2 und die Annahme, dass bei aktiviertem externem AT
(`1463 = 1`) derselbe Hardwarepfad analog als Temperaturfühler ausgewertet
wird, sind derzeit lediglich Vermutungen.

> **Status: Reverse Engineering / noch nicht abschließend bestätigt.**
> Weder die Bezeichnung DIN2 noch eine physische Klemmenzuordnung sind für
> diesen Zusammenhang derzeit gesichert.
