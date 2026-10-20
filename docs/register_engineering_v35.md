# GL9 V3.5: Engineering-Korrekturen und Heizsollwertstatus

Grundlage ist die abgeschlossene Mainboard-Firmwareanalyse V3.5 aus dem
übermittelten Registertext. Es wurde keine neue Firmwareanalyse durchgeführt.
Die Aussagen gelten für den untersuchten direkten User-/Mainboard-Modbus.
Daraus folgen keine neuen Cloud-Mappings, Display-Adressen oder Regelungs-UIs.

## Engineering-RAM-Fenster

`ENG:CTRL:8801–8820`, RAM-Basis `0x20016980`, unterstützt FC03, FC06 und FC16.
8801 und die vorhandene virtuelle SG-/PV-Steuerung bleiben unverändert.

| Register | Name | RAM-Adresse | Darstellung |
|---|---|---|---|
| 8802 | Additiver Warmwasser-Sollwertoffset | 0x20016982 | signed int16 / 10 °C |
| 8803 | Additiver Heiz-Wassersollwertoffset | 0x20016984 | signed int16 / 10 °C |
| 8804 | Subtraktive Kühl-Sollwertkorrektur | 0x20016986 | signed int16 / 10 °C |
| 8805 | Korrekturwert für Zonenregelung A | 0x20016988 | signed int16, Einheit offen |
| 8806 | Korrekturwert für Zonenregelung B | 0x2001698A | signed int16, Einheit offen |
| 8807 | Engineering-Korrekturwert 8807 (Reserve V3.5) | 0x2001698C | signed int16 RAW, Bedeutung/Einheit/Skalierung offen |
| 8808 | Engineering-Korrekturwert 8808 (Reserve V3.5) | 0x2001698E | signed int16 RAW, Bedeutung/Einheit/Skalierung offen |

Alle sieben Einträge verwenden die bestehende Engineering-Sichtbarkeit und sind
standardmäßig aus der normalen Parameteransicht ausgeblendet. Sie bleiben im
technischen Offline-Registerbrowser auffindbar. Es gibt keine erfundenen
Herstellergrenzen oder Defaults. Signed-Werte werden als Zweierkomplement
kodiert; Temperaturformate und Signed-Decoding verwenden die vorhandenen Pfade.

Die Werte sind Runtime-/RAM-Steuerregister, keine normalen persistenten
Benutzerparameter. Im untersuchten direkten FC06-/FC16-Schreibpfad ist kein
EEPROM-/Flash-Schreibaufruf nachgewiesen. Das beweist nicht, dass das gesamte
System unter allen Umständen niemals einen dieser Werte persistiert. Eine
Wiederherstellung nach Neustart ist nicht garantiert; Werte bei Bedarf erneut
initialisieren. Für Einzeländerungen FC06 bevorzugen; keine unvalidierten
größeren Blockschreibvorgänge. Der bestehende Backend-Schreibpfad bleibt erhalten.

## Auswahl der Korrekturquelle

MAIN:1334 selektiert zuerst; MAIN:1540 wird erst im verbleibenden Zweig geprüft.

| MAIN:1334 | MAIN:1540 | Korrektursatz |
|---|---|---|
| 0 | 0 | Engineering 8802–8808 |
| 0 | !=0 | Warmlink 8024–8028 plus Engineering 8807/8808 |
| 1, 2, 3, 5, 6, 7 | beliebig | SG-Korrektursatz |
| 4 | beliebig | AI-Saving-/Remote-Korrektursatz |
| Andere, nicht vorgesehene Werte | 0 bzw. !=0 | Derselbe Auswahlzweig wie bei 1334=0; keine Empfehlung als zulässige Betriebsmodi |

8803 wirkt regulär nur bei **1334=0 und 1540=0** additiv auf den berechneten
Heizsollwert. Bei **1334=7**, auch mit **8801=2 (Neutral)**, bleibt 8803 unwirksam;
bei **1334=4** ebenfalls. Bei 1334=0 und 1540!=0 ersetzt Warmlink **8025** den
8803-Heizoffset. Die Heizkurve/Außentemperaturführung verhindert seine Verwendung
grundsätzlich nicht; anschließend gelten die normalen **R10-/R11-Grenzen**.
8803 ist kein universeller Heizsollwert-Eingang.

8805 führt über `0x20016CE0 +0x0A` zu Zone A `0x2001606C +0x9E`, 8806 über
`0x20016CE0 +0x0C` zu Zone B `0x20016110 +0x9E`. Die Zonenregelung addiert oder
subtrahiert das Feld abhängig von Regelrichtung/Betriebsart. Herstellername und
endgültig belegte Einheit bleiben offen. Bei 1334=0 und 1540!=0 werden stattdessen
8027/8028 verwendet.

8807/8808 addieren auf die Arbeitsfelder `0x20016CE0 +0x06/+0x08` im nicht durch
SG/AI abgefangenen Zweig sowohl mit 1540=0 als auch 1540!=0. Bei 1334=7 werden
auch diese Korrekturen im untersuchten Auswahlpfad übersprungen. Ihre fachliche
Bedeutung ist nicht ausreichend belegt; deshalb neutrale technische Namen.

