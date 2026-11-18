@echo off
rem Avvia MythoGraph in locale e apre il browser su http://localhost:8000
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Prima esecuzione: creo l'ambiente virtuale e installo le dipendenze...
    python -m venv .venv || goto :errore
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :errore
    ".venv\Scripts\python.exe" -m pip install -q -e . || goto :errore
)

if not exist "data\generated\mythograph.trig" (
    echo Genero il grafo...
    ".venv\Scripts\python.exe" -m mythograph.build || goto :errore
)

echo Avvio del server su http://localhost:8000  (chiudi questa finestra per fermarlo)
start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8000"
".venv\Scripts\python.exe" -m uvicorn mythograph.web.app:app --port 8000
goto :eof

:errore
echo.
echo Qualcosa e' andato storto. Controlla che Python 3.11+ sia installato.
pause
