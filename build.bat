@echo off
rem Costruisce dist\IstatUploader.exe su QUESTO PC Windows.
rem E' la strada di riserva: quella normale e' scaricarlo da GitHub
rem (vedi BUILD_WINDOWS.md). Serve Python 3.12 da python.org, installato con
rem la spunta "Add python.exe to PATH". Basta un doppio clic su questo file.
setlocal
cd /d "%~dp0"

echo.
echo === Istat Uploader: costruzione dell'eseguibile ===
echo.

set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (py -3 --version >nul 2>&1 && set "PY=py -3")
if not defined PY (python --version >nul 2>&1 && set "PY=python")
if not defined PY goto :nopython
echo Uso: %PY%
%PY% --version

echo.
echo [1/4] Preparo un ambiente pulito in .venv-build ...
if exist .venv-build rmdir /s /q .venv-build
%PY% -m venv .venv-build || goto :errore
set "VPY=.venv-build\Scripts\python.exe"
%VPY% -m pip install --upgrade pip --quiet || goto :errore

echo [2/4] Installo le versioni fissate in requirements-dev.txt ...
%VPY% -m pip install -r requirements-dev.txt --quiet || goto :errore

echo [3/4] Controlli: se non passano NON costruisco ...
%VPY% -m ruff check . || goto :errore
%VPY% -m pytest -q || goto :errore

echo [4/4] Costruisco l'eseguibile ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%VPY% -m PyInstaller IstatUploader.spec --noconfirm --clean || goto :errore
if not exist dist\IstatUploader.exe goto :errore

rem L'eseguibile appena fatto controlla di avere tutto dentro (Selenium,
rem Selenium Manager, la finestra). Non apre niente.
start "" /wait dist\IstatUploader.exe --autoverifica dist\autoverifica.txt
type dist\autoverifica.txt
findstr /c:"tutto dentro" dist\autoverifica.txt >nul || goto :errore
rem E la finestra vera: si apre un attimo e si chiude da sola.
start "" /wait dist\IstatUploader.exe --autoverifica-finestra dist\finestra.txt
type dist\finestra.txt
findstr /c:"interfaccia pronta" dist\finestra.txt >nul || goto :errore

echo.
echo FATTO: dist\IstatUploader.exe
echo Copialo dove vuoi (anche il Desktop) e aprilo con un doppio clic.
echo.
pause
exit /b 0

:nopython
echo.
echo Non trovo Python. Installa Python 3.12 da https://www.python.org/downloads/
echo e nella prima schermata dell'installazione metti la spunta su
echo "Add python.exe to PATH". Poi chiudi questa finestra e rifai doppio clic.
echo.
pause
exit /b 1

:errore
echo.
echo Qualcosa e' andato storto: leggi le righe qui sopra.
echo Se non e' chiaro, fai una foto a questa finestra e mandala.
echo.
pause
exit /b 1
