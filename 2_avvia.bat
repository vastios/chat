@echo off
chcp 65001 >nul
title Chat Locale AI
cd /d "%~dp0"

rem -- Controlla se Ollama e' attivo; se no lo avvia ridotto a icona
curl -s -o nul http://localhost:11434 >nul 2>nul
if errorlevel 1 (
    echo Avvio di Ollama in background...
    start "Ollama" /min cmd /c "ollama serve"
    timeout /t 5 /nobreak >nul
)

if not exist venv (
    echo Ambiente non ancora installato: avvia prima "1_installazione.bat"
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo.
echo   Chat Locale AI si apre nel browser:  http://localhost:7860
echo   Per chiudere tutto: chiudi questa finestra.
echo.
python -m backend.app
pause
