# Mainboard-Firmware V3.4 – Reverse Engineering

Stand: 2026-08-30

Diese Datei dokumentiert den statischen Vergleich der Mainboard-Firmware **V3.3** mit **V3.4** für die Softwarefamilie **82400644**. Die Aussagen stammen aus einem Binärvergleich und einer ARM/Thumb-Disassembly der beiden originalen OTA-Images. Wo die fachliche Bedeutung noch nicht vollständig geschlossen ist, ist dies ausdrücklich gekennzeichnet.

## Vertrauensstufen

- **bestätigt** – direkter Daten-/Codepfad im Binary geschlossen.
- **sehr wahrscheinlich** – Codepfad ist eindeutig, fachliche Benennung folgt aus Register-/Runtime-Zuordnung.
- **offen** – Struktur/Funktion ist sichtbar, einzelne Semantik oder externe Abbildung ist noch nicht geschlossen.

---

## 1. Identität und Layout

| Merkmal | V3.3 | V3.4 |
|---|---:|---:|
| Softwarefamilie | `82400644` | `82400644` |
| eingebettete Version | `0033` | `0034` |
| Hardwarekennung | `823003140000` | `823003140000` |
| Imagegröße | 287598 Byte | 289806 Byte |
| Differenz | – | +2208 Byte (`0x8A0`) |
| Initial Stack Pointer | `0x2000EB90` | `0x2000EB90` |
| Reset Handler | `0x080927D1` | `0x08093071` |
| APP-Basis | `0x08050000` | `0x08050000` |

V3.4 ist klar dieselbe Firmware-/Hardwarelinie wie V3.3. Ein großer Teil des späteren Codes ist lediglich um `+0x8A0` verschoben. Es handelt sich nicht um einen Plattformwechsel oder ein neues Flashlayout.

### OTA-/Flash-Kompatibilität

Statisch bestätigt:

- aktive Anwendung: `0x08050000`
- OTA-Staging: `0x080A1000`
- Promotion kopiert aus dem Stagingbereich nach `0x08050000`
- V3.3 enthält Größenprüfungen von `0x4B000` (307200 Byte) und in einem weiteren Pfad `0x48800` (296960 Byte)
- V3.4 mit 289806 Byte liegt unter beiden Grenzen
- bei 168 Byte OTA-Nutzdaten ergeben sich 1726 Blöcke; der letzte Block enthält 6 relevante Firmwarebytes
- die Integritätsprüfung arbeitet über die exakte Dateigröße und nicht über die aufgefüllte Transportblockgröße

V3.4-MD5 des untersuchten OTA-Images:

`149A586EDE6F035B385762EA48C71605`

---

## 2. Überblick V3.3 → V3.4

Die auffälligsten funktionalen Änderungen sind:

1. **Außentemperaturkurve und Leistungstimer können gleichzeitig wirken.**
2. **A34 / Kurbelgehäuse-/Ölsumpf-Vorheizung wurde deutlich überarbeitet.**
3. **Neue dreiphasige Eingangsstrom-Begrenzung** auf Basis des höchsten Stroms aus L1/L2/L3.
4. **SG-Ready/PV-State-Machine erweitert**, u. a. um zusätzliche Zustände 6/7/8 und eine sauberere Übergabe der Mode-4-Sollwertoffsets.
5. Die eigentliche Thermostatlogik der Kurbelgehäuseheizung wurde **nicht** geändert.

Die eigentliche Außentemperatur-Kurveninterpolation und große Teile der übrigen Regelung sind unverändert oder nur verschoben.

---

## 3. Außentemperaturkurve + Leistungstimer

**Status: bestätigt**

Der bekannte inoffizielle Hinweis, dass V3.4 die gleichzeitige Nutzung von Außentemperaturkurve und Leistungstimern erlaubt, lässt sich im Binary nachvollziehen.

### V3.3

V3.3 behandelt einen aktiven Timerpfad zu breit als Sollwert-Override. Vereinfacht:

```text
Timer aktiv
  -> Timer-Sollwertpfad
  -> normale Sollwert-/AT-Kurvenberechnung wird umgangen
```

Dadurch kann bereits ein Timer, der primär eine Leistungsgrenze setzen soll, die Außentemperaturkompensation verdrängen.

### V3.4

V3.4 trennt die Entscheidung stärker:

```text
Timer aktiv
  -> Leistungsvorgabe darf aktiv bleiben
  -> separater interner Merker entscheidet, ob auch ein Temperatur-Override gilt
  -> ohne Temperatur-Override bleibt die normale/AT-kompensierte Sollwertberechnung aktiv
```

