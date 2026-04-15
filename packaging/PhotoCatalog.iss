; =============================================================================
; PhotoCatalog.iss — Inno Setup script for PhotoCatalog
; =============================================================================
; Wraps the PyInstaller --onedir output (dist/PhotoCatalog/) into a single
; setup installer that friends and family can double-click to install.
;
; Produces:   release/PhotoCatalog-Setup-<version>.exe
;
; Build with:  iscc packaging\PhotoCatalog.iss
; (or run packaging\build.ps1 which handles PyInstaller + Inno Setup in one
; shot.)
;
; Requires Inno Setup 6+ from https://jrsoftware.org/isinfo.php
; =============================================================================

#define MyAppName        "PhotoCatalog"
#define MyAppVersion     "2.1.1"
#define MyAppPublisher   "David Krist"
#define MyAppURL         "https://github.com/dkrist/PhotoCatalog"
#define MyAppExeName     "PhotoCatalog.exe"
#define MyAppIcon        "..\Images\photocatalog.ico"
#define MyAppSourceDir   "..\dist\PhotoCatalog"
#define MyOutputDir      "..\release"

[Setup]
; NOTE: AppId is a GUID — do NOT change it after the first release, or Windows
; will treat upgrades as a separate product. Generate once, keep forever.
AppId={{B6B0C94A-3F5A-4A3F-9E1C-6A9E1B8C0A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Install into Program Files by default; allow per-user install fallback.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Require Windows 10 or newer (our Python builds target it).
MinVersion=10.0

; Compress into a single LZMA setup.exe, which is what users will download.
Compression=lzma2
SolidCompression=yes

; Output
OutputDir={#MyOutputDir}
OutputBaseFilename=PhotoCatalog-Setup-{#MyAppVersion}

; Visual polish
WizardStyle=modern
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ArchitecturesInstallIn64BitMode=x64compatible

; Start Menu shortcut lives under the AppName group.
DisableFinishedPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Grab the entire PyInstaller onedir output. The * + recursesubdirs pair
; is the standard Inno Setup idiom for shipping a folder of files.
Source: "{#MyAppSourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; \
  Excludes: "{#MyAppExeName}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch the app after install completes.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent
