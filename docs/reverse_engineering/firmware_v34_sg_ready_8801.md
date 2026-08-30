# Mainboard-Firmware V3.4 – SG Ready / virtuelles Register 8801

Stand: 2026-08-30

Diese Notiz ergänzt `firmware_v34.md` um die inzwischen geschlossene Zuordnung des virtuellen SG-Eingangs **Register 8801** und der in V3.4 erweiterten SG-State-Machine.

## Kurzfazit

- **Register 8801 ist direkt als virtueller SG-Eingang im Mainboard-Code bestätigt.**
- 8801 selbst ist **nicht neu in V3.4**; der klassische virtuelle 4-Zustands-SG-Ready-Pfad existiert bereits in V3.3.
- V3.4 ergänzt zusätzlich eine zweite, reduzierte **3-Zustands-SG/PV-Familie**.
- Diese zweite Familie verwendet die bisher in der Oberfläche nicht dokumentierten Auswahlwerte **SG01 = 5, 6, 7**.
- **SG01 = 7** ist dabei der virtuelle Modbus-Pfad und verwendet wiederum **Register 8801**.
- Die Herstellerbezeichnung der neuen 5/6/7-Familie ist im Mainboard-Binary nicht als Text enthalten. Funktional verhält sie sich wie ein vereinfachter PV/SG-Modus ohne klassischen Sperrzustand und ohne mittlere PV-Stufe.

> Sicherheitsnotiz: Die Werte 5/6/7 sind statisch aus dem V3.4-Code dekodiert, aber derzeit nicht als reguläre Bedienwerte in der FoxAir-Control-Registertabelle freigegeben. Vor einem kontrollierten Live-Test **nicht auf SG01/1334 schreiben**.

---

## 1. Register 8801 im Modbus-Parser

Der V3.4-Modbus-Parser besitzt einen eigenen Bereich:

```text
0x2261 <= Adresse < 0x2275
```

Das entspricht dezimal:

```text
8801 ... 8820
```

Das erste Wort des zugehörigen RAM-Blocks liegt bei `0x20016970`. Genau diese Adresse wird von der SG-Routine als 16-Bit-Wert gelesen.

Damit ist die Kette geschlossen:

```text
Modbus Register 8801
        ↓
RAM 0x20016970
        ↓
SG-State-Machine
```

---

## 2. SG01 / Register 1334 ist der Quellenauswahlschalter

Die Parameterabbildung lässt sich mit dem realen 1xxx-Modbus-Parser schließen:

```text
Register 1001 -> Parameterarray + 0x3E8
jedes weitere Register -> +2 Byte
```

Für SG01:

```text
0x3E8 + 2 * (1334 - 1001) = 0x682
```

Die SG-Routine übernimmt aus diesem Offset den 16-Bit-Auswahlwert. Die folgenden Wörter sind ebenfalls eindeutig:

| Register | SG-Code | Funktion |
|---:|---|---|
| 1334 | SG01 | SG-Auswahl / Eingangsart |
| 1335 | SG02 | Mode-1 Schlaf-/Sperrzeit |
| 1336 | SG03 | Mode-2 Leistungswert / wenig PV |
| 1337 | SG04 | Mode-3 Leistungswert / mittel PV |
| 1338 | SG05 | Mode-4 WW-Sollwertoffset |
| 1339 | SG06 | Mode-4 Heiz-Sollwertoffset |
| 1340 | SG07 | Mode-4 Kühl-Sollwertoffset |
| 1341 | SG08 | E-Heizer-Freigabe in Mode 4 |

---

## 3. Klassisches SG Ready – SG01 = 1 / 2 / 3

Die bereits bekannte Auswahlfamilie bleibt erhalten:

```text
SG01 = 1  -> ein physischer SG-Kontakt
SG01 = 2  -> zwei physische SG-Kontakte
SG01 = 3  -> virtuelle Kontakte über Modbus 8801
```

### SG01 = 3: vollständige 8801-Zuordnung

V3.4 dekodiert Register 8801 so:

| 8801 | virtueller Kontakt 1 | virtueller Kontakt 2 | interner SG-Zustand |
|---:|---:|---:|---:|
| 1 | 1 | 0 | 1 |
| 2 | 0 | 0 | 2 |
| 3 | 0 | 1 | 3 |
| 4 | 1 | 1 | 4 |

Damit ist für den klassischen virtuellen SG-Ready-Modus:

```text
SG01 = 3
8801 = 1 -> Zustand 1
8801 = 2 -> Zustand 2
8801 = 3 -> Zustand 3
8801 = 4 -> Zustand 4
```

### Wirkung der Zustände 1 ... 4

Aus der nachgeschalteten V3.4-Ausgabe:

- **Zustand 1:** Sperr-/Schlafpfad; eigener Zeitpfad über SG02.
- **Zustand 2:** verwendet **SG03 / Register 1336** als Leistungswert.
- **Zustand 3:** verwendet **SG04 / Register 1337** als Leistungswert.
- **Zustand 4:** aktiviert den High-PV-/Sollwertoffsetpfad:
  - WW: `Soll += SG05 / 1338`
  - Heizen: `Soll += SG06 / 1339`
  - Kühlen: `Soll -= SG07 / 1340`
  - SG08 / 1341 ist dem E-Heizer-/Mode-4-Pfad zugeordnet.

Dieser klassische 8801-Pfad ist grundsätzlich bereits in V3.3 vorhanden.

---

