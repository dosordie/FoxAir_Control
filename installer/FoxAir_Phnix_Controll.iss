#define MyAppName "FoxAir / Phnix Controll"
#define MyAppExeName "FoxAir_Phnix_Controll.exe"
#define MyAppVersion "0.2.27"
#define MyAppPublisher "DosOrDie"

[Setup]
AppId={{B15D04E7-3A60-4F44-8C77-5D2F0F62D226}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FoxAir Phnix Controll
DefaultGroupName=FoxAir Phnix Controll
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=FoxAir_Phnix_Controll_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\app_icon.ico
LicenseFile=..\LICENSE

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "..\dist\FoxAir_Phnix_Controll\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PUBLIC_WARNING.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FoxAir Phnix Controll"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\FoxAir Phnix Controll"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Optionale Verknuepfungen:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "FoxAir Phnix Controll starten"; Flags: nowait postinstall skipifsilent
