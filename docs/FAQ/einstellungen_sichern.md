# Einstellungen vor einem Firmwareupdate sichern

Vor einem Mainboard-Firmwareupdate sollten die aktuellen Einstellungen gesichert werden.

Das ist besonders sinnvoll, wenn viele Parameter bereits an die eigene Anlage angepasst wurden.

## Mit FoxAir Control

FoxAir Control besitzt eine Backup-/Restore-Funktion für Parameter.

Empfehlung:

1. Wärmepumpe verbinden
2. aktuelle Parameter vollständig einlesen
3. Backup speichern
4. Firmwareupdate durchführen
5. Einstellungen nach dem Update vergleichen
6. nur bei Bedarf Werte gezielt wiederherstellen

> Nicht jedes Firmwareupdate besitzt exakt dieselben Parameter. Deshalb ein altes Backup nach einem Update nicht blind vollständig zurückschreiben.

Wichtige individuelle Einstellungen sollten zusätzlich dokumentiert werden.

MAIN:1017 ist ein Parameter mit ungeklärter Funktion und wird deshalb nicht
automatisch gesichert oder wiederhergestellt, auch aus alten Backup-Dateien.
Die frühere Bezeichnung „Logo-Auswahl“ war falsch; dafür ist MAIN:1026/H39 zuständig.
Die übrigen bestätigten Paketbereiche behalten ihre bisherige Backup-/Restore-Policy.