Die eigentliche Interpolations-/Kurvenfunktion ist dabei nahezu unverändert. Geändert wurde die **Arbitration/Priorität davor**.

### Interne neue Felder

Im V3.4-Parameter-/Runtime-Pfad tauchen dafür neue Felder im hinteren Parameterblock auf. Ein früher rein rechnerisches Mapping auf „Register 1737“ ist **nicht als externes Modbusregister bestätigt**, weil die Firmware mehrere alternative/duplizierte Parameterabbildungen besitzt. Deshalb werden diese Felder vorerst nur als **interne V3.4-Arbitrationsfelder** dokumentiert.

**Nicht auf vermeintliche Register 1733/1737 schreiben.**

---

## 4. Kurbelgehäuseheizung: Thermostat unverändert

**Status: bestätigt**

Die physische Kurbelgehäuseheizung liegt weiterhin auf GPIOE Pin 15. Im Status wird sie über **Register 2019, Bit 11** gespiegelt.

Die Thermostathysterese ist in V3.3 und V3.4 identisch:

```text
interne korrigierte AT < 8,1 °C  -> Heizung EIN
interne korrigierte AT >= 10,0 °C -> Heizung AUS
8,1 ... 9,9 °C                    -> Zustand halten
```

Da die Temperatur in 0,1-°C-Schritten verarbeitet wird, bedeutet `< 8,1 °C` praktisch: **8,0 °C oder niedriger**.

Die oft live beobachteten ca. 8,2 °C sind daher keine hart codierte 8,2-°C-Grenze. Die Heizlogik verwendet einen intern korrigierten AT-Wert.

### AT-Kalibrierung / Register 1355

Der Parameterpfad von **Register 1355** lässt sich auf ein signed Kalibrierbyte zurückführen, das dem internen Außentemperaturwert zugeschlagen wird. Dieser Wert liegt in einem persistenten EEPROM-Block ab `0x0278`.

Damit ist für 1355 sehr wahrscheinlich:

- signed Temperaturkorrektur der Außentemperatur
- Auflösung sehr wahrscheinlich 0,1 K
- persistent

Beispiel:

```text
angezeigter/roher AT-Wert  8,2 °C
Kalibrierung                -0,2 K
interner Regelwert           8,0 °C
-> Kurbelgehäuseheizung EIN
```

Vor einer endgültigen Umbenennung in der Registertabelle sollte 1355 an realer Hardware **nur gelesen** und gegen den sichtbaren AT-Wert geprüft werden.

---

## 5. A34 – Kurbelgehäuse-/Ölsumpf-Vorheizzeit

Register **1064 / A34** ist laut Parameterabbildung `Crank Preheating Time`, Einheit Minuten. Die bisher beobachtete Einstellung war z. B. 5 min.

Wichtig: A34 ist **nicht** die 8,1/10,0-°C-Thermostathysterese. A34 entscheidet über eine zusätzliche **Kompressor-Startfreigabe/Vorheizanforderung**.

### 5.1 V3.3-Verhalten

**Status: bestätigt**

V3.3 besitzt einen relativ einfachen Vorheizpfad:

1. tatsächlichen GPIO-Ausgang der Kurbelgehäuseheizung prüfen
2. wenn Heizung EIN: Vorheiz-Flag setzen
3. einen 32-Bit-Zähler hochzählen
4. Zähler gegen `A34 * 120` vergleichen
5. nach Ablauf das Vorheiz-Flag löschen
6. das Vorheiz-Flag wird an anderer Stelle als Kompressor-Startblockade ausgewertet

Vereinfacht:

```text
Heizung physisch EIN
  -> preheat_pending = 1
  -> elapsed++

elapsed >= A34 * 120
  -> preheat_pending = 0
  -> Startfreigabe möglich
```

### Auffälligkeit V3.3

Der Zähler wird in diesem Pfad beim normalen Ausschalten der Heizung **nicht auf 0 zurückgesetzt**. Es wurden im Image keine weiteren normalen Reset-Schreibstellen auf diesen Zähler gefunden; ein Neustart/BSS-Init setzt ihn natürlich zurück.

Damit verhält sich A34 in V3.3 eher wie ein **kumulatives Vorheizguthaben seit Initialisierung/Boot** als wie „vor jedem Kompressorstart erneut A34 Minuten warten“.

Praktische Folge:

- nach Boardstart kann bereits bei relativ mildem Wetter, solange die Kurbelgehäuseheizung wegen der 8,1-°C-Schwelle läuft, A34-Heizzeit gesammelt werden
- nach einmal erfüllter A34-Zeit sind spätere Starts typischerweise nicht erneut um A34 verzögert

### 5.2 V3.4-Verhalten