## 4. Neu in V3.4: zweite SG/PV-Auswahlfamilie 5 / 6 / 7

V3.4 prüft in derselben SG-State-Machine zusätzlich explizit die SG01-Werte **5, 6 und 7**.

Die Struktur ist parallel zur alten Familie:

| SG01 | Eingangsart | erzeugte Zustände |
|---:|---|---|
| 5 | ein physischer Kontakt | 7 / 8 |
| 6 | zwei physische Kontakte | 6 / 7 / 8 |
| 7 | virtueller Modbus-Eingang über 8801 | 6 / 7 / 8 |

Damit ergibt sich sehr deutlich die Paarung:

```text
1 <-> 5   ein Kontakt
2 <-> 6   zwei Kontakte
3 <-> 7   virtuell über 8801
```

Die Werte 5/6/7 sind im V3.4-Code reale SG01-Auswahlwerte und keine bloßen internen State-Nummern.

### SG01 = 5 – vereinfachter Ein-Kontakt-Modus

```text
Kontakt = 0 -> Zustand 7
Kontakt = 1 -> Zustand 8
```

### SG01 = 6 – vereinfachter Zwei-Kontakt-Modus

```text
Kontakt 1 = 1            -> Zustand 6
Kontakt 1 = 0, Kontakt 2 = 0 -> Zustand 7
Kontakt 1 = 0, Kontakt 2 = 1 -> Zustand 8
```

### SG01 = 7 – virtueller vereinfachter Modus über 8801

V3.4 dekodiert hier dasselbe Register 8801 in einer zweiten Semantik:

| SG01 | 8801 | interner Zustand |
|---:|---:|---:|
| 7 | 1 | 6 |
| 7 | 2 | 7 |
| 7 | 3 | 8 |

Für `8801 = 4` gibt es in diesem neuen SG01=7-Zweig keine entsprechend saubere explizite Zuordnung; dieser Wert sollte deshalb **nicht verwendet werden**.

---

## 5. Bedeutung der neuen Zustände 6 / 7 / 8

Die Ausgangsseite ist inzwischen klar:

### Zustand 6 – niedrige Leistung / wenig PV

Zustand 6 übernimmt denselben Leistungsparameter wie der klassische Zustand 2:

```text
Leistung = SG03 / Register 1336
WW-/Heiz-/Kühl-Offsets = 0
```

### Zustand 7 – neutral

Zustand 7 setzt die SG-Leistungs-/Temperaturoverrides auf neutral/0.

```text
keine SG-Sollwertoffsets
kein High-PV-Offsetpfad
```

### Zustand 8 – High PV / thermische Speicherung

Zustand 8 benutzt denselben Offsetpfad wie der klassische Zustand 4:

```text
WW-Soll       += SG05 / 1338
Heiz-Soll     += SG06 / 1339
Kühl-Soll     -= SG07 / 1340
```

Der Mode-4-/High-PV-Merker wird dabei ebenfalls gesetzt.

### Interpretation

Die neue Familie 5/6/7 bildet damit funktional einen reduzierten Dreizustandsmodus:

```text
Zustand 6 -> wenig PV / Leistungsbegrenzung
Zustand 7 -> neutraler Normalbetrieb
Zustand 8 -> viel PV / Sollwertanhebung bzw. thermische Speicherung
```

Im Gegensatz zum klassischen 4-Zustands-SG-Ready fehlen hier als eigene Zustände:

- der klassische harte Sperr-/Schlafzustand 1
- die mittlere Leistungs-/PV-Stufe 3

Das passt funktional sehr gut zu einer vereinfachten **PV-/SG-Funktion**. Die exakte Herstellerbezeichnung für SG01=5/6/7 bleibt jedoch noch offen.

---

## 6. Zustandswechsel / Verzögerung

Bei zahlreichen SG-Zustandswechseln setzt die Firmware einen internen Timer auf:

```text
0x4B0 = 1200 Ticks
```

Die genaue Schedulerperiode dieses Pfads ist noch nicht ausreichend geschlossen. Daher wird daraus derzeit **keine feste Minutenangabe** abgeleitet.

---

## 7. Was ist gegenüber V3.3 tatsächlich neu?

Wichtig für das V3.3 -> V3.4-Changelog:

**Nicht neu:**

```text
SG01 = 3
8801 = 1 ... 4
-> klassisches virtuelles 4-Zustands-SG-Ready
```

Dieser Grundpfad existiert bereits in V3.3.

**Neu bzw. deutlich erweitert in V3.4:**

```text
SG01 = 5 / 6 / 7
-> zweite reduzierte SG/PV-Familie

SG01 = 7
-> Register 8801 erneut als virtueller Eingang
-> 8801 = 1 / 2 / 3 -> Zustände 6 / 7 / 8
```

Zusätzlich wurde die Weitergabe der High-PV-Sollwertoffsets in der V3.4-State-Machine erweitert/robuster organisiert.

---

## 8. Sinnvolle Live-Verifikation

Zunächst ausschließlich lesend:

- Register 1334 (SG01) lesen
- Register 8801 lesen
- Register 2133 bzw. den bereits bekannten effektiven SG-Status parallel beobachten
- 1336...1341 mitloggen

Ein späterer kontrollierter Test der versteckten SG01-Werte 5/6/7 sollte erst nach Parameterbackup und mit bewusst gewähltem Anlagenzustand erfolgen. Diese Werte verändern die Regelvorgaben der Wärmepumpe und sind derzeit nicht als normale UI-Einstellungen freigegeben.
