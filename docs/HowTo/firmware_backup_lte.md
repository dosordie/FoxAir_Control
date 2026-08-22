# Firmware-Backup des LTE-Modems über Micro-USB

Diese Anleitung beschreibt kurz, wie man sich unter Windows per **Micro-USB** mit dem LTE-Modem verbindet und die Firmware sowie einige zusätzliche Dateien mit **ADB** sichert.

> [!WARNING]
> Die aus dem LTE-Modem ausgelesenen Firmware- und Datendateien **nicht öffentlich hochladen oder weiterveröffentlichen**. Sie können herstellerspezifische Software, Konfigurationsdaten oder andere nicht für die Veröffentlichung bestimmte Inhalte enthalten.

## 1. LTE-Modem öffnen und USB-Port freilegen

- Der Deckel des LTE-Modems ist **nur gesteckt** und kann vorsichtig abgenommen werden.
- Im **Micro-USB-Port** kann sich etwas Versiegelungs-/Vergussmasse von der Platine befinden.
- Diese lässt sich vorsichtig z. B. mit einer **Pinzette** entfernen.
- Dabei unbedingt darauf achten, den USB-Port, die Kontakte und die Platine nicht zu beschädigen.

Fotos vom geöffneten LTE-Modem werden später ergänzt.

## 2. Windows-Treiber installieren

Benötigt werden die SIMCom USB-Treiber:

- [SIMCOM Windows USB Drivers V1.0.2](https://files.waveshare.com/upload/2/24/SIMCOM_Windows_USB_Drivers_V1.0.2.zip)

ZIP-Datei entpacken und die passenden Windows-Treiber installieren.

Danach das LTE-Modem über den Micro-USB-Port mit dem PC verbinden.

## 3. Android SDK Platform Tools / ADB installieren

ADB ist Bestandteil der Android SDK Platform Tools:

- [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools?hl=de#downloads)

Für Windows die ZIP-Datei herunterladen und z. B. nach

```text
C:\platform-tools
```

entpacken.

Anschließend PowerShell in diesem Ordner öffnen und testen:

```powershell
.\adb.exe devices
```

Wenn die Verbindung funktioniert, sollte das LTE-Modem in der Geräteliste erscheinen.

Optional kann man zusätzlich testen:

```powershell
.\adb.exe shell
```

Mit

```text
exit
```

wird die Shell wieder verlassen.

## 4. Firmware sichern

Die eigentliche Firmware-Datei liegt unter:

```text
/cache/phnixIot_device_OTA
```

Download in den aktuellen Ordner:

```powershell
.\adb.exe pull /cache/phnixIot_device_OTA
```

## 5. Zusätzliche Dateien sichern

Zusätzlich können folgende Dateien bzw. Datenbereiche interessant sein.

### `/data/phnixIot4G`

```powershell
.\adb.exe pull /data/phnixIot4G
```

### `/data/phnixIot_device_OTA_INFO`

```powershell
.\adb.exe pull /data/phnixIot_device_OTA_INFO
```

### `/data/phnixIot_device_statisic`

```powershell
.\adb.exe pull /data/phnixIot_device_statisic
```

Die Dateien werden jeweils in den Ordner heruntergeladen, in dem PowerShell aktuell geöffnet ist.

## 6. Gesicherte Dateien prüfen

Nach dem Backup sollten sich die heruntergeladenen Dateien im aktuellen `platform-tools`-Ordner befinden.

Zur Sicherheit empfiehlt es sich, die Originaldateien zunächst **unverändert zu archivieren**, bevor sie analysiert oder weiterverarbeitet werden.

> [!IMPORTANT]
> Diese Backups bitte **nicht in ein öffentliches GitHub-Repository, Forum oder einen anderen öffentlich zugänglichen Speicher hochladen**.
