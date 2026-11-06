@echo off
chcp 65001 >nul
title Chat Personaggi
cd /d "%~dp0"

if not exist venv (
    echo [ERRORE] Manca l'ambiente virtuale: lancia prima "1_installazione.bat".
    pause
    exit /b 1
)

rem Se il server di LM Studio non risponde, avviso ma parto comunque
curl -s -m 3 http://localhost:1234/v1/models >nul 2>nul
if errorlevel 1 (
    echo [ATTENZIONE] LM Studio non risponde sulla porta 1234.
    echo Apri LM Studio, carica un modello e premi Start Server
    echo nella scheda Developer, altrimenti i personaggi non potranno
    echo rispondere.
    echo.
)

call venv\Scripts\activate.bat
echo Apro Chat Personaggi nel browser (Ctrl+C qui per fermare)...
streamlit run app.py --server.headless true
pause
