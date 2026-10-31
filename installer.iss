#ifndef AppVersion
  #error Build with build.ps1 so the version comes from VERSION
#endif

[Setup]
AppId={{C1DD4A29-1B64-433C-A69E-352D1DB9E575}
AppName=Luminaria
AppMutex=Local\LuminariaDesktop
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
#define AppPublisher "Desselle Solution Software"
AppPublisher={#AppPublisher}
AppCopyright=Copyright (C) 2026 {#AppPublisher}
VersionInfoCompany={#AppPublisher}
VersionInfoCopyright=Copyright (C) 2026 {#AppPublisher}
VersionInfoProductName=Luminaria
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription=Luminaria Setup
DefaultDirName={userdesktop}\Luminaria\App
UsePreviousAppDir=no
DefaultGroupName=Luminaria
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=Luminaria-{#AppVersion}-Setup
SetupIconFile=web\brand\luminaria.ico
UninstallDisplayIcon={app}\LocalAIStudio.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[InstallDelete]
; Program files are replaced as a whole so nothing from an older version lingers.
; Chats, settings, models and files live in data, models and Files, which are never touched.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\runtime\agent-tools"

[Files]
Source: ".build\dist\LocalAIStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "licenses\llama.cpp.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "runtime\agent-tools\*"; DestDir: "{app}\runtime\agent-tools"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "runtime\prereqs\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{group}\Luminaria"; Filename: "{app}\LocalAIStudio.exe"
Name: "{autodesktop}\Luminaria"; Filename: "{app}\LocalAIStudio.exe"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 (needed to show the app)..."; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\LocalAIStudio.exe"; Description: "Open Luminaria"; Flags: nowait postinstall skipifsilent

; Uninstallation removes program files only. History, models and workspace are retained.

[Code]
const WebView2Key = '\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(Root: Integer; Key: String): Boolean;
var V: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasVersion(HKLM, 'SOFTWARE\WOW6432Node' + WebView2Key) or
                 HasVersion(HKLM, 'SOFTWARE' + WebView2Key) or
                 HasVersion(HKCU, 'Software' + WebView2Key));
end;
