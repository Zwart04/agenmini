#ifndef AppVersion
#define AppVersion "0.5.0"
#endif
[Setup]
AppId={{B347A6AD-CE20-46CF-9CEB-902D80657671}
AppName=Agen Mini
AppVersion={#AppVersion}
AppPublisher=Zwart04
AppPublisherURL=https://github.com/Zwart04/agenmini
DefaultDirName={localappdata}\Programs\Agen Mini
DefaultGroupName=Agen Mini
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=agenmini-setup-{#AppVersion}-windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
UninstallDisplayIcon={app}\runtime\pythonw.exe
[Tasks]
Name: "desktopicon"; Description: "Buat shortcut desktop"; Flags: unchecked
Name: "autostart"; Description: "Jalankan Agen Mini ketika login Windows"; Flags: unchecked
[Files]
Source: "payload\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Agen Mini"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"
Name: "{group}\Hentikan Agen Mini"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"" --stop"; WorkingDir: "{app}"
Name: "{autodesktop}\Agen Mini"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"""; Tasks: desktopicon
Name: "{userstartup}\Agen Mini"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"" --no-browser"; Tasks: autostart
[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"""; Description: "Buka Agen Mini"; Flags: postinstall nowait skipifsilent
[UninstallRun]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"" --stop"; Flags: runhidden waituntilterminated

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var ResultCode: Integer; PythonPath: String;
begin
  Result := '';
  PythonPath := ExpandConstant('{app}\runtime\pythonw.exe');
  if FileExists(PythonPath) then begin
    Exec(PythonPath, '"'+ExpandConstant('{app}\launcher.py')+'" --stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(PythonPath, '"'+ExpandConstant('{app}\launcher.py')+'" --backup', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if ResultCode <> 0 then Result := 'Backup belum berhasil. Update dihentikan agar data tetap aman.';
  end;
end;
