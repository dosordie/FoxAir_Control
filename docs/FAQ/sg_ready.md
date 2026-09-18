# SG Ready und PV-Überschusssteuerung

SG Ready ermöglicht es, der Wärmepumpe vorzugeben, ob gerade wenig oder viel elektrische Energie zur Verfügung steht.

Das kann zum Beispiel für PV-Überschuss genutzt werden.

## Möglichkeiten

Die FoxAir unterstützt – abhängig von Firmware und Konfiguration – mehrere Varianten:

- Steuerung über physische Kontakte
- klassische SG-Ready-Zustände
- bei neueren Firmwareständen auch virtuelle Steuerung über Modbus

Typische Zustände sind:

- Sperren / Schlafmodus
- Normalbetrieb
- erhöhte Leistung
- hoher PV-Überschuss / Sollwertanhebung

Für die Einrichtung und die genaue Zuordnung der Kontakte und Register gibt es eine eigene technische Dokumentation:

[SG-Ready-Dokumentation](../sg_ready.md)

> Für eine einfache PV-Steuerung sollte zuerst festgelegt werden, ob physische Kontakte oder Modbus verwendet werden sollen.
