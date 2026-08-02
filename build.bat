@echo off
setlocal
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -r requirements.txt pyinstaller -q
if errorlevel 1 goto :fail

echo Building WindowsCleaner.exe ...
python -m PyInstaller --noconfirm --clean windowscleaner.spec
if errorlevel 1 goto :fail

echo.
echo Done.
echo Distribute this file:
echo   dist\WindowsCleaner.exe
echo.
echo Tip: zip it as WindowsCleaner-portable.zip for sharing.
echo Recipients: double-click the EXE (no Python install needed).
echo For full cleanup they should Accept UAC when asked to elevate.
goto :eof

:fail
echo Build failed.
exit /b 1
