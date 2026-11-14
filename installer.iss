; Inno Setup Script for V-Stream Downloader Pro v5.1 (--onedir with V-Stream-Engine)
#define MyAppName "V-Stream Downloader"
#define MyAppVersion "5.1.0"
#define MyAppPublisher "Eslam Mustafa"
#define MyAppExeName "V-Stream-Downloader.exe"

[Setup]
AppId={{8F4E2B19-7C91-4E3A-9D52-14B8E9C05100}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=V-Stream-Downloader-Pro-v{#MyAppVersion}-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\V-Stream-Downloader\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\V-Stream-Downloader\V-Stream-Engine\*"; DestDir: "{app}\V-Stream-Engine"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
