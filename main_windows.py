#!/usr/bin/env python3
"""
Version Windows du serveur de monitoring de caméras
Optimisé pour fonctionner directement avec Python sur Windows
"""
import os
import sys
import logging
from pathlib import Path

# Ajouter le répertoire courant au PYTHONPATH
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

# Configuration pour Windows
os.environ.setdefault('SESSION_SECRET', 'dev-secret-key-change-in-production')
os.environ.setdefault('DATABASE_URL', 'sqlite:///monitoring_local.db')

# Configuration du logging pour Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('camera_monitoring.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Point d'entrée principal pour Windows"""
    try:
        logger.info("Démarrage du système de monitoring de caméras...")
        
        # Importer l'application Flask
        from app import app
        import routes  # Importer les routes
        
        # Configuration spécifique à Windows
        app.config['DEBUG'] = False  # Désactiver le debug pour éviter les erreurs
        app.config['ENV'] = 'production'
        
        print("=" * 60)
        print("   SYSTÈME DE MONITORING DE CAMÉRAS")
        print("=" * 60)
        print()
        print("🔗 Serveur démarré sur: http://localhost:5000")
        print("📧 Admin par défaut: admin / admin123")
        print("⚠️  IMPORTANT: Changez le mot de passe admin !")
        print()
        print("Appuyez sur Ctrl+C pour arrêter le serveur")
        print("=" * 60)
        
        # Lancer le serveur Flask
        app.run(
            host='127.0.0.1',  # Localhost seulement pour la sécurité
            port=5000,
            debug=False,        # Désactiver debug pour éviter les conflits
            use_reloader=False, # Éviter les problèmes de rechargement sur Windows
            threaded=True       # Support multi-thread
        )
        
    except KeyboardInterrupt:
        logger.info("Arrêt du serveur demandé par l'utilisateur")
        print("\n\n✅ Serveur arrêté proprement")
        
    except ImportError as e:
        logger.error(f"Erreur d'importation: {e}")
        print(f"\n❌ ERREUR: Impossible d'importer les modules requis")
        print(f"Détails: {e}")
        print("\nSolutions possibles:")
        print("1. Vérifiez que vous êtes dans le bon répertoire")
        print("2. Exécutez 'install_windows.bat' pour installer les dépendances")
        print("3. Activez l'environnement virtuel: venv\\Scripts\\activate")
        input("\nAppuyez sur Entrée pour continuer...")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage: {e}")
        print(f"\n❌ ERREUR: {e}")
        print("\nVérifiez les logs dans 'camera_monitoring.log' pour plus de détails")
        input("\nAppuyez sur Entrée pour continuer...")
        sys.exit(1)

if __name__ == '__main__':
    main()