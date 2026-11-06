@echo off
chcp 65001 >nul
title Chat Personaggi
cd /d "%~dp0"

if not exist venv (
    echo [ERRORE] Manca l'ambiente virtuale: lancia prima "1_installazione.bat".
    pause
    exit /b 1
)

rem Se Ollama non e in esecuzione, lo avvio ridotto a icona
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    echo Avvio Ollama in background...
    start "Ollama" /MIN cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
)

call venv\Scripts\activate.bat
echo Apro Chat Personaggi nel browser (Ctrl+C qui per fermare)...
streamlit run app.py --server.headless true
pause
