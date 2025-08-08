@echo off
echo ====================================================
echo   DEMARRAGE SIMPLE - MONITORING CAMERAS  
echo ====================================================
echo.

:: Vérifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Python non installé
    echo Téléchargez depuis: https://python.org
    pause
    exit /b 1
)

:: Aller dans le répertoire du script
cd /d "%~dp0"

echo Répertoire: %CD%
echo.

:: Lancer le script Python simplifié
echo Démarrage du serveur...
python run_windows_simple.py

echo.
echo Serveur arrêté.
pause