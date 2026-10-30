@echo off
chcp 65001 >nul
title Chat Locale AI - Installazione (solo la prima volta)
cd /d "%~dp0"

echo.
echo  ============================================
echo   Chat Locale AI - INSTALLAZIONE
echo  ============================================
echo.

echo [1/4] Controllo di Python...
python --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo   X Python non trovato!
    echo   1) Installalo da https://www.python.org/downloads/
    echo   2) Nella prima schermata spunta "Add python.exe to PATH"
    echo   3) Riavvia questo file
    echo.
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] Creo l'ambiente virtuale (venv)...
if not exist venv (
    python -m venv venv
    if errorlevel 1 (
        echo   X Errore nella creazione del venv.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat

echo.
echo [3/4] Installo le librerie (flask, pydantic, requests)...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo   X Errore nell'installazione delle librerie.
    pause
    exit /b 1
)

echo.
echo [4/4] Controllo di Ollama...
where ollama >nul 2>nul
if errorlevel 1 (
    echo.
    echo   X Ollama non trovato!
    echo   1) Scaricalo da https://ollama.com/download/windows
    echo   2) Installalo (basta premere Avanti)
    echo   3) Riavvia questo file
    echo.
    pause
    exit /b 1
)

echo.
echo  Ora scarico i due modelli IA (serve una sola volta).
echo  - Attore:   qwen2.5:7b-instruct-q4_K_M  (~4,7 GB)
echo  - Archivista: qwen2.5:3b-instruct-q4_K_M  (~1,9 GB)
echo  Puoi lasciare il PC lavorare: ci mette da 10 a 40 minuti.
echo.
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5:3b-instruct-q4_K_M

echo.
echo  ============================================
echo   INSTALLAZIONE COMPLETATA
echo   Da adesso avvia solo "2_avvia.bat"
echo  ============================================
echo.
pause
