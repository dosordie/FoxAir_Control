# FoxAir / PHNIX – Firmwareversionen und ihre Unterschiede

**Stand: 19. November 2026**

Welche Firmware ist auf meiner FoxAir installiert? Was bringt eine neuere Version? Und warum kann auf dem Display V1.7 stehen, obwohl die Wärmepumpe bereits V3.5 verwendet?

Der wichtigste Punkt vorweg: **Die Wärmepumpe besteht aus mehreren Geräten, die jeweils eine eigene Softwareversion haben.** Diese Versionen dürfen nicht miteinander verwechselt werden.

## Drei verschiedene Firmwareversionen

| Bauteil | Wofür ist es zuständig? | Bekannte Versionsbeispiele | Wie wird es aktualisiert? |
| --- | --- | --- | --- |
| **Hauptsteuerung (Mainboard)** | Heizbetrieb, Verdichter, Pumpen, Abtauung und Schutzfunktionen | V1.2, V1.3, V3.3, V3.4, V3.5 | Über das Kommunikationsmodul, zum Beispiel mit dem FoxAir Updater |
| **Touch-Display** | Anzeige, Menüs und Bedienung direkt an der Wärmepumpe | V1.3, V1.7 | Per SD-Karte |
| **LTE-/WarmLink-Modul** | Verbindung zur WarmLink-App und zum Internet | z. B. V1.2 | Über einen eigenen Updateweg des Kommunikationsmoduls |

**Beispiel:** Eine FoxAir kann gleichzeitig **Display V1.7** und **Hauptsteuerung V3.5** haben. Das ist kein Fehler, sondern vollkommen normal.

### Wozu brauche ich den Softwarecode?

Neben der Versionsnummer gibt es eine längere **Software-Kennnummer**. Sie zeigt, **für welche Geräte- bzw. Steuerungsfamilie** eine Firmware vorgesehen ist.

| Bauteil | Bekannte Kennnummer |
| --- | --- |
| Hauptsteuerung vieler FoxAir GL9/GL9-1 | **82400644** |
| Kleines DWIN-Touch-Display | **82400463** |
| LTE-/WarmLink-Modul, bei einem Gerät festgestellt | **82400409** |

Die Nummern sind **keine Versionsnummern**. Beispielsweise kann dieselbe Hauptsteuerungs-Kennnummer `82400644` sowohl mit V3.3 als auch mit V3.5 vorkommen.

**Vor einem Firmwareupdate immer beide Angaben prüfen: Softwarecode und Version.** Eine passende Versionsnummer allein bedeutet noch nicht, dass das Update zum eigenen Gerät passt.

---

## Hauptsteuerung – welche Versionen sind bekannt?

Die folgenden Angaben beziehen sich überwiegend auf die FoxAir-GL9-/GL9-1-Familie mit der **Software-Kennnummer 82400644**.

| Version | Woher kennen wir sie? | Wichtigste bekannte Merkmale |
| --- | --- | --- |
| **V1.2** | Auf FoxAir-Geräten beobachtet | Älterer Softwarestand; ein vollständiges Änderungsprotokoll liegt nicht vor |
| **V1.3** | Auf GL9/GL9-1 beobachtet | Älterer Softwarestand; häufig zusammen mit Display V1.7 anzutreffen |
| **V3.3** | Auf GL9 verwendet und untersucht | Automatische Umwälzpumpenregelung und erweiterte SG-Ready-Funktionen |
| **V3.4** | Original-Firmware untersucht und im Forum als Update gemeldet | Verbesserungen bei Heizkurve, Timern, Kaltstart und Strombegrenzung |
| **V3.5** | Original-Firmware aus einer FoxAir BlueLine untersucht | Zusätzliche Möglichkeiten für eine externe Leistungs- und Sollwertregelung |

In Unterlagen zu **anderen PHNIX-Geräten** kommen außerdem V2.4 und V2.6 vor. Diese Versionen sind deshalb **nicht automatisch als Updates für die FoxAir GL9** geeignet.

### V3.3 – wichtigste bekannte Änderungen

Für Anwender sind vor allem diese Erweiterungen interessant:

