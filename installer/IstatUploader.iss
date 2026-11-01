; L'installer di Istat Uploader (Inno Setup). Senza diritti di amministratore: installa per
; l'utente e registra hostlab-turismatica://, l'indirizzo con cui HostLab apre l'app.
; Si costruisce su Windows: ISCC /DVersione=1.6.0 installer\IstatUploader.iss
#ifndef Versione
  #error "Serve /DVersione=X.Y.Z"
#endif

[Setup]
AppId={{6C0A9E3B-4D1F-4E57-9B5A-2F7C1D8E6A10}
AppName=Istat Uploader
AppVersion={#Versione}
AppPublisher=Fortitudo
DefaultDirName={localappdata}\Programs\IstatUploader
DefaultGroupName=Istat Uploader
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=IstatUploaderSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
UninstallDisplayIcon={app}\IstatUploader.exe
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Files]
Source: "..\dist\IstatUploader.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Istat Uploader"; Filename: "{app}\IstatUploader.exe"
Name: "{userdesktop}\Istat Uploader"; Filename: "{app}\IstatUploader.exe"

[Registry]
Root: HKCU; Subkey: "Software\Classes\hostlab-turismatica"; ValueType: string; ValueData: "URL:HostLab Turismatica"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\hostlab-turismatica"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\hostlab-turismatica\DefaultIcon"; ValueType: string; ValueData: "{app}\IstatUploader.exe,0"
Root: HKCU; Subkey: "Software\Classes\hostlab-turismatica\shell\open\command"; ValueType: string; ValueData: """{app}\IstatUploader.exe"" ""%1"""

[Run]
Filename: "{app}\IstatUploader.exe"; Description: "Apri Istat Uploader"; Flags: postinstall nowait skipifsilent
