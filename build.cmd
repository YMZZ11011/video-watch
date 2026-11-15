@echo off
rem Builds dist\Video Watch.exe (the app) and dist\Video Watch Setup.exe (the installer to hand to other people;
rem it carries the app inside it).
rem One-time setup:  py -3.12 -m venv .build\venv  then  .build\venv\Scripts\pip install pyinstaller anthropic
cd /d "%~dp0"
if not exist ".build\venv\Scripts\pyinstaller.exe" (
  echo Build tools missing. Run once:  py -3.12 -m venv .build\venv  and  .build\venv\Scripts\pip install pyinstaller anthropic
  exit /b 1
)
".build\venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed --name "Video Watch" --icon "%~dp0assets\icon.ico" --add-data "%~dp0ui;ui" --paths "%~dp0watchlib" --hidden-import frames --hidden-import download --hidden-import transcribe --hidden-import whisper --hidden-import config --workpath ".build\work" --specpath ".build" --distpath dist app.py || exit /b 1
".build\venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed --name "Video Watch Setup" --icon "%~dp0assets\icon.ico" --add-data "%~dp0dist\Video Watch.exe;payload" --add-data "%~dp0assets\icon.ico;payload" --workpath ".build\work-setup" --specpath ".build" --distpath dist installer.py || exit /b 1
echo.
echo Built dist\Video Watch.exe and dist\Video Watch Setup.exe
