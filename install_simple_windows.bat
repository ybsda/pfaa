@echo off
echo ====================================================
echo   INSTALLATION SIMPLE - MONITORING CAMERAS
echo ====================================================
echo.

:: Vérifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Python non trouvé
    echo Installez Python depuis https://python.org
    pause
    exit /b 1
)

echo ✓ Python détecté
python --version

:: Installation simple des dépendances essentielles
echo.
echo Installation des packages essentiels...

:: Flask et base
pip install flask flask-sqlalchemy flask-login werkzeug
if %errorlevel% neq 0 (
    echo ERREUR lors de l'installation Flask
    pause
    exit /b 1
)

:: Services
pip install requests sendgrid apscheduler
if %errorlevel% neq 0 (
    echo ERREUR lors de l'installation des services
    pause
    exit /b 1
)

:: Utilitaires
pip install python-dotenv email-validator
if %errorlevel% neq 0 (
    echo Attention: utilitaires non installés
)

:: Base de données (optionnel)
pip install psycopg2-binary
if %errorlevel% neq 0 (
    echo Note: PostgreSQL non installé, utilisation SQLite
)

echo.
echo Configuration de base...
if not exist ".env" (
    echo SESSION_SECRET=windows-secret-key-changez-la > .env
    echo DATABASE_URL=sqlite:///monitoring_windows.db >> .env
    echo FROM_EMAIL=admin@votre-systeme.local >> .env
    echo ✓ Configuration créée
)

echo.
echo ====================================================
echo   INSTALLATION SIMPLE TERMINÉE !
echo ====================================================
echo.
echo Pour lancer: python start_windows.py
echo Ou utilisez: launch_windows.bat
echo.
echo URL: http://localhost:5000
echo Admin: admin / admin123
echo.
pause