**Status: bestätigt**

V3.4 ersetzt diesen einfachen Pfad durch eine eigene neue Routine bei ca. `0x08089D88` und einen kleinen Zustandsautomaten.

Die relevante Struktur enthält mindestens:

```text
+0  mode/state
+1  externer Sperr-/Resetmerker (genaue Semantik offen)
+2  Qualifizierungszähler
+3  weiterer Sperr-/Resetmerker (genaue Semantik offen)
+4  32-Bit Vorheiz-Zeitkonto
+8  berechnete Restzeit
```

### Qualifikation der Vorheizung

V3.4 startet die eigentliche A34-Vorheizphase erst, wenn folgende Bedingungen erfüllt sind:

1. **A34 != 0**
2. kein externer Sperr-/Resetmerker aktiv
3. korrigierte Außentemperatur **unter ca. -4,9 °C** **oder** AT-Sensorfehler
4. **Abgas-/Heißgastemperatur (Register 2053)** unter `5,1 °C`
5. physischer GPIO-Ausgang der Kurbelgehäuseheizung ist tatsächlich EIN
6. diese Bedingungen liegen **20 aufeinanderfolgende Regelzyklen** an

Danach geht der Zustand von 0 auf 1.

Bei einem Scheduler von nominal etwa 2 Hz wären 20 Zyklen ungefähr 10 Sekunden; die Zykluszeit ist noch nicht separat als feste 2 Hz bewiesen und sollte deshalb nur als Näherung verstanden werden.

### Zustand 1: Start blockiert / Vorheizung läuft

Sobald `mode == 1`:

```text
elapsed++
remaining = max(A34 - elapsed/120, 0)

wenn elapsed >= A34 * 120:
    mode = 2
```

Die Kompressor-Startfreigabe prüft diesen Zustand direkt: **mode == 1** führt in den Sperrpfad. Zustand 0 und Zustand 2 blockieren über diesen A34-Pfad nicht.

### Zustand 2: Vorheizung erfüllt

`mode == 2` bedeutet: A34-Vorheizanforderung erfüllt.

Auch in V3.4 bleibt das 32-Bit-Zeitkonto bei verschiedenen State-Resets erhalten. Daher ist A34 weiterhin keine klassische „bei jedem Takt neu A34 Minuten“-Wartezeit. Die Änderung betrifft vor allem **wann überhaupt Vorheizzeit als gültig anerkannt und der Start blockiert wird**.

### 5.3 Erwartete Änderung im Realbetrieb

**Sehr wahrscheinlich / aus der bestätigten Logik abgeleitet:**

#### Bei mild-kaltem Wetter, z. B. +8 ... 0 °C

Die Kurbelgehäuseheizung kann durch ihre normale 8,1/10,0-°C-Hysterese EIN sein.

- **V3.3:** diese Heizzeit konnte bereits A34-Vorheizzeit sammeln bzw. nach Boardstart eine A34-Sperre erzeugen.
- **V3.4:** die spezielle A34-Startvorheizung wird bei gültigem AT-Sensor erst unter ungefähr -5 °C qualifiziert. Bei +8 ... 0 °C läuft zwar ggf. die Heizung, aber die A34-Sonder-Startblockade wird dadurch nicht automatisch scharf.

Erwartung: **weniger unnötige Startverzögerungen bei nur mäßig kalter Außentemperatur.**

#### Bei echtem Kaltstart unter ca. -5 °C

V3.4 prüft zusätzlich:

- Kompressor/Heißgas tatsächlich kalt (`2053 < 5,1 °C`)
- Heizungs-GPIO physisch EIN
- stabile Bedingung über 20 Zyklen
- Sensorfehler-Fallback

Erwartung: **robustere Vorheizabsicherung eines wirklich kalten Kompressors** und weniger falsches „Vorheizen erledigt“, nur weil irgendwann einmal ein Heizsignal vorhanden war.

#### Nach bereits absolvierter Vorheizung

Das Zeitkonto wird nicht bei jedem normalen Kompressorstopp gelöscht. A34 wirkt daher eher wie eine **Cold-start-/Power-up-Schutzlogik mit Heizguthaben** und nicht wie eine Verzögerung vor jedem Verdichterstart.

### Noch offen bei A34

- genaue fachliche Bedeutung der beiden internen Sperrbytes `state+1` und `state+3`
- exakte externe Anzeige/Abbildung der berechneten Restzeit `state+8`
- exakte Scheduler-Periode der 120 Ticks/min in diesem Pfad

---

## 6. Neue dreiphasige Eingangsstrom-Begrenzung

**Status: Funktion bestätigt; externer Einstellparameter noch nicht sicher gemappt**

