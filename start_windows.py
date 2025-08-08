#!/usr/bin/env python3
"""
Script de démarrage simplifié pour Windows
Lance le système sans configuration complexe
"""
import os
import sys
import subprocess
from pathlib import Path

def check_python():
    """Vérifier si Python est disponible"""
    try:
        result = subprocess.run([sys.executable, '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"✓ Python détecté: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError:
        print("❌ Python non trouvé dans le PATH")
        return False

def install_requirements():
    """Installer les dépendances si nécessaires"""
    core_requirements = [
        'flask', 'flask_sqlalchemy', 'flask_login', 'werkzeug',
        'sendgrid', 'apscheduler', 'requests'
    ]
    
    optional_requirements = [
        'cv2',  # opencv-python
        'PIL',  # pillow
    ]
    
    print("Vérification des dépendances core...")
    missing_core = []
    
    for package in core_requirements:
        try:
            __import__(package)
        except ImportError:
            missing_core.append(package.replace('_', '-'))
    
    if missing_core:
        print(f"Installation des packages essentiels: {', '.join(missing_core)}")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing_core, 
                         check=True)
            print("✓ Dépendances core installées")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur installation core: {e}")
            # Essayer installation individuelle
            for pkg in missing_core:
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], 
                                 check=True)
                    print(f"✓ {pkg} installé")
                except subprocess.CalledProcessError:
                    print(f"⚠️ {pkg} échoué - continuez sans ce package")
    else:
        print("✓ Toutes les dépendances core présentes")
    
    # Vérification optionnelle (pas d'échec si absent)
    print("Vérification des dépendances optionnelles...")
    for package in optional_requirements:
        try:
            __import__(package)
            print(f"✓ {package} disponible")
        except ImportError:
            print(f"⚠️ {package} non disponible - fonctionnalités limitées")
    
    return True

def setup_environment():
    """Configurer l'environnement"""
    # Variables d'environnement par défaut
    os.environ.setdefault('SESSION_SECRET', 'dev-secret-key-windows')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///monitoring_local.db')
    os.environ.setdefault('FLASK_ENV', 'development')
    
    print("✓ Variables d'environnement configurées")

def main():
    """Point d'entrée principal"""
    print("=" * 50)
    print("  SYSTÈME DE MONITORING CAMÉRAS - Windows")
    print("=" * 50)
    print()
    
    # Vérifications préliminaires
    if not check_python():
        input("Appuyez sur Entrée pour quitter...")
        sys.exit(1)
    
    if not install_requirements():
        input("Appuyez sur Entrée pour quitter...")
        sys.exit(1)
    
    setup_environment()
    
    try:
        # Importer et lancer l'application
        print("\nDémarrage du serveur...")
        print("🌐 URL: http://localhost:5000")
        print("👤 Admin: admin / admin123")
        print("\nAppuyez sur Ctrl+C pour arrêter")
        print("=" * 50)
        
        from app import app
        app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)
        
    except KeyboardInterrupt:
        print("\n\n✅ Serveur arrêté")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        input("Appuyez sur Entrée pour quitter...")

if __name__ == '__main__':
    main()