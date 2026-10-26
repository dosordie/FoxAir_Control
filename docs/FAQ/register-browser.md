# Register-Browser

Durchsuche die bekannten **FoxAir-/PHNIX-Register** nach Nummer, Parametercode, Namen und Beschreibung. Du kannst nach Kommunikationsbereich, Parametergruppe und Schreibbarkeit filtern, die Tabelle sortieren und die Registerdetails aufklappen.

**Nur Dokumentation:** Dieser Browser verbindet sich nicht mit deiner Wärmepumpe und verändert keine Einstellungen. Die Verfügbarkeit der Register hängt von Gerätevariante, Firmware und Kommunikationsweg ab.

!!! warning "Virtuelle Register und Display-Bus"
    **Virtuelle FoxAir-IDs (beispielsweise 91xxx)** sind keine direkt adressierbaren Modbus-Register. Der Display-Bus ist nicht mit dem Benutzer-Modbus am Mainboard gleichzusetzen. Nicht vollständig bestätigte Zuordnungen bleiben vorläufig.

<div id="fox-register-browser" data-src="../assets/register-browser/registers.json">
  <p>Registerliste wird geladen …</p>
</div>

<noscript>Für den interaktiven Browser wird JavaScript benötigt. Die Daten findest du auch im <a href="https://github.com/dosordie/FoxAir_Control/tree/main/data">GitHub-Repository</a>.</noscript>

---

**Quellen:** [Mainboard-Register](https://github.com/dosordie/FoxAir_Control/blob/main/data/foxair_phnix_registers.json) · [Display-/virtuelle Register](https://github.com/dosordie/FoxAir_Control/blob/main/data/foxair_phnix_display_registers.json) · [Ergänzendes Wissen](https://github.com/dosordie/FoxAir_Control/blob/main/data/foxair_phnix_knowledge.json)

Die Daten werden beim Website-Build automatisch neu eingelesen. Die Originaldateien bleiben unverändert.
