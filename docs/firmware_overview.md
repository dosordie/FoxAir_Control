# Firmware-Übersicht

## V3.5: Warmlink-Remote-Regelung

V3.5 ergänzt die direkten MAIN-Exporte 1492, 1540 und 1557. MAIN:1430 gab es bereits zuvor; für V3.5 ist seine zusätzliche Verwendung als Gate des 8055-Pfads bestätigt.

MAIN:1540 ist ein persistentes uint8-Gate für die zusätzlichen Warmlink-Werte 8021–8028. Die Frequenz wird **nicht** auf 30/36/42/48 Hz quantisiert. Stattdessen nähert die Logik einen bisherigen Frequenzbefehl bei Bedarf in Schritten von höchstens 6 Hz an die Remote-/Adaptivreferenz an, ohne diese zu unterschreiten. Erst anschließend wird ein interner 6-Hz-Bin-Index berechnet. C02, C03 und dynamische Min-/Max-Grenzen bleiben wirksam.

MAIN:1557 exportiert den effektiven Heiz-Wassersollwert read-only als signed int16, RAW/10 °C. MAIN:1492 enthält High Byte (8055-Korrekturfaktor) und Low Byte (Hardware-Eingangsselector); beide Bytes und MAIN:1430 sind persistente Engineeringparameter.

AI Saving über SG01/MAIN:1334 = 4 gehört zum älteren Remote-Komplex 8001/8004/8006, 0x20016A54 und MAIN1691/1692, der bereits in V3.4 existiert. Es ist kein interner Setter `SG01=4 -> MAIN1540=1` bestätigt: **SG01=4 ist nicht MAIN1540=1**.