V3.4 enthält eine neue kleine Funktion bei ca. `0x08089D6C`, die das Maximum aus drei 16-Bit-Werten bildet. Die drei Eingänge lassen sich auf die bekannten Statuswerte zurückführen:

- **2029 – Eingangsstrom L1**
- **2030 – Eingangsstrom L2**
- **2031 – Eingangsstrom L3**

Damit arbeitet V3.4 auf dem **höchsten Phasenstrom**.

### Aktivierung

Ein neuer interner Grenzwert wird geprüft. Ist dieser Wert `0`, wird der neue Regler deaktiviert und sein Zustand zurückgesetzt.

Der Grenzwert stammt aus einem neuen Feld im hinteren V3.4-Parameterblock. Eine externe Modbusadresse ist noch **nicht sicher bestätigt**. Er ist außerdem **nicht identisch mit A39 / Register 1343 „Maximaler Stromwert“**, dessen Pfad an anderer Stelle liegt.

### Hysterese

Für `Imax = max(L1, L2, L3)` wird sinngemäß entschieden:

```text
Imax >= Limit - 10  -> Zustand 2
Imax >= Limit - 15  -> Zustand 1
Imax <  Limit - 20  -> Zustand 0
sonst                -> bisherigen Zustand halten
```

Die Werte 10/15/20 sind sicher als Rohdifferenzen im Code vorhanden. Die exakte physikalische Skalierung dieses neuen Grenzwertfeldes ist noch nicht separat geschlossen. Falls derselbe Rohmaßstab wie bei den Phasenstromwerten verwendet wird, ergeben sich entsprechende Stromhysteresen; dies sollte live verifiziert werden.

### Zustand 1 – Soft Cap

Zustand 1 wird in der Frequenzregelung ausgewertet und verhindert bzw. begrenzt eine weitere Anhebung der zulässigen Kompressorfrequenz. Der Pfad setzt außerdem einen internen Limiterstatus.

Interpretation: **Strom nähert sich dem Grenzwert → nicht weiter hochmodulieren.**

### Zustand 2 – aktive Rückregelung

Zustand 2 wirkt stärker:

- beim Eintritt wird ein Regelzähler initialisiert
- im nachfolgenden Frequenzpfad wird die zulässige Kompressorfrequenz um **5 Hz** reduziert
- bleibt Zustand 2 bestehen, erfolgt nach jeweils ca. 20 Regelzyklen eine weitere 5-Hz-Reduktion
- die Frequenz wird nicht unter die bereits vorhandene Mindestgrenze gedrückt

Interpretation:

```text
höchster Phasenstrom zu hoch
  -> Kompressorfrequenz aktiv in 5-Hz-Schritten reduzieren
  -> bis Strom wieder im Hysteresebereich liegt oder Min.-Frequenz erreicht ist
```

### Bedeutung im Realbetrieb

Sehr wahrscheinlich handelt es sich um einen neuen **Soft Current Limiter für dreiphasige Geräte**:

- berücksichtigt die am stärksten belastete Phase statt nur eines Summen-/Einphasenwerts
- verhindert weitere Leistungssteigerung nahe dem Grenzwert
- regelt bei stärkerer Überschreitung aktiv in 5-Hz-Schritten zurück
- kann Netzanschluss, Sicherung/Leitung und Inverter vor dauerhaft zu hohem Eingangsstrom schützen

Die Funktion ist deutlich mehr als ein Alarm: sie greift aktiv in die Kompressorfrequenz ein.

### Noch offen

- sichere externe Adresse und Einheit des neuen Grenzwerts
- extern sichtbare Zuordnung des internen Limiterstatus; ein Statusbit `0x0400` wird intern gesetzt, die endgültige 2xxx-Abbildung ist noch offen
- Liveverhalten und reale Hysterese in Ampere

---

## 7. SG Ready / PV-State-Machine erweitert

**Status: Zuordnung bestätigt; einzelne neue Übergänge noch nicht vollständig fachlich benannt**

Ein großer, gegenüber V3.3 deutlich erweiterter Funktionsblock gehört zur **SG-Ready-/PV-Logik**. Die Runtime-Struktur wird aus den bekannten SG-Parametern gespeist:

- 1334 / SG01 – SG Ready Auswahl
- 1335 / SG02 – Mode-1 Schlafzeit
- 1336 / SG03 – Mode-2 Leistung / wenig PV
- 1337 / SG04 – Mode-3 Leistung / mittel PV
- 1338 / SG05 – Mode-4 WW-Sollwertanhebung
- 1339 / SG06 – Mode-4 Heiz-Sollwertanhebung
- 1340 / SG07 – Mode-4 Kühl-Sollwertanhebung
- 1341 / SG08 – E-Heizer in Mode 4

