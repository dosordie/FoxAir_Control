@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Python-Pakete pruefen/installieren ...
py -m pip install -r requirements.txt || goto :err
py -m pip install -r requirements-build.txt || goto :err

echo [2/3] Portable EXE mit PyInstaller bauen ...
py -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "FoxAir_Phnix_Control" ^
  --icon "app_icon.ico" ^
  --add-data "data;data" ^
  --add-data "assets;assets" ^
  --add-data "app_icon.png;." ^
  --add-data "app_icon.ico;." ^
  --add-data "docs\public;docs\public" ^
  --collect-submodules keyring ^
  --hidden-import keyring.backends.Windows ^
  --hidden-import keyring.backends.null ^
  foxair_phnix_control.py || goto :err

echo [3/3] Portable ZIP-Ordner vorbereiten ...
if exist "dist\FoxAir_Phnix_Control_Portable" rmdir /s /q "dist\FoxAir_Phnix_Control_Portable"
mkdir "dist\FoxAir_Phnix_Control_Portable"
xcopy /e /i /y "dist\FoxAir_Phnix_Control" "dist\FoxAir_Phnix_Control_Portable\FoxAir_Phnix_Control" >nul
copy /y README.md "dist\FoxAir_Phnix_Control_Portable\" >nul
copy /y LICENSE "dist\FoxAir_Phnix_Control_Portable\" >nul
copy /y PUBLIC_WARNING.txt "dist\FoxAir_Phnix_Control_Portable\" >nul
copy /y CHANGELOG.md "dist\FoxAir_Phnix_Control_Portable\" >nul

echo.
echo Fertig: dist\FoxAir_Phnix_Control_Portable\FoxAir_Phnix_Control\FoxAir_Phnix_Control.exe
goto :eof

:err
echo.
echo FEHLER beim Build.
pause
exit /b 1
