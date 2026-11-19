# Fehlermeldungen – Übersicht und Hilfe

Hier findest du die bekannten Fehlermeldungen der FoxAir mit ihrer Bedeutung und ersten Prüfschritten. Die Liste wird an einer Stelle gepflegt, damit andere FAQ-Artikel nur noch hierher verweisen müssen.

**Hinweis:** Je nach Modell und Softwareversion können sich Meldungen und Schutzfunktionen unterscheiden. Manche Fehler sind genauer untersucht als andere. Angegebene Zeiten sind ungefähre Richtwerte.

## Fehlerübersicht

| Fehler / Anzeige | Bedeutung | Zuerst prüfen |
| --- | --- | --- |
| **E030** | Wasserdurchfluss beim Abtauen zu gering | Umwälzpumpe, Heizkreis, **D22** |
| **E032** | Durchflussschalter am Eingang **S3** meldet eine Störung | Tatsächlichen Durchfluss, Schalter und S3-Anschluss |
| **E035** | Berechneter Wasserdurchfluss zu gering | Umwälzpumpe, Pumpentyp **H31**, **A40** |
| **Externer Außentemperaturfühler** | Aktivierter Außenfühler fehlt oder liefert ungültige Werte | Fühler, Anschluss und **1463** |
| **P03** | Temperaturfühler am Warmwasserspeicher gestört | Speicherfühler und Anschluss |
| **P03a** | Temperaturfühler am Pufferspeicher gestört | Pufferfühler und Anschluss |
| **P42** | Raumtemperaturfühler gestört | Angeschlossenen Raumfühler prüfen |
| **P105 / P106** | Raumtemperaturfühler Zone 1 / 2 gestört | Fühler der betroffenen Zone |
| **P107** | Mischtemperaturfühler Zone 2 gestört | Fühler am gemischten Heizkreis |
| **E08g / E08h** | Kommunikationsfehler Thermostat Zone 1 / 2 | Thermostat und Verbindung der betroffenen Zone |
| **E04** | Übertemperaturstörung der elektrischen Zusatzheizung | Heizstab und Übertemperaturschutz |
| **E065** | Austrittswassertemperatur zu hoch | Wasserdurchfluss, Vor- und Rücklauftemperatur |
| **P182** | Heißgastemperatur zu hoch | Betriebswerte; bei Wiederholung Fachbetrieb |
| **Hochdruckschutz** | Druck im Kältekreis zu hoch | Luftweg, Lüfter, Heizwasserdurchfluss |
| **Niederdruckschutz** | Druck im Kältekreis zu niedrig | Luftweg, Vereisung; bei Wiederholung Fachbetrieb |
| **PP12** | Hochdrucksensor gestört | Sensor und Anschluss fachlich prüfen |
| **E103 / E203** | Lüftermotor 1 / 2 überlastet | Eis, blockierter Lüfter, Verschmutzung |
| **E08c** | Kommunikation mit Hydraulikmodul gestört | Falls vorhanden: Modul, Versorgung, Verbindung |
| **F151** | Kommunikation zwischen Verdichter- und Hauptsteuerung gestört | Verbindungen und Steuerung fachlich prüfen |
| **Kommunikationsfehler Display / Steuerplatine** | Display und Hauptsteuerung kommunizieren nicht richtig | Verbindung und Versorgung fachlich prüfen |
| **E19 / E29** | Primäre / sekundäre Frostschutzstörung | Wassertemperatur und Wasserumwälzung |

Die Übersicht enthält sowohl genau untersuchte Fehler als auch Meldungen, deren **Bezeichnung zuverlässig zugeordnet** ist. Wo genaue Grenzwerte oder Abschaltzeiten nicht bekannt sind, werden keine angenommen.

## Die Durchflussfehler im Detail

**E030, E032 und E035 sind unterschiedliche Überwachungen.** E032 gehört zum mechanischen Durchflussschalter **S3**. Bei E030 und E035 bewertet die Steuerung zusätzlich den Wasserdurchfluss.