V3.4 kennt in dieser State-Machine zusätzliche interne Zustände **6, 7 und 8**.

### Nachgeschaltete Wirkung

Der nachfolgende Sollwertpfad zeigt eindeutig:

- WW-Offset wird addiert
- Heiz-Offset wird addiert
- Kühl-Offset wird abgezogen

Das entspricht exakt der bekannten SG-Mode-4-Semantik.

Die neuen Zustände 6/7/8 gehören damit zu zusätzlichen SG-Eingangs-/Auswahlkombinationen und zum High-PV-/Sollwert-Offsetpfad, nicht zum neuen Strombegrenzer.

### Weitere Auffälligkeit

Bei bestimmten Zustandswechseln wird ein interner Timer mit `0x4B0 = 1200` Ticks initialisiert. Bei nominal 2 Hz entspräche dies etwa 10 Minuten; die genaue Schedulerperiode muss noch separat bestätigt werden.

### Bedeutung im Realbetrieb

V3.4 behandelt mehr SG-Auswahl-/Kontaktkombinationen explizit und kann die drei Mode-4-Sollwertänderungen sauber als gemeinsame Zustandsausgabe anwenden. Das sieht nach einer Erweiterung/Robustheitsverbesserung der SG/PV-Arbitration aus.

Dies ist eine zusätzlich im Binary gefundene Änderung; sie ist **nicht** mit dem bekannten inoffiziellen V3.3→V3.4-Changelogpunkt „AT-Kurve + Leistungstimer“ gleichzusetzen.

---

## 8. Was sich nicht geändert hat

Folgende Bereiche sind zwischen V3.3 und V3.4 nach aktuellem Stand unverändert oder funktional gleich:

- Hardware-/Softwarefamilie
- APP- und OTA-Flashlayout
- grundlegende Cortex-M-Vektortabelle/Startupstruktur
- Kurbelgehäuseheizungs-Thermostat mit 8,1/10,0-°C-Hysterese
- eigentliche Außentemperatur-Kurveninterpolation
- große Teile der bestehenden Regelungs-/Modbuslogik

V3.4 wirkt daher wie ein gezieltes Wartungs-/Regelungsupdate und nicht wie eine Neuentwicklung.

---

## 9. Sinnvolle Live-Tests nach einem V3.4-Update

Nur lesende Tests, solange neue Parameterfelder nicht sicher gemappt sind:

1. **Version prüfen**
   - 2104 sollte `34` liefern
   - 2105 sollte bei `644` bleiben

2. **Kurbelgehäuseheizung beobachten**
   - 2019 Bit 11
   - 2048 Außentemperatur
   - 2053 Abgas-/Heißgastemperatur
   - 1064 A34
   - 1355 nur lesen und gegen AT-Korrektur prüfen

3. **A34-Kaltstart prüfen**
   - besonders interessant: Board-/Anlagenstart bei AT knapp oberhalb und unterhalb ca. -5 °C
   - prüfen, ob bei milden Temperaturen keine A34-Startblockade mehr auftritt
   - bei echtem Frost Vorheizdauer und Startfreigabe protokollieren

4. **Neue Strombegrenzung**
   - 2029/2030/2031 loggen
   - parallel Kompressor-Soll-/Istfrequenz beobachten
   - nach einem extern sichtbaren Statuswechsel suchen, wenn eine Phase den Grenzbereich erreicht

5. **AT-Kurve + Leistungstimer**
   - Leistungstimer aktivieren, aber keinen Temperatur-Override erzwingen
   - prüfen, ob 2013/2014/2016 weiterhin der wetterkompensierten Sollwertbildung folgen

### Sicherheitsnotiz

Die neuen hinteren internen V3.4-Parameterfelder sind noch nicht als eindeutige externe Modbusregister verifiziert. Bis zur geschlossenen Mappingkette dort **keine Schreibversuche** durchführen.

---

## 10. Offene Punkte für weitere Analyse

- externe Modbusadresse/Skalierung des neuen dreiphasigen Stromlimits
- externes Statusregister des Strombegrenzers (`0x0400` interner Statusmerker)
- genaue Bedeutung der beiden A34-Sperr-/Resetbytes
- externe Anzeige/Abbildung der A34-Restzeit
- vollständige fachliche Benennung der neuen SG-Zustände 6/7/8 pro Eingangskombination
- Livebestätigung von Register 1355 als signed AT-Korrekturwert

Diese Punkte sollten bei neuen Logs/Live-Messungen weiter geschlossen werden.