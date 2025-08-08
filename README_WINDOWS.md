# Système de Monitoring Caméras - Installation Windows

## Installation Rapide

### Option 1 : Installation Simple (RECOMMANDÉE) ⭐
1. **Double-cliquez sur `install_simple_windows.bat`**
2. Attendez l'installation automatique
3. Lancez avec `python start_windows.py`
   - **Cette version évite les erreurs de dépendances**

### Option 2 : Installation Automatique Avancée
1. Double-cliquez sur `install_windows.bat`
2. Suivez les instructions à l'écran
3. Double-cliquez sur `launch_windows.bat` pour démarrer

### Option 3 : Démarrage Ultra-Rapide
1. Double-cliquez sur `quick_start.bat`
   - Installe automatiquement les dépendances si nécessaire
   - Lance directement le serveur

### Option 3 : Installation Manuelle

#### Prérequis
- Python 3.8+ installé sur Windows
- Accès internet pour télécharger les dépendances

#### Étapes
```cmd
# 1. Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements_windows.txt

# 3. Lancer l'application
python start_windows.py
```

## Utilisation

### Accès à l'application
- URL : http://localhost:5000
- Utilisateur admin par défaut : `admin`
- Mot de passe admin par défaut : `admin123`

⚠️ **IMPORTANT** : Changez le mot de passe administrateur après la première connexion !

### Fonctionnalités

#### Pour les Administrateurs
- Gestion des clients et utilisateurs
- Vue d'ensemble de tous les équipements
- Approbation/Refus des comptes clients
- Gestion globale des alertes
- Administration du système

#### Pour les Clients
- Gestion de leurs équipements uniquement
- Visualisation de l'historique de leurs équipements
- Réception d'alertes par email
- Tableau de bord personnalisé

### Notifications Email
Pour activer les notifications email :
1. Créez un compte SendGrid
2. Obtenez votre clé API
3. Modifiez le fichier `.env` :
   ```
   SENDGRID_API_KEY=votre_clé_api_sendgrid
   FROM_EMAIL=votre-email@domaine.com
   ```

## Configuration Avancée

### Base de Données
Par défaut, le système utilise SQLite (`monitoring_local.db`).

Pour utiliser PostgreSQL, modifiez dans `.env` :
```
DATABASE_URL=postgresql://user:password@localhost/camera_monitoring
```

### Variables d'Environnement
Fichier `.env` :
```
SESSION_SECRET=votre-clé-secrète-très-longue-et-complexe
DATABASE_URL=sqlite:///monitoring_local.db
SENDGRID_API_KEY=votre_clé_sendgrid
FROM_EMAIL=no-reply@votre-domaine.com
```

## API pour les Équipements

### Endpoint de Ping
Les caméras/DVR peuvent envoyer des pings au système :

```http
POST /api/ping
Content-Type: application/json

{
    "ip": "192.168.1.100",
    "equipement_id": 1,
    "response_time": 50,
    "message": "Ping successful"
}
```

### Intégration DVR/Caméras
Configurez vos équipements pour envoyer des requêtes HTTP à :
- URL : http://votre-serveur:5000/api/ping
- Méthode : POST
- Format : JSON
- Fréquence recommandée : 60 secondes

## Dépannage

### Erreurs Communes

#### "Module not found" ou erreurs de packages
```cmd
# Solution 1 : Utiliser l'installateur simple
install_simple_windows.bat

# Solution 2 : Installation manuelle
pip install flask flask-sqlalchemy flask-login werkzeug
pip install requests sendgrid apscheduler

# Solution 3 : En cas de conflit
pip uninstall -y flask flask-sqlalchemy
pip install --no-cache-dir flask flask-sqlalchemy
```

#### Erreur "charset_normalizer" ou "urllib3"
```cmd
# Solution : Installation séparée
pip install --upgrade pip setuptools wheel
pip install --no-deps flask flask-sqlalchemy flask-login
pip install requests sendgrid apscheduler
```

#### "Port 5000 already in use"
- Fermer les autres applications utilisant le port 5000
- Ou modifier le port dans `start_windows.py`

#### "Database locked"
- Fermer complètement l'application
- Supprimer le fichier `monitoring_local.db`
- Relancer l'application

### Logs
- Les logs sont sauvegardés dans `camera_monitoring.log`
- Console Windows affiche les messages en temps réel

## Support

### Structure des Fichiers
```
├── app.py                      # Application Flask principale
├── models.py                   # Modèles de base de données
├── routes.py                   # Routes et logique métier  
├── camera_stream.py            # Service de streaming RTSP/IP
├── email_service.py            # Service d'envoi d'emails
├── scheduler.py                # Tâches planifiées
├── templates/                  # Templates HTML
├── static/                     # CSS, JS, images
├── install_simple_windows.bat  # Installation simple (RECOMMANDÉE)
├── install_windows.bat         # Installation complète
├── launch_windows.bat          # Lancement standard
├── quick_start.bat             # Démarrage rapide
├── start_windows.py            # Script Python de démarrage
├── main_windows.py             # Version Windows optimisée
└── requirements_windows.txt    # Dépendances Python
```

### Fonctionnalités Nouvelles - Streaming RTSP/IP 📹

#### Configuration de Caméras
- **Support RTSP** : Connexion directe aux caméras IP
- **Authentification** : Nom d'utilisateur et mot de passe
- **Résolutions** : 640x480, 800x600, 1024x768, 1280x720
- **Qualité ajustable** : Low, Medium, High
- **FPS configurables** : 1-30 images/seconde

#### URLs RTSP Communes
```
# Hikvision
rtsp://username:password@192.168.1.100:554/Streaming/Channels/101

# Dahua  
rtsp://username:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0

# Axis
rtsp://username:password@192.168.1.100:554/axis-media/media.amp

# Generic
rtsp://username:password@192.168.1.100:554/stream1
```

### Fonctionnalités Techniques
- **Authentification** : Système local avec hashage MD5
- **Base de données** : SQLAlchemy avec SQLite/PostgreSQL
- **Planificateur** : APScheduler pour les tâches automatiques
- **Emails** : SendGrid pour les notifications
- **Interface** : Bootstrap 5 avec thème sombre
- **API** : Endpoints REST pour l'intégration d'équipements

### Sécurité
- Changer immédiatement le mot de passe admin
- Utiliser HTTPS en production
- Configurer un pare-feu approprié
- Sauvegarder régulièrement la base de données