| | **E030** | **E032** | **E035** |
| --- | --- | --- | --- |
| **Wann?** | Beim Abtauen | Bei Störung des Durchflussschalters S3 | Auch beim normalen Heizen möglich |
| **Grenze / Auslöser** | Durchfluss unter **D22** | Meldung des Schalters S3 | Berechneter Durchfluss unter etwa **50 % von A40** |
| **Bis zum Fehler** | Ungefähr **10 Sekunden** | Abhängig vom Betriebszustand | Ungefähr **6 Sekunden**, wenn die Überwachung aktiv ist; ansonsten möglicherweise länger |
| **Wirkung** | Verdichter beim Abtauen auf maximal **50 Hz** begrenzt | Verdichter kann gestoppt werden | Verdichter kann gestoppt werden |
| **Rücknahme** | Wenn wieder ausreichend Durchfluss vorhanden ist | Nach behobener Ursache in manchen Fällen nach ungefähr **3 Sekunden** | Normalerweise nach ungefähr **10 Sekunden** mit berechnetem Durchfluss **über 60 % von A40** |
| **Prüfen** | Pumpe, Ventile, Luft im Heizkreis, D22 | Echten Durchfluss, Pumpe, Schalter S3 | Pumpe, **H31**, **A40**, Durchflussanzeige |

**Beispiel E035:** Bei **A40 = 1,20 m³/h** beginnt der kritische Bereich unter ungefähr **0,60 m³/h**. Zur Rücknahme muss der berechnete Durchfluss normalerweise wieder **über 0,72 m³/h** steigen.

**D22 = 0** deaktiviert die spezielle E030-Durchflussprüfung. **E032 und E035 bleiben davon unberührt.** Einstellungen und Sicherheitseinrichtungen nicht verändern, um einen vorhandenen Durchflussfehler zu umgehen.

### Startet der Verdichter nach E032 oder E035 automatisch neu?

**Das ist möglich.** Sobald die Ursache behoben ist und die Fehlermeldung zurückgeht, kann die Wärmepumpe bei weiter bestehendem Wärmebedarf ohne manuelles Zurücksetzen wieder anlaufen. Weitere Schutzbedingungen können den Start verzögern oder verhindern.

Die oben genannten Sekundenwerte gelten für die ungefähre **Fehlerrücknahme**, **nicht** für den tatsächlichen Verdichterstart.

### Warum stimmen angezeigter und echter Durchfluss nicht immer überein?

Bei vielen FoxAir-Geräten wird der Durchfluss anhand der Pumpenrückmeldung berechnet, nicht direkt gemessen. Deshalb muss der eingestellte **Pumpentyp H31** stimmen. Den berechneten Wert zeigt **Register 2077 (T39)** an.

Ein plausibler Anzeigewert ersetzt keine Prüfung des echten Durchflusses. Bei unklaren Fehlern möglichst mit einem unabhängigen Messgerät vergleichen.

Mehr dazu: [Wasserdurchfluss und Pumpenbetriebsarten](wasserdurchfluss_pumpe.md) · [PWM-Rückmeldung und Wasserdurchfluss](pwm_durchflusskennlinien.md).

## Weitere bekannte Fehler im Detail

