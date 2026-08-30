# Mainboard-Firmware V3.4 – SG-Statusregister 2133

Stand: 2026-08-30

Ergänzung zu `firmware_v34_sg_ready_8801.md`.

## Ergebnis

Die V3.4-Firmware veröffentlicht die internen SG-Zustände nicht immer 1:1 in Register **2133**.

Der relevante Codepfad liest den internen SG-State und macht:

```text
wenn state >= 6:
    Register_2133 = state - 5
sonst:
    Register_2133 = state
```

Damit gilt:

| interner V3.4-State | Register 2133 |
|---:|---:|
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 5 |
| 6 | 1 |
| 7 | 2 |
| 8 | 3 |

## Bedeutung für die neue SG01-Familie 5/6/7

Für den neuen vereinfachten SG/PV-Pfad bedeutet das:

```text
interner State 6 -> 2133 = 1 -> wenig PV / Leistungsbegrenzung (SG03/1336)
interner State 7 -> 2133 = 2 -> neutraler Normalbetrieb
interner State 8 -> 2133 = 3 -> High-PV-/Sollwertoffsetpfad (SG05..SG07)
```

Damit ist 2133 **modusabhängig zu interpretieren**. Die bisherige allgemeine Wertetabelle 0..5 beschreibt den klassischen SG-Ready-Pfad, ist für die neue V3.4-Auswahlfamilie SG01=5/6/7 aber nicht ausreichend.

Insbesondere bedeutet bei SG01=5/6/7:

- `2133 = 1` nicht zwingend klassischer SG-Ready-Schlaf-/Sperrmodus,
- `2133 = 2` ist hier der neutrale Zustand,
- `2133 = 3` ist hier bereits der High-PV-/Boostpfad.

Das ist ein weiteres starkes Indiz dafür, dass V3.4 mit SG01=5/6/7 eine **eigene dreistufige SG/PV-Funktion** implementiert und die Zustände 6/7/8 intern nur verwendet, um sie vom klassischen vierstufigen SG-Ready zu unterscheiden.

## Live-Test

Bei einem späteren kontrollierten Test von SG01=7 kann die Zuordnung direkt beobachtet werden:

| SG01 | 8801 | interner State | erwartetes 2133 |
|---:|---:|---:|---:|
| 7 | 1 | 6 | 1 |
| 7 | 2 | 7 | 2 |
| 7 | 3 | 8 | 3 |

Diese Tests verändern die SG-Regelvorgaben und sollten erst nach Parameterbackup und mit bewusst gewähltem Anlagenzustand durchgeführt werden.
