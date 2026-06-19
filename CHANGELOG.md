## PUBLIC V0.2.46

- Version auf **0.2.46** angehoben; `APP_EDITION` bleibt **PUBLIC**.
- Projektstruktur aufgeräumt: Core, Cloud, Worker, Dialoge, UI-Helfer und JSON-Daten liegen jetzt in eigenen Ordnern.
- WarmLink-Cloud/LTE-Fenster aus `foxair_phnix_control.py` nach `dialogs/cloud_dialog.py` ausgelagert.
- Pfad-/Resource-Helfer nach `ui/paths.py` und kleine UI-Konstanten nach `ui/theme.py` ausgelagert.
- JSON-Register-/Knowledge-Dateien nach `data/` verschoben und Build-Pfade angepasst.
- Dev-/Experimentierwerkzeuge nach `devtools/` verschoben; sie werden nicht als Runtime-Daten in den PyInstaller-Build gepackt.
- Verhalten aus PUBLIC V0.2.45 bleibt erhalten: Cloud-only-Schalter nur im Cloud-Fenster, dort standardmäßig aktiv; keyring bleibt Pflicht-Abhängigkeit; Cloud-Schreibformat unverändert.

## PUBLIC V0.2.45

- Cloud-only-Zeilen-Schalter aus dem Hauptfenster entfernt.
- Cloud-only-Zeilen bleiben im WarmLink-Cloud-Fenster und sind dort standardmäßig aktiviert.
- `keyring>=25.0` bleibt Pflicht-Abhängigkeit.
- PyInstaller-Build sammelt `keyring`/Windows-Keyring-Abhängigkeiten ein.

## PUBLIC V0.2.44

- Public-Build mit WarmLink/Linked-Go-Cloud-Funktionen erstellt; `APP_EDITION` ist **PUBLIC**.
- Enthält Cloud-Login, Geräte-/Device-ID-Anzeige, Cloud-Polling, Cloud-Overlay, Cloud-Wertefinder und Cloud-Schreibtest.
- Cloud-Schreiben nutzt das bestätigte Format: `app/device/control?lang=en` mit `appId="16"` und `param: [{deviceCode, protocolCode, value}]`.
- Hauptfenster: Rechtsklick **Wert per Cloud schreiben ...** für bekannte schreibbare Cloud-Codes.
- Log-Spam im Backend **Modbus Display** reduziert.