| Fehler / Anzeige | Was wissen wir dazu? | Was ist sinnvoll? |
| --- | --- | --- |
| **Externer Außentemperaturfühler** | Ist der externe Fühler über **1463** aktiviert, aber nicht vorhanden oder defekt, kann die FoxAir auf den **internen Außentemperaturfühler T04** zurückfallen und **weiterlaufen**, solange dieser gültig ist. | Prüfen, ob der Fühler richtig angeschlossen ist und 1463 zur Anlage passt. [Mehr zum Außenfühler](externer_at_fuehler.md). |
| **P03 / P03a – Speicherfühler** | P03 betrifft den Warmwasserspeicher, P03a den Pufferspeicher. Welche Betriebsarten beeinträchtigt werden, hängt von der Anlagenkonfiguration ab. | Temperaturanzeige, Fühler, Stecker und Leitung prüfen. [Mehr zu Speicherfühlern](speicherfuehler.md). |
| **P42 / P105 / P106 / P107** | P42 bezeichnet einen Raumtemperaturfühlerfehler; die weiteren Codes unterscheiden die Raumfühler von **Zone 1 und 2** sowie den Mischtemperaturfühler von **Zone 2**. | Anschlüsse und angezeigte Temperaturen der betroffenen Fühler prüfen. [Mehr zur Zonenregelung](zonenregelung.md). |
| **E04 – Zusatzheizung zu heiß** | Der Fehler gehört zur Übertemperaturüberwachung der elektrischen Zusatzheizung. Eine allgemein gültige Auslöseschwelle ist hier nicht gesichert. | Heizstab und Übertemperaturschutz durch eine Fachkraft überprüfen lassen. [Mehr zum Heizstab](heizstab.md). |
| **E065 – Austrittswasser zu heiß** | Die Wärmepumpe meldet eine zu hohe Wasseraustrittstemperatur. Die genaue Grenze kann je nach Ausführung abweichen. | Vor- und Rücklauftemperatur, Umwälzpumpe und Ventile prüfen. |
| **P182 – Heißgastemperatur zu hoch** | Die Meldung betrifft den Verdichterausgang. Normale Leistungsbegrenzungen wegen hoher Temperatur sind nicht automatisch dieselbe Fehlermeldung. | Betriebswerte beobachten; bei Wiederholung den Kältekreis fachlich prüfen lassen. |
| **Hochdruck- / Niederdruckschutz und PP12** | Hoch- und Niederdruckschutz melden einen unzulässigen Druckzustand. **PP12** steht dagegen für einen **Hochdrucksensorfehler** – das ist nicht dieselbe Meldung. Die genauen Auslösezeiten und Druckgrenzen sind hier nicht für alle Geräte gesichert. | Luftweg, Lüfter und Vereisung prüfen; bei Hochdruck auch den Heizwasserdurchfluss. Bei PP12 den Drucksensor fachlich prüfen lassen. |
| **E103 / E203 – Lüfterüberlast** | Betroffen ist Lüftermotor 1 bzw. 2. Ein Lüfterstillstand während des Abtauens allein ist **kein** Beweis für einen Fehler. | Lüfter auf Blockierungen, Eis und Fremdkörper prüfen. [Mehr zur Lüfterregelung](luefterregelung.md). |
| **E08c / E08g / E08h – Kommunikation** | E08c betrifft das optionale Hydraulikmodul; E08g und E08h die Kommunikation mit dem Thermostat der **Zone 1 bzw. 2**. | Nur bei entsprechender Ausstattung: Versorgung und Verbindung des betroffenen Geräts prüfen. |
| **F151 / Kommunikation Display–Steuerplatine** | F151 betrifft die Verbindung zur Verdichtersteuerung. Für das Display gibt es eine eigene Kommunikationsfehlermeldung. Der Text allein zeigt nicht zwingend, welches Bauteil die Ursache ist. | Bei wiederkehrender Meldung Verbindungen und Steuerung fachlich prüfen lassen. |
| **E19 / E29 – Frostschutz** | Zwei getrennt angezeigte Frostschutzstufen. Die jeweilige Wirkung hängt vom Betriebszustand ab. | Temperaturen und Wasserumwälzung prüfen. [Mehr zum Frostschutz](abtauen_frostschutz.md). |

## Was tun, wenn ein Fehler angezeigt wird?

1. **Fehlercode, Uhrzeit und Betriebsart notieren**, möglichst auch den genauen Text auf dem Display.
2. **Naheliegende Ursachen prüfen**: Läuft die Umwälzpumpe? Sind Ventile geöffnet? Ist der Luftweg frei? Sind Fühler angeschlossen?
3. **Prüfen, ob der Fehler noch aktiv ist.** Manche Meldungen verschwinden nach Beseitigung der Ursache automatisch.
4. **Wiederkehrende Störungen untersuchen lassen** und dazu möglichst die angezeigten Temperaturen und Betriebswerte festhalten.

Das Löschen des Fehlerspeichers beseitigt nicht die eigentliche Ursache. Schutzschalter und andere Sicherheitseinrichtungen niemals überbrücken.

[Fehler und Betriebszustände anzeigen](fehler_und_status.md) · [FoxAir Control – Diagnose](foxair_control_diagnose.md)

---

*Die Liste wird ergänzt, sobald zu weiteren Fehlern zuverlässige Einzelheiten bekannt sind. Die Zuordnung einer Fehlerbezeichnung bedeutet nicht automatisch, dass schon alle Auslöse- und Rückstellbedingungen geklärt sind.*