- **Automatische Regelung der Heizkreispumpe:** Die Wärmepumpe kann die Pumpendrehzahl passend zur Temperaturdifferenz zwischen Vor- und Rücklauf anpassen.
- **Mehr Pumpenleistung beim Abtauen:** Im Automatikbetrieb wird die Pumpe während des Abtauens mit hoher Drehzahl betrieben.
- **Verbesserte Wannenheizung:** Die Heizung der Bodenwanne kann nach dem Abtauen zeitlich begrenzt weiterlaufen.
- **Mehr Einstellungen für SG Ready und PV-Überschuss:** Die Steuerung bietet zusätzliche Möglichkeiten für die Einbindung einer Photovoltaikanlage.
- **Zusätzliche Einstell- und Anzeigewerte:** Neuere Programme und Displays können weitere Funktionen zugänglich machen.

**Was bringt das im Alltag?** Vor allem die automatische Pumpenregelung kann unnötig hohe Pumpendrehzahlen vermeiden, sofern die Anlage richtig eingestellt ist.

Weitere Informationen: [Wasserdurchfluss und Pumpenbetriebsarten](https://dosordie.github.io/FoxAir_Control/wasserdurchfluss_pumpe/) und [Automatische Pumpenregelung](https://dosordie.github.io/FoxAir_Control/automatische_up_regelung/).

### V3.4 – wichtigste bekannte Änderungen

V3.4 erweitert die Funktionen von V3.3:

- **Heizkurve und Leistungstimer gleichzeitig:** Beide Funktionen können zusammen verwendet werden. Bei älteren Softwareständen gab es dabei Einschränkungen.
- **Überarbeiteter Kaltstart:** Die Vorheizung des Verdichters vor einem Kaltstart wurde verbessert. Die normale Verdichter-/Ölsumpfheizung arbeitet unabhängig davon weiter.
- **Verbesserte Strombegrenzung:** Die Wärmepumpe kann bei dreiphasiger Versorgung die Belastung der einzelnen Phasen berücksichtigen.
- **Erweiterte SG-Ready-/PV-Funktionen:** Weitere Möglichkeiten zur Beeinflussung des Betriebs durch externe Vorgaben sind vorhanden.

**Was bringt das im Alltag?** Besonders die gleichzeitige Nutzung von Heizkurve und Leistungstimern ist eine praktische Verbesserung.

### V3.5 – wichtigste bekannte Änderungen

V3.5 baut auf V3.4 auf. **Die bekannten Grundfunktionen bleiben erhalten.** Neu sind vor allem zusätzliche Möglichkeiten, die Wärmepumpe durch eine übergeordnete Steuerung oder über eine passende Fernanbindung zu beeinflussen.

| Bereich | Was ist neu bzw. erweitert? | Was bedeutet das für Nutzer? |
| --- | --- | --- |
| **Verdichterleistung** | Zusätzliche Vorgaben zur Begrenzung der Verdichterfrequenz beim Heizen, Kühlen und bei der Warmwasserbereitung | Eine geeignete externe Steuerung kann die Leistung gezielter beeinflussen |
| **Solltemperaturen** | Erweiterte Möglichkeiten, die Solltemperaturen für Heizung, Kühlung und Warmwasser anzupassen | Interessant für eine Einbindung in Energiemanagement oder Hausautomation |
| **Raum- und Zonenregelung** | Zusätzliche Korrekturmöglichkeiten für die Temperaturregelung einzelner Zonen | Vor allem bei Anlagen mit entsprechender Zonenregelung relevant |
| **Angepasste Leistungsregelung** | Weitere Regeln für den Umgang mit externen Leistungsanforderungen | Die Wärmepumpe kann externe Vorgaben feiner umsetzen |
| **Anzeige des Heizsollwerts** | Der tatsächlich berechnete Heizungs-Sollwert lässt sich zusätzlich auslesen | Hilfreich, wenn man verstehen möchte, welche Temperatur die Steuerung gerade anstrebt |

**Wichtig:** Diese neuen Möglichkeiten werden nicht automatisch bei jeder Wärmepumpe genutzt. Ein Teil davon setzt eine entsprechend eingerichtete externe Steuerung voraus. Wer seine FoxAir ausschließlich über das Touch-Display bedient, bemerkt deshalb möglicherweise kaum einen Unterschied.

#### Was ist mit „AI Saving“ und dynamischen Stromtarifen?

Einige Apps und Steuerungsvarianten bieten eine Funktion namens **AI Saving** beziehungsweise eine Anpassung an Strompreise an.

- **Nicht erst seit V3.5:** Die grundlegende Unterstützung für eine entsprechende Fernregelung war bereits in **V3.4** vorhanden.
- **In V3.5 erweitert:** Neuere Softwarestände bieten zusätzliche Möglichkeiten, Leistung und Temperaturen von außen anzupassen.
- **Keine automatische Garantie:** Ein Firmwareupdate allein aktiviert weder einen dynamischen Stromtarif noch eine passende Optimierung.
- **„AI“ ist eine Funktionsbezeichnung:** Ob bei der Auswertung tatsächlich künstliche Intelligenz eingesetzt wird, lässt sich daraus nicht ableiten.

**Kurz gesagt:** V3.5 erweitert die Möglichkeiten für externe Energie- und Leistungsoptimierung. Eine generell höhere Effizienz oder automatisch niedrigere Stromkosten lassen sich daraus nicht versprechen.

#### Kann ich V3.5 auch auf einer GreenLine verwenden?

Die untersuchte V3.5 stammt von einer **FoxAir BlueLine**. BlueLine und entsprechende GreenLine-/GL-Geräte verwenden jedoch dieselbe Firmwarefamilie, **wenn die Software-Kennnummer 82400644 übereinstimmt**.

Daher ist die V3.5 dieser Firmwarefamilie grundsätzlich auch für passende GreenLine-/GL-Geräte vorgesehen. **Entscheidend ist die Kennnummer der Hauptsteuerung, nicht allein die Modellbezeichnung.** Bei anderen Kennnummern darf die Firmware nicht einfach als kompatibel angenommen werden.

#### Gibt es bereits praktische Erfahrungen mit Firmwareupdates?

Ja. Mit dem [FoxAir Updater](https://github.com/dosordie/FoxAir_updater) wurden unter anderem diese Wechsel erfolgreich durchgeführt:

- **V1.2 → V3.4**
- **V3.3 → V3.4**
- **Update auf V3.5**
- **Downgrade V3.5 → V3.4**

Das sind erfolgreiche Tests, **keine Garantie für jede Geräte- und Versionskombination**. Vorher die Software-Kennnummer prüfen und die passende Firmware verwenden.

---

## Touch-Display – unabhängig von der Hauptsteuerung

Das kleine DWIN-Touch-Display hat seine **eigene Firmware**. Eine ältere Anzeige bedeutet daher nicht automatisch, dass auch die Wärmepumpe selbst veraltete Software nutzt.

| Displayversion | Software-Kennnummer | Bekanntes Paket |
| --- | --- | --- |
| **V1.3** | **82400463** | Englisch, Stand Juli 2022 |
| **V1.7** | **82400463** | Englisch, Stand November 2023 |

Ein Update des Displays erfolgt **über eine SD-Karte** mit dem vollständigen Ordner `DWIN_SET`. Die Software der Hauptsteuerung wird dadurch nicht verändert.

**Warum lohnt sich V1.7?** Ältere Displayversionen kennen manche später ergänzten Funktionen nicht. Die Wärmepumpe kann trotzdem laufen, aber einzelne Einstellungen oder Anzeigen fehlen dann möglicherweise.

Bei einer Hauptsteuerung mit **V3.3, V3.4 oder V3.5** ist daher nach Möglichkeit **Display V1.7** sinnvoll.

Neben der englischen V1.7 gibt es auch eine **deutsch übersetzte Community-Version**. Deren Sprache und Darstellung können von der Originalversion abweichen.

Eine Updateanleitung und Hinweise zu den Displaypaketen findest du unter [Firmware-Versionen und Display-Update](https://dosordie.github.io/FoxAir_Control/firmware/).

---

## LTE-/WarmLink-Modul – nochmals eine eigene Version

Das LTE-Modul verbindet die Wärmepumpe mit WarmLink und den Online-Diensten. Es besitzt ebenfalls eine eigene Software.

Bei einem untersuchten Gerät wurden folgende Daten festgestellt:

| Kennung | Beobachteter Wert |
| --- | --- |
| Hardwarecode | 82300225 |
| Softwarecode | 82400409 |
| Version | V1.2 |

Diese Angaben gelten für das untersuchte Modul und müssen **nicht bei allen FoxAir-Geräten identisch** sein.

Ein Update dieses Moduls ist etwas anderes als ein Update der Hauptsteuerung oder des Touch-Displays.

---

## Welche Firmware passt zu meiner FoxAir?

Für **GL9 und GL9-1** ist die Hauptsteuerungs-Kennnummer **82400644** gut dokumentiert. Dieselbe Kennnummer kommt aber auch bei anderen PHNIX-Geräten vor.

Deshalb sollte man vor einem Update Folgendes abgleichen:

1. **Welches Modell habe ich?** Zum Beispiel GL9, GL9-1 oder BlueLine.
2. **Welche Software-Kennnummer hat die Hauptsteuerung?**
3. **Welche Version ist aktuell installiert?**
4. **Für welche Geräte und Software-Kennnummer ist die neue Firmware vorgesehen?**

Wer unsicher ist, sollte **nicht allein nach einer höheren Versionsnummer aktualisieren**.

Die benötigten Angaben lassen sich je nach Gerät über die Geräteinformationen, WarmLink oder [FoxAir Control](https://github.com/dosordie/FoxAir_Control) auslesen.

## Firmware aktualisieren – wo finde ich die Anleitung?

| Vorhaben | Richtige Anleitung |
| --- | --- |
| **Display-Firmware aktualisieren** | [Display-Update per SD-Karte](https://dosordie.github.io/FoxAir_Control/firmware/#display-firmware-aktualisieren) |
| **Hauptsteuerung unter Windows aktualisieren** | [FoxAir Updater – Windows-Anleitung](https://dosordie.github.io/FoxAir_Control/firmwareupdate-windows/) |
| **Hauptsteuerung unter Linux / Raspberry Pi aktualisieren** | [Linux-/Raspberry-Pi-Anleitung](https://dosordie.github.io/FoxAir_Control/firmwareupdate-linux/) |
| **LTE-Modul sichern / vorbereiten** | [LTE-Modem-Anleitung](https://dosordie.github.io/FoxAir_Control/lte-modem-backup/) |

**Achtung:** Ein Firmwareupdate erfolgt auf eigenes Risiko. Während des Updates dürfen Wärmepumpe und Kommunikationsmodul nicht einfach ausgeschaltet werden. Auch eine Anzeige von 100 % bei der Datenübertragung bedeutet noch nicht, dass das Update vollständig abgeschlossen ist.

---

## Quellen und Erfahrungen aus der Community

Die bekannten Änderungen beruhen auf verfügbaren Firmwareständen, praktischen Tests und Berichten anderer FoxAir-/PHNIX-Nutzer. Ein vollständiges offizielles Änderungsprotokoll des Herstellers liegt nicht für jede Version vor.

- [FoxAir im Photovoltaikforum – Erfahrungen und Firmwareversionen](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=48)
- [Diskussion zu älteren Hauptsteuerungs-Versionen](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=85)
- [Unterschied zwischen Display- und Hauptsteuerungs-Firmware](https://www.photovoltaikforum.com/thread/242531-foxair-w%C3%A4rmepumpen-erfahrungen-meinungen-tipps/?pageNo=91)
- [PHNIX-/WarmLink-Nutzer im Wärmepumpenforum](https://www.waermepumpenforum.com/forum/thread/4752-suche-zwecks-erfahrungsaustausch-phnix-warmlink-nutzer/)

## Neue Firmware entdeckt?

Damit andere Nutzer eine Version eindeutig zuordnen können, sind diese Angaben hilfreich:

- **Modell:** zum Beispiel FoxAir GL9
- **Hauptsteuerung:** Software-Kennnummer und Version
- **Display:** Software-Kennnummer und Version
- **WarmLink-Modul:** Version, sofern bekannt
- **Quelle:** zum Beispiel Foto des Displays oder Informationen aus der App

So lässt sich leichter erkennen, ob es sich um eine wirklich neue Version für die jeweilige FoxAir handelt.
