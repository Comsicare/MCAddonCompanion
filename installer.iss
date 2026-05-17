[Setup]
AppName=MCAddonCompanion
AppVersion=0.2.0
AppPublisher=Comsicare
DefaultDirName={localappdata}\MCAddonCompanion
DefaultGroupName=MCAddonCompanion
OutputDir=Output
OutputBaseFilename=MCAddonCompanion-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\MCAddonCompanion.exe

[Registry]
Root: HKCU; Subkey: "Software\MCAddonCompanion"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Files]
Source: "dist_windows\MCAddonCompanion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MCAddonCompanion"; Filename: "{app}\MCAddonCompanion.exe"
Name: "{commondesktop}\MCAddonCompanion"; Filename: "{app}\MCAddonCompanion.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\MCAddonCompanion.exe"; Description: "Launch MCAddonCompanion"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Leave %APPDATA%\MCAddonCompanion\ (state.json) — user data
