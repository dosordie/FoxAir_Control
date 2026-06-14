@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\FoxAir_Phnix_Control\FoxAir_Phnix_Control.exe" (
  echo EXE fehlt. Erst build_windows_exe.bat ausfuehren.
  pause
  exit /b 1
)

set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 nicht gefunden.
  echo Download: https://jrsoftware.org/isinfo.php
  pause
  exit /b 1
)

%ISCC% "installer\FoxAir_Phnix_Control.iss" || goto :err

echo.
echo Fertig: installer\Output\
goto :eof

:err
echo Fehler beim Installer-Build.
pause
exit /b 1
