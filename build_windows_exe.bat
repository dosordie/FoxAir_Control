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
  --name "FoxAir_Phnix_Controll" ^
  --icon "app_icon.ico" ^
  --add-data "foxair_phnix_registers.json;." ^
  --add-data "foxair_phnix_knowledge.json;." ^
  --add-data "app_icon.png;." ^
  --add-data "app_icon.ico;." ^
  --add-data "docs;docs" ^
  --add-data "tools;tools" ^
  foxair_phnix_controll.py || goto :err

echo [3/3] Portable ZIP-Ordner vorbereiten ...
if exist "dist\FoxAir_Phnix_Controll_Portable" rmdir /s /q "dist\FoxAir_Phnix_Controll_Portable"
mkdir "dist\FoxAir_Phnix_Controll_Portable"
xcopy /e /i /y "dist\FoxAir_Phnix_Controll" "dist\FoxAir_Phnix_Controll_Portable\FoxAir_Phnix_Controll" >nul
copy /y README.md "dist\FoxAir_Phnix_Controll_Portable\" >nul
copy /y LICENSE "dist\FoxAir_Phnix_Controll_Portable\" >nul
copy /y PUBLIC_WARNING.txt "dist\FoxAir_Phnix_Controll_Portable\" >nul
copy /y CHANGELOG.md "dist\FoxAir_Phnix_Controll_Portable\" >nul

echo.
echo Fertig: dist\FoxAir_Phnix_Controll_Portable\FoxAir_Phnix_Controll\FoxAir_Phnix_Controll.exe
goto :eof

:err
echo.
echo FEHLER beim Build.
pause
exit /b 1
