[Setup]
AppId={{C1DD4A29-1B64-433C-A69E-352D1DB9E575}
AppName=Luminaria
AppVersion=0.2.1
AppPublisher=Luminaria Project
DefaultDirName={userdesktop}\Luminaria\App
UsePreviousAppDir=no
DefaultGroupName=Luminaria
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=Luminaria-0.2.1-Setup
SetupIconFile=web\brand\luminaria.ico
UninstallDisplayIcon={app}\LocalAIStudio.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Files]
Source: ".build\dist\LocalAIStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Luminaria"; Filename: "{app}\LocalAIStudio.exe"
Name: "{autodesktop}\Luminaria"; Filename: "{app}\LocalAIStudio.exe"

[Run]
Filename: "{app}\LocalAIStudio.exe"; Description: "Open Luminaria"; Flags: nowait postinstall skipifsilent

; Uninstallation removes program files only. History, models and workspace are retained.
