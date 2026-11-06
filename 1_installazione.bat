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

echo [1/3] Creo l'ambiente virtuale...
if not exist venv python -m venv venv
call venv\Scripts\activate.bat

echo [2/3] Aggiorno pip...
python -m pip install --upgrade pip --quiet

echo [3/3] Installo Streamlit e requests...
pip install -r requirements.txt --quiet

echo.
echo Controllo LM Studio (porta 1234)...
curl -s -m 3 http://localhost:1234/v1/models >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ATTENZIONE] Il server di LM Studio non risponde: non blocca
    echo l'installazione, ma serve per far parlare i personaggi.
    echo.
    echo   1. Installa LM Studio da https://lmstudio.ai
    echo   2. Cerca e scarica un modello (consigliato "Qwen2.5 7B Instruct",
    echo      quantizzazione q4_K_M, circa 4,7 GB)
    echo   3. Caricalo e premi Start Server nella scheda Developer
    echo.
)

echo ============================================
echo   Installazione completata!
echo   Avvia ora "2_avvia.bat"
echo ============================================
pause
