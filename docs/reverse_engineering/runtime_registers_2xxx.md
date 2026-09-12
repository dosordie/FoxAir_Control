# Runtime-Register 2xxx – Reverse Engineering

Stand: 2026-09-12

Diese Notiz sammelt Zuordnungen aus Live-Beobachtungen, der DWIN/DEMONS-Display-ASM und der statischen Analyse der Mainboard-Firmware V3.3/V3.4. Unsichere Zuordnungen sind ausdrücklich als Kandidat/offen markiert.

## Vertrauensstufen

- **bestätigt** – direkte Bezeichnung bzw. geschlossener Codepfad.
- **sehr wahrscheinlich** – Datentyp/Struktur ist im Code klar, die konkrete fachliche Quelle aber noch nicht vollständig geschlossen.
- **offen** – nur Struktur-/Live-Hinweise, keine belastbare fachliche Benennung.

## Registerübersicht

| Register | Zuordnung | Skalierung / Beobachtung | Status |
|---:|---|---|---|
| 2057 | T35 – AC-Eingangsstrom | RAW / 10 = A; RAW 30 = 3,0 A | bestätigt |
| 2080 | internes Betriebs-/Anforderungs-Statuswort; identisch zu Displaybus 91099 | 16-Bit-Bitfeld, Einzelbits noch offen | bestätigt als Bitfeld |
| 2106 | `M_PULS` – Zeit-/Impulsstatus | Bit 0: 5-Minuten-Puls für Display-Historie | bestätigt |
| 2139 | Mehrzonen-/Zone-1-Runtimewert | live 0 ↔ 32 (`0x20`); Bit 5 auffällig | offen |
| 2146 | interner Temperatur-/Regelwert | signed / 10 °C; RAW 44 = 4,4 °C | sehr wahrscheinlich |
| 2152 | Zone-1-Runtime-/Regelwert | live 1 ↔ 2; intern gefiltert/geglättet, kein einfaches Enum | sehr wahrscheinlich für Struktur, Semantik offen |
| 2164 | Zone 1: Auslasswassertemperatur nach AT-Kompensation | RAW / 10 °C; RAW 450 = 45,0 °C | bestätigt |
| 2165 | Zone 2: Auslasswassertemperatur nach AT-Kompensation | RAW / 10 °C; RAW 350 = 35,0 °C | bestätigt |
| 2166 | Statuswert direkt hinter Mehrzonen-Liveblock | live RAW 1 | offen |

## 2057 – T35 / AC-Eingangsstrom

Die Mainboard-Zuordnung ist **T35 / AC Input Current**. Die Skalierung ist 0,1 A pro Rohwert. Damit ist eine Anzeige von 30 A bei RAW `30` falsch; korrekt sind **3,0 A**. T34 / AC-Eingangsspannung liegt separat auf Register 2062.

## 2080 – internes Status-/Anforderungswort

Die V3.4-Firmware behandelt den exportierten Wert bitweise: einzelne Bits werden gesetzt, gelöscht und separat ausgewertet. Damit ist 2080 kein normaler Messwert, sondern ein **16-Bit-Statuswort/Bitfeld**.

Live wurde bereits beobachtet, dass 2080 identisch zur virtuellen Displaybus-ID `91099` verläuft. Die fachliche Belegung der einzelnen Bits ist noch nicht vollständig geschlossen und wird deshalb noch nicht in der Mapping-Datei benannt.

## 2106 – M_PULS / 5-Minuten-Puls

In `VAR_DEMONS.Lst` ist direkt definiert:

```text
M_PULS EQU 0X083A
```

`0x083A` entspricht dezimal **2106**. In der Display-ASM wird Bit 0 auf eine steigende Flanke geprüft und der Abschnitt ist ausdrücklich als **5-Minuten-Datenspeicherung** bezeichnet. Sinngemäß:

```text
LDWR R0,M_PULS
...
AND  R10,R12,2
... steigende Flanke ...
IJNE R11,1,FZBCRET
; 5 Minuten erreicht
```

Damit ist die frühere Hypothese „Pumpenregel-/PWM-Regelzyklus“ widerlegt. Der damals live beobachtete ungefähr fünfminütige Puls war der Display-/Historien-Zeitimpuls. Weitere Bits von 2106 sind noch offen.

## 2139 – Mehrzonen-Runtimewert

Der V3.4-Datenpfad führt 2139 in den Mehrzonen-/Zone-1-Konfigurations-/Runtimebereich. Im Livebetrieb wurde ein Wechsel zwischen `0` und `32` beobachtet. `32 = 0x20` macht Bit 5 auffällig; eine fachliche Bitbezeichnung ist derzeit aber **nicht bestätigt**.

Deshalb bleibt das Register im Mapping bewusst `RAW` und wird nur als Kandidat gekennzeichnet.

## 2146 – Temperatur-/Regelwert

Die V3.4-Firmware verwendet den veröffentlichten Wert als signed Temperatur-/Schwellwert im 0,1-°C-Maßstab. Ein Livewert `44` entspricht deshalb **4,4 °C**.

Noch offen ist, welche konkrete Sensor-, Differenz- oder interne Regeltemperatur hier veröffentlicht wird. Der Datentyp `TEMP1` ist deutlich besser belegt als die fachliche Bezeichnung.

## 2152 – Zone-1-Runtimefeld

2152 gehört zum Runtimeblock von **Zone 1**; in der internen Zone-2-Struktur existiert ein entsprechendes Feld. Der Wert wird in Regelpfaden über längere Zeit gefiltert bzw. geglättet. Die aktuell beobachteten Werte `1` und `2` dürfen daher **nicht als Enum 1/2 interpretiert** werden.

Physikalische Bedeutung und Skalierung sind noch offen.

## 2164 / 2165 – AT-kompensierte Zonen-Auslasstemperaturen

Die Display-ASM benennt beide Werte direkt:

```text
; Zone 1: Wasseraustrittstemperatur nach Umgebungstemperaturkompensation
LDWR R240,0874H

; Zone 2: Wasseraustrittstemperatur nach Umgebungstemperaturkompensation
LDWR R240,0875H
```

Damit gilt:

- `0x0874` = **2164** = Zone 1, AT-kompensierte Auslasswassertemperatur
- `0x0875` = **2165** = Zone 2, AT-kompensierte Auslasswassertemperatur

Die Werte werden über die Temperatur-Anzeigeroutine ausgegeben und sind in 0,1 °C skaliert. Die Livewerte `450` und `350` entsprechen somit **45,0 °C** bzw. **35,0 °C**.

## 2166 – noch offen

2166 folgt direkt auf den bestätigten Mehrzonen-Liveblock. Live wurde `1` beobachtet. Für `0x0876` wurde in der untersuchten Display-ASM jedoch keine direkte Referenz gefunden. Deshalb wird vorerst **keine konkrete Funktion behauptet**.
