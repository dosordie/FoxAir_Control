# SG Ready: Welche Auswahl ist die richtige?

SG01 / MAIN:1334 kennt mehr Einstellungen als die älteren App-Anzeigen vermuten lassen:

- **0 – Aus:** keine SG-Ready-Steuerung.
- **1/2/3 – Klassisch:** ein Kontakt, zwei Kontakte oder vier virtuelle Zustände über Register 8801.
- **4 – AI Saving / Remote Energy Control:** separater App-Pfad für AI Saving beziehungsweise dynamische Stromtarife; kein normaler SG-Ready-Modus.
- **5 – SG/PV erweitert, ein Kontakt:** Neutral oder High PV.
- **6 – SG/PV erweitert, zwei Kontakte:** Low PV, Neutral oder High PV.
- **7 – SG/PV erweitert, Modbus:** Low PV, Neutral oder High PV über Register 8801 (`1/2/3`).

Die Bezeichnung „SG/PV erweitert“ beschreibt die erkannte Funktion; ein offizieller Herstellername für 5/6/7 ist nicht bekannt. Die physischen Varianten 5 und 6 sind in der V3.4-Firmware bestätigt, aber noch nicht live am Gerät verifiziert. Modus 7 ist praktisch deutlich besser bestätigt.

Register 8801 sollte nur bei Modus 3 oder 7 und nur über den direkten User-/Mainboard-Modbus verwendet werden. Es ist nicht als funktionaler Eingang über Warmlink/LTE bestätigt. Technische Details, Stufenwirkungen und Vertrauensstände stehen in [SG Ready](../sg_ready.md).
