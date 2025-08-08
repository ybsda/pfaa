#!/usr/bin/env python3
"""
Démarrage simplifié pour Windows - Version sans erreurs
Résout le problème de connexion localhost refusée
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def setup_environment():
    """Configuration de l'environnement Windows"""
    # Variables d'environnement essentielles
    os.environ['SESSION_SECRET'] = 'windows-secret-key-123'
    os.environ['DATABASE_URL'] = 'sqlite:///monitoring_windows.db'
    os.environ['FLASK_ENV'] = 'production'
    os.environ['FLASK_DEBUG'] = '0'
    
    # Désactiver les fonctionnalités problématiques
    os.environ['DISABLE_SCHEDULER'] = '1'
    os.environ['DISABLE_CAMERA_STREAMS'] = '1'
    
    print("✓ Configuration Windows appliquée")

def check_dependencies():
    """Vérifier les dépendances essentielles"""
    required = ['flask', 'flask_sqlalchemy', 'flask_login', 'werkzeug']
    missing = []
    
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module.replace('_', '-'))
    
    if missing:
        print(f"❌ Modules manquants: {', '.join(missing)}")
        print("Exécutez: install_simple_windows.bat")
        return False
    
    print("✓ Toutes les dépendances sont présentes")
    return True

def start_flask_app():
    """Démarrer l'application Flask de manière sécurisée"""
    try:
        # Configuration du chemin
        current_dir = Path(__file__).parent.absolute()
        sys.path.insert(0, str(current_dir))
        
        print("Importation de l'application...")
        from app import app
        
        # Importer les routes sans erreur
        try:
            import routes
            print("✓ Routes chargées")
        except ImportError as e:
            print(f"⚠️ Erreur routes: {e}")
        
        # Configuration pour Windows
        app.config.update({
            'DEBUG': False,
            'TESTING': False,
            'ENV': 'production'
        })
        
        print("=" * 50)
        print("  MONITORING CAMERAS - WINDOWS")
        print("=" * 50)
        print("🌐 URL: http://127.0.0.1:5000")
        print("👤 Admin: admin / admin123")
        print("🔧 Mode: Production Windows")
        print("=" * 50)
        print("Serveur en cours de démarrage...")
        
        # Petit délai pour l'affichage
        time.sleep(2)
        
        # Démarrer avec paramètres Windows optimisés
        app.run(
            host='127.0.0.1',     # Localhost uniquement
            port=5000,            # Port standard
            debug=False,          # Pas de debug
            use_reloader=False,   # Pas de rechargement
            threaded=True,        # Multi-thread
            passthrough_errors=True  # Afficher les erreurs
        )
        
    except ImportError as e:
        print(f"❌ Erreur d'importation: {e}")
        print("\nSolutions:")
        print("1. Exécutez: install_simple_windows.bat")
        print("2. Vérifiez que vous êtes dans le bon dossier")
        return False
        
    except OSError as e:
        if "Address already in use" in str(e):
            print("❌ Le port 5000 est déjà utilisé")
            print("Solution: Fermez les autres applications sur le port 5000")
        else:
            print(f"❌ Erreur réseau: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Point d'entrée principal"""
    print("Système de Monitoring Caméras - Windows")
    print("Démarrage sécurisé...\n")
    
    # Vérifications préliminaires
    setup_environment()
    
    if not check_dependencies():
        input("\nAppuyez sur Entrée pour quitter...")
        return
    
    print("Démarrage de l'application Flask...\n")
    
    try:
        start_flask_app()
    except KeyboardInterrupt:
        print("\n\n✅ Serveur arrêté par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        input("Appuyez sur Entrée pour quitter...")

if __name__ == '__main__':
    main()