## Virtueller SG-/PV-Pfad bei 1334=7

| 8801 | Interner State | MAIN:2133 | Funktion |
|---|---|---|---|
| 1 | 6 | 1 | Low PV / Leistungsbegrenzung |
| 2 | 7 | 2 | Neutral |
| 3 | 8 | 3 | High PV / Sollwertanhebungen |

Heizkorrektur: `MAIN:1339 / SG06 → 0x20016CD0 +0x0A → 0x20016972`
(vorbereitet) `→ 0x2001696C` (bei High PV aktiv) `→ 0x20016CE0 +0x02`.
Neutral setzt den aktiven Heizoffset auf null.

Die internen RAM-Felder 0x20016972/0x2001696C haben keinen nachgewiesenen gültigen
direkten User-Modbus-Alias. Rechnerische Adressen **8794 und 8791 sind ungültig**,
da das Engineering-Fenster erst bei 8801 beginnt. Es gibt keinen bestätigten
User-Modbus-Weg für einen unabhängigen dynamischen Heizoffset analog 8803 bei
1334=7. Normale MAIN-Parameter wie **1158/R02** und **1339/SG06** gehören zur
persistenten Konfigurationslogik; häufiges zyklisches Schreiben ist nicht als
verschleißfrei belegt. 1339 ist kein bestätigter EEPROM-freier Runtime-Ersatz.

## Statusregister und Korrektur des falschen Alias

| Register | Quelle in V3.5 | Aussage |
|---|---|---|
| 2013 | 0x200164C8 +0x06 | Gesondert aufbereiteter interner Regelsollwert; weitergehende Regelstufe/Begrenzungssemantik offen |
| 2014 | 0x200164C8 +0x56 | Betriebsabhängig ausgewählter Heiz-, Warmwasser- oder Kühlsolltemperaturwert |
| 2016 | 0x200164C8 +0x56 | Echter Spiegel von 2014; nicht pauschal identisch mit 2013 |
| 2017 | Getter 0x0808261C | Effektiver berechneter Heiz-Wassersollwert, V3.5+, read-only FC03, TEMP1 signed int16 / 10 °C |

2017 enthält wirksame Regelkorrekturen, Heizkurven-/Timerpfade und die normale
Heiztemperaturbegrenzung. Der Getter berechnet den Heizsollwert unabhängig davon,
ob Heizen gerade aktiv ist. Der Wert ist nicht in jeder Betriebsart zwingend der
aktuell aktive Vorlaufsollwert. In V3.3 war 2017 reserviert/unbenutzt.

Der Statuspuffer liegt bei `0x20012790`, sein Offset berechnet sich als
`0x820 + 2*(Register - 2001)`: für 2017 genau **+0x840**. Die frühere Deutung
als **MAIN:1557 war falsch**. FC03-Normalparameter enden im untersuchten direkten
V3.5-Dispatcher bei 1540 (1001–1540), der Statusbereich ist 2001–2180.
1557 ist dort kein gültiger Export und aus Registerkatalog und gebündelter
Knowledge-Datei entfernt; kein paralleler Alias. Bestehende Namen von 2013/2014
bleiben erhalten; 2016 verliert lediglich den irreführenden Verweis auf 2013.

## Ausgewertete Firmwarebelege

| Codeadresse (V3.5) | Nachweis |
|---|---|
| 0x08066664–0x08066680 | FC03-Normalparameterbereich endet bei 1540 |
| 0x080666C2–0x08066706 | FC03-Statusbereich 2001–2180 und Adressberechnung |
| 0x080668A0–0x080668E8 | Engineering-Fenster FC03 |
| 0x08066DAE–0x08066DEC | Engineering FC06 |
| 0x0806736C–0x080673B4 | Engineering FC16 |
| 0x0806C504–0x0806C558 | Statuswerte 2013–2017 |
| 0x08082592 / 0x0808261C | Interne Heizsollwert-Getter / Getter für 2017 |
| 0x080827F4–0x080827FE | SG06 in vorbereiteten SG-RAM-Wert übernehmen |
| 0x08082F5C–0x08082F96 | Neutral und Rücksetzen des SG-Heizoffsets |
| 0x08082F98–0x08082FDE | High PV und Aktivierung der SG-Korrekturen |
| 0x08089E60–0x0808A046 | Auswahl und Anwendung der Korrektursätze |

Vom Auftrag übermittelte Referenz: `dosordie/FoxAir_private`,
`docs/reverse_engineering/firmware/V3.5/disassembly/chunks/`, Chunks
0027, 0028, 0034, 0040, 0061 und 0070. Das private Repository wurde für diesen
Auftrag weder untersucht noch geändert. Die Registerintegration ist automatisiert
mit synthetischen Modbus-Werten geprüft; ein neuer Hardware-Livetest erfolgte nicht.
