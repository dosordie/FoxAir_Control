#define MyAppName "FoxAir / Phnix Control"
#define MyAppExeName "FoxAir_Phnix_Control.exe"
#define MyAppVersion "0.2.45"
#define MyAppPublisher "DosOrDie"

[Setup]
AppId={{B15D04E7-3A60-4F44-8C77-5D2F0F62D226}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FoxAir Phnix Control
DefaultGroupName=FoxAir Phnix Control
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=FoxAir_Phnix_Control_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\app_icon.ico
LicenseFile=..\LICENSE

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "..\dist\FoxAir_Phnix_Control\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PUBLIC_WARNING.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FoxAir Phnix Control"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\FoxAir Phnix Control"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Optionale Verknuepfungen:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "FoxAir Phnix Control starten"; Flags: nowait postinstall skipifsilent
