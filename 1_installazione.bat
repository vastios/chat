@echo off
chcp 65001 >nul
title Chat Personaggi - Installazione
cd /d "%~dp0"

echo ============================================
echo   Chat Personaggi - installazione (1/2)
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRORE] Python non trovato.
    echo Installa Python da https://www.python.org/downloads/
    echo Durante l'installazione spunta "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Creo l'ambiente virtuale...
if not exist venv python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Aggiorno pip...
python -m pip install --upgrade pip --quiet

echo [3/4] Installo Streamlit e requests...
pip install -r requirements.txt --quiet

echo [4/4] Controllo Ollama...
where ollama >nul 2>nul
if errorlevel 1 (
    echo [ERRORE] Ollama non trovato.
    echo Installalo da https://ollama.com e riavvia questo file.
    pause
    exit /b 1
)

echo Scarico il modello attore (una volta sola, circa 4,7 GB)...
ollama pull qwen2.5:7b-instruct-q4_K_M
echo Scarico il modello archivista (circa 2,3 GB)...
ollama pull qwen2.5:3b-instruct-q4_K_M

echo.
echo ============================================
echo   Installazione completata!
echo   Avvia ora "2_avvia.bat"
echo ============================================
pause
