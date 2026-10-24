#define MyAppName "Composer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "cyberpartition"
#define MyAppExeName "Composer.exe"

[Setup]
AppId={{8F3C2A71-6B14-4E59-9D20-5C7A1E4B8F03}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Composer
DefaultGroupName=Composer
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=Composer-1.0.0-setup
SetupIconFile=composer.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Files]
Source: "..\release\portable\Composer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Composer"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Composer"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Composer"; Flags: nowait postinstall skipifsilent
