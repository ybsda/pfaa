import logging
import os
from datetime import datetime, timedelta
from flask import render_template, request, jsonify, flash, redirect, url_for, session, Response
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import Client, Equipement, HistoriquePing, Alerte, User
from email_service import email_service

logger = logging.getLogger(__name__)

# Importer le gestionnaire de caméras seulement si les streams sont activés
if os.environ.get('DISABLE_CAMERA_STREAMS') != '1':
    try:
        from camera_stream import camera_manager, generate_stream_response
    except ImportError as e:
        logger.warning(f"Camera streaming non disponible: {e}")
        camera_manager = None
else:
    camera_manager = None

# Routes d'authentification
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nom_utilisateur = request.form.get('nom_utilisateur')
        mot_de_passe = request.form.get('mot_de_passe')
        
        if not nom_utilisateur or not mot_de_passe:
            flash('Veuillez saisir votre nom d\'utilisateur et mot de passe.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(nom_utilisateur=nom_utilisateur, actif=True).first()
        
        if user and user.check_password(mot_de_passe):
            # Vérifier si le compte est approuvé
            if user.statut == 'en_attente':
                flash('Votre compte est en attente d\'approbation par un administrateur.', 'warning')
                return render_template('login.html')
            elif user.statut == 'refuse':
                flash('Votre demande de compte a été refusée. Contactez un administrateur.', 'error')
                return render_template('login.html')
            
            login_user(user)
            user.update_last_login()
            flash(f'Connexion réussie ! Bienvenue {user.nom_complet or user.nom_utilisateur}.', 'success')
            
            # Redirection vers la page demandée ou dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash('Vous avez été déconnecté avec succès.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Page d'inscription pour les clients (avec validation admin)"""
    if request.method == 'POST':
        nom_utilisateur = request.form.get('nom_utilisateur')
        email = request.form.get('email')
        mot_de_passe = request.form.get('mot_de_passe')
        nom_complet = request.form.get('nom_complet')
        nom_entreprise = request.form.get('nom_entreprise')
        adresse = request.form.get('adresse')
        telephone = request.form.get('telephone')
        
        if not all([nom_utilisateur, email, mot_de_passe, nom_entreprise]):
            flash('Tous les champs obligatoires doivent être remplis.', 'error')
            return render_template('register.html')
        
        # Vérifier si l'utilisateur existe déjà
        if User.query.filter_by(nom_utilisateur=nom_utilisateur).first():
            flash('Ce nom d\'utilisateur existe déjà.', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Cette adresse email est déjà utilisée.', 'error')
            return render_template('register.html')
        
        try:
            # Créer d'abord le client
            nouveau_client = Client()
            nouveau_client.nom = nom_entreprise
            nouveau_client.email = email
            nouveau_client.adresse = adresse
            nouveau_client.telephone = telephone
            
            db.session.add(nouveau_client)
            db.session.flush()  # Pour obtenir l'ID du client
            
            # Créer l'utilisateur lié au client
            nouveau_user = User()
            nouveau_user.nom_utilisateur = nom_utilisateur
            nouveau_user.email = email
            nouveau_user.nom_complet = nom_complet
            nouveau_user.role = 'client'
            nouveau_user.statut = 'en_attente'
            nouveau_user.client_id = nouveau_client.id
            nouveau_user.set_password(mot_de_passe)
            
            db.session.add(nouveau_user)
            db.session.commit()
            
            flash('Votre demande de compte a été soumise avec succès ! Un administrateur va examiner votre demande et vous recevrez un email de confirmation.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erreur lors de la création du compte client: {e}')
            flash('Une erreur est survenue lors de la création du compte.', 'error')
    
    return render_template('register.html')

@app.route('/')
@login_required
def dashboard():
    """Page d'accueil avec vue d'ensemble du système"""
    try:
        # Statistiques globales ou filtrées par client selon le rôle
        if current_user.role == 'admin':
            total_clients = Client.query.filter_by(actif=True).count()
            total_equipements = Equipement.query.filter_by(actif=True).count()
            equipements = Equipement.query.filter_by(actif=True).all()
            clients = Client.query.filter_by(actif=True).all()
        else:
            # Pour les clients, afficher seulement leurs données
            total_clients = 1 if current_user.client_id else 0
            total_equipements = Equipement.query.filter_by(client_id=current_user.client_id, actif=True).count()
            equipements = Equipement.query.filter_by(client_id=current_user.client_id, actif=True).all()
            clients = [current_user.client] if current_user.client else []
        
        # Compter les équipements en ligne et hors ligne
        equipements_en_ligne = 0
        equipements_hors_ligne = 0
        
        for eq in equipements:
            if eq.est_en_ligne:
                equipements_en_ligne += 1
            else:
                equipements_hors_ligne += 1
        
        # Alertes non lues (filtrées par client si nécessaire)
        if current_user.role == 'admin':
            alertes_non_lues = Alerte.query.filter_by(lue=False).count()
            dernieres_alertes = Alerte.query.order_by(Alerte.timestamp.desc()).limit(10).all()
        else:
            # Pour les clients, ne montrer que leurs alertes
            alertes_non_lues = db.session.query(Alerte).join(Equipement).filter(
                Equipement.client_id == current_user.client_id,
                Alerte.lue == False
            ).count()
            dernieres_alertes = db.session.query(Alerte).join(Equipement).filter(
                Equipement.client_id == current_user.client_id
            ).order_by(Alerte.timestamp.desc()).limit(10).all()
        
        stats = {
            'total_clients': total_clients,
            'total_equipements': total_equipements,
            'equipements_en_ligne': equipements_en_ligne,
            'equipements_hors_ligne': equipements_hors_ligne,
            'alertes_non_lues': alertes_non_lues
        }
        
        return render_template('dashboard.html', 
                             stats=stats, 
                             clients=clients,
                             dernieres_alertes=dernieres_alertes)
    except Exception as e:
        logger.error(f"Erreur dans dashboard: {e}")
        flash(f"Erreur lors du chargement du tableau de bord: {e}", "error")
        return render_template('dashboard.html', stats={}, clients=[], dernieres_alertes=[])

@app.route('/clients')
@login_required
def clients():
    """Page de gestion des clients (admin seulement)"""
    if current_user.role != 'admin':
        flash('Accès refusé : réservé aux administrateurs.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        clients_list = Client.query.filter_by(actif=True).all()
        return render_template('clients.html', clients=clients_list)
    except Exception as e:
        logger.error(f"Erreur dans clients: {e}")
        flash(f"Erreur lors du chargement des clients: {e}", "error")
        return render_template('clients.html', clients=[])

@app.route('/equipements')
@login_required
def equipements():
    """Page de gestion des équipements"""
    try:
        if current_user.role == 'admin':
            equipements_list = Equipement.query.filter_by(actif=True).all()
            clients_list = Client.query.filter_by(actif=True).all()
        else:
            # Pour les clients, afficher seulement leurs équipements
            equipements_list = Equipement.query.filter_by(client_id=current_user.client_id, actif=True).all()
            clients_list = [current_user.client] if current_user.client else []
        
        return render_template('equipements.html', equipements=equipements_list, clients=clients_list)
    except Exception as e:
        logger.error(f"Erreur dans equipements: {e}")
        flash(f"Erreur lors du chargement des équipements: {e}", "error")
        return render_template('equipements.html', equipements=[], clients=[])

@app.route('/historique')
@login_required
def historique():
    """Page d'historique des pings"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        if current_user.role == 'admin':
            historique_query = HistoriquePing.query.order_by(HistoriquePing.timestamp.desc())
        else:
            # Pour les clients, filtrer par leurs équipements
            historique_query = db.session.query(HistoriquePing).join(Equipement).filter(
                Equipement.client_id == current_user.client_id
            ).order_by(HistoriquePing.timestamp.desc())
        
        try:
            historique_pagine = historique_query.paginate(
                page=page, per_page=per_page, error_out=False
            )
        except AttributeError:
            # Fallback pour les versions plus anciennes de SQLAlchemy
            from sqlalchemy import func
            total = historique_query.count()
            historique_items = historique_query.offset((page - 1) * per_page).limit(per_page).all()
            
            class MockPagination:
                def __init__(self, items, page, per_page, total):
                    self.items = items
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = (total + per_page - 1) // per_page
                    self.has_prev = page > 1
                    self.has_next = page < self.pages
                    self.prev_num = page - 1 if self.has_prev else None
                    self.next_num = page + 1 if self.has_next else None
            
            historique_pagine = MockPagination(historique_items, page, per_page, total)
        
        return render_template('history.html', historique=historique_pagine)
    except Exception as e:
        logger.error(f"Erreur dans historique: {e}")
        flash(f"Erreur lors du chargement de l'historique: {e}", "error")
        return render_template('history.html', historique=None)

@app.route('/alertes')
@login_required
def alertes():
    """Page des alertes"""
    try:
        if current_user.role == 'admin':
            alertes_list = Alerte.query.order_by(Alerte.timestamp.desc()).all()
        else:
            # Pour les clients, filtrer par leurs équipements
            alertes_list = db.session.query(Alerte).join(Equipement).filter(
                Equipement.client_id == current_user.client_id
            ).order_by(Alerte.timestamp.desc()).all()
        
        return render_template('alerts.html', alertes=alertes_list)
    except Exception as e:
        logger.error(f"Erreur dans alertes: {e}")
        flash(f"Erreur lors du chargement des alertes: {e}", "error")
        return render_template('alerts.html', alertes=[])

# API Routes pour recevoir les pings des DVR/caméras
@app.route('/api/ping', methods=['POST'])
def recevoir_ping():
    """Endpoint pour recevoir les pings des équipements"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Données JSON requises"}), 400
        
        adresse_ip = data.get('ip')
        equipement_id = data.get('equipement_id')
        
        if not adresse_ip and not equipement_id:
            return jsonify({"error": "IP ou ID d'équipement requis"}), 400
        
        # Trouver l'équipement
        if equipement_id:
            equipement = Equipement.query.get(equipement_id)
        else:
            equipement = Equipement.query.filter_by(adresse_ip=adresse_ip, actif=True).first()
        
        if not equipement:
            logger.warning(f"Équipement non trouvé pour IP: {adresse_ip}, ID: {equipement_id}")
            return jsonify({"error": "Équipement non trouvé"}), 404
        
        # Vérifier si l'équipement était hors ligne
        etait_hors_ligne = not equipement.est_en_ligne
        
        # Mettre à jour le dernier ping
        equipement.dernier_ping = datetime.utcnow()
        
        # Enregistrer dans l'historique
        historique = HistoriquePing()
        historique.equipement_id = equipement.id
        historique.timestamp = datetime.utcnow()
        historique.statut = 'success'
        historique.reponse_ms = data.get('response_time')
        historique.message = data.get('message', 'Ping reçu avec succès')
        
        db.session.add(historique)
        
        # Créer une alerte si l'équipement revient en ligne
        if etait_hors_ligne:
            alerte = Alerte()
            alerte.equipement_id = equipement.id
            alerte.type_alerte = 'retour_en_ligne'
            alerte.message = f"L'équipement {equipement.nom} ({equipement.adresse_ip}) est revenu en ligne"
            alerte.timestamp = datetime.utcnow()
            db.session.add(alerte)
            logger.info(f"Équipement {equipement.nom} revenu en ligne")
        
        db.session.commit()
        
        logger.debug(f"Ping reçu pour {equipement.nom} ({equipement.adresse_ip})")
        
        return jsonify({
            "status": "success",
            "message": "Ping reçu",
            "equipement_id": equipement.id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du ping: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# Routes d'administration (admin seulement)
@app.route('/admin/users')
@login_required
def admin_users():
    """Page d'administration des utilisateurs (admin seulement)"""
    if current_user.role != 'admin':
        flash('Accès refusé : réservé aux administrateurs.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        users_list = User.query.filter_by(actif=True).all()
        return render_template('admin_users.html', users=users_list)
    except Exception as e:
        logger.error(f"Erreur dans admin_users: {e}")
        flash(f"Erreur lors du chargement des utilisateurs: {e}", "error")
        return render_template('admin_users.html', users=[])

@app.route('/admin/users/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    """Approuver un utilisateur (admin seulement)"""
    if current_user.role != 'admin':
        flash('Accès refusé : réservé aux administrateurs.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        user = User.query.get(user_id)
        if not user:
            flash('Utilisateur non trouvé.', 'error')
            return redirect(url_for('admin_users'))
        
        user.statut = 'approuve'
        db.session.commit()
        
        # Envoyer un email de confirmation
        if email_service:
            email_service.send_account_approval_notification(user.email, user.nom_complet or user.nom_utilisateur, approved=True)
        
        flash(f'Utilisateur {user.nom_utilisateur} approuvé avec succès.', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de l'approbation de l'utilisateur {user_id}: {e}")
        flash('Erreur lors de l\'approbation de l\'utilisateur.', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/reject', methods=['POST'])
@login_required  
def reject_user(user_id):
    """Refuser un utilisateur (admin seulement)"""
    if current_user.role != 'admin':
        flash('Accès refusé : réservé aux administrateurs.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        user = User.query.get(user_id)
        if not user:
            flash('Utilisateur non trouvé.', 'error')
            return redirect(url_for('admin_users'))
        
        user.statut = 'refuse'
        db.session.commit()
        
        # Envoyer un email de refus
        if email_service:
            email_service.send_account_approval_notification(user.email, user.nom_complet or user.nom_utilisateur, approved=False)
        
        flash(f'Utilisateur {user.nom_utilisateur} refusé.', 'info')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors du refus de l'utilisateur {user_id}: {e}")
        flash('Erreur lors du refus de l\'utilisateur.', 'error')
    
    return redirect(url_for('admin_users'))

# AJAX Routes pour les mises à jour en temps réel
@app.route('/api/stats')
@login_required
def api_stats():
    """API pour obtenir les statistiques en temps réel"""
    try:
        if current_user.role == 'admin':
            total_clients = Client.query.filter_by(actif=True).count()
            total_equipements = Equipement.query.filter_by(actif=True).count()
            equipements = Equipement.query.filter_by(actif=True).all()
        else:
            total_clients = 1 if current_user.client_id else 0
            total_equipements = Equipement.query.filter_by(client_id=current_user.client_id, actif=True).count()
            equipements = Equipement.query.filter_by(client_id=current_user.client_id, actif=True).all()
        
        equipements_en_ligne = len([eq for eq in equipements if eq.est_en_ligne])
        equipements_hors_ligne = len([eq for eq in equipements if not eq.est_en_ligne])
        
        if current_user.role == 'admin':
            alertes_non_lues = Alerte.query.filter_by(lue=False).count()
        else:
            alertes_non_lues = db.session.query(Alerte).join(Equipement).filter(
                Equipement.client_id == current_user.client_id,
                Alerte.lue == False
            ).count()
        
        return jsonify({
            'total_clients': total_clients,
            'total_equipements': total_equipements,
            'equipements_en_ligne': equipements_en_ligne,
            'equipements_hors_ligne': equipements_hors_ligne,
            'alertes_non_lues': alertes_non_lues
        })
        
    except Exception as e:
        logger.error(f"Erreur dans api_stats: {e}")
        return jsonify({'error': 'Erreur lors du chargement des statistiques'}), 500

@app.route('/api/equipements/status')
@login_required
def api_equipements_status():
    """API pour obtenir le statut des équipements en temps réel"""
    try:
        if current_user.role == 'admin':
            equipements = Equipement.query.filter_by(actif=True).all()
        else:
            equipements = Equipement.query.filter_by(client_id=current_user.client_id, actif=True).all()
        
        equipements_data = []
        for eq in equipements:
            equipements_data.append({
                'id': eq.id,
                'nom': eq.nom,
                'adresse_ip': eq.adresse_ip,
                'est_en_ligne': eq.est_en_ligne,
                'statut_texte': eq.statut_texte,
                'dernier_ping': eq.dernier_ping.isoformat() if eq.dernier_ping else None,
                'duree_depuis_dernier_ping': eq.duree_depuis_dernier_ping
            })
        
        return jsonify(equipements_data)
        
    except Exception as e:
        logger.error(f"Erreur dans api_equipements_status: {e}")
        return jsonify({'error': 'Erreur lors du chargement du statut des équipements'}), 500

# Routes pour les flux de caméras RTSP
@app.route('/camera/<int:camera_id>/stream')
@login_required
def camera_stream(camera_id):
    """Flux vidéo MJPEG pour une caméra"""
    try:
        # Vérifier si le streaming est disponible
        if camera_manager is None:
            return jsonify({"error": "Streaming de caméras non disponible"}), 503
        
        # Vérifier les permissions
        equipement = Equipement.query.get(camera_id)
        if not equipement:
            return jsonify({"error": "Caméra non trouvée"}), 404
        
        # Vérifier les permissions d'accès
        if current_user.role == 'client' and equipement.client_id != current_user.client_id:
            return jsonify({"error": "Accès refusé"}), 403
        
        # Vérifier si le streaming est activé
        if not equipement.has_stream_capability:
            return jsonify({"error": "Streaming non configuré pour cette caméra"}), 400
        
        # Démarrer le flux si pas encore actif
        if not camera_manager.get_stream(camera_id):
            if not camera_manager.start_camera_stream(equipement):
                return jsonify({"error": "Impossible de démarrer le flux"}), 500
        
        # Retourner le flux MJPEG
        return generate_stream_response(camera_id)
        
    except Exception as e:
        logger.error(f"Erreur flux caméra {camera_id}: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@app.route('/camera/<int:camera_id>/snapshot')
@login_required
def camera_snapshot(camera_id):
    """Capture instantanée d'une caméra"""
    try:
        # Vérifier si le streaming est disponible
        if camera_manager is None:
            return jsonify({"error": "Streaming de caméras non disponible"}), 503
        
        # Vérifier les permissions
        equipement = Equipement.query.get(camera_id)
        if not equipement:
            return jsonify({"error": "Caméra non trouvée"}), 404
        
        if current_user.role == 'client' and equipement.client_id != current_user.client_id:
            return jsonify({"error": "Accès refusé"}), 403
        
        if not equipement.has_stream_capability:
            return jsonify({"error": "Streaming non configuré"}), 400
        
        # Obtenir l'instantané
        jpeg_data = camera_manager.get_snapshot(camera_id)
        if jpeg_data:
            return Response(jpeg_data, mimetype='image/jpeg')
        else:
            return jsonify({"error": "Pas d'image disponible"}), 404
            
    except Exception as e:
        logger.error(f"Erreur snapshot caméra {camera_id}: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@app.route('/camera/<int:camera_id>/start_stream', methods=['POST'])
@login_required
def start_camera_stream_route(camera_id):
    """Démarre le flux d'une caméra"""
    try:
        equipement = Equipement.query.get(camera_id)
        if not equipement:
            return jsonify({"error": "Caméra non trouvée"}), 404
        
        if current_user.role == 'client' and equipement.client_id != current_user.client_id:
            return jsonify({"error": "Accès refusé"}), 403
        
        if not equipement.has_stream_capability:
            return jsonify({"error": "Streaming non configuré"}), 400
        
        success = camera_manager.start_camera_stream(equipement)
        if success:
            return jsonify({"status": "success", "message": "Flux démarré"})
        else:
            return jsonify({"error": "Impossible de démarrer le flux"}), 500
            
    except Exception as e:
        logger.error(f"Erreur démarrage flux caméra {camera_id}: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@app.route('/camera/<int:camera_id>/stop_stream', methods=['POST'])
@login_required
def stop_camera_stream_route(camera_id):
    """Arrête le flux d'une caméra"""
    try:
        equipement = Equipement.query.get(camera_id)
        if not equipement:
            return jsonify({"error": "Caméra non trouvée"}), 404
        
        if current_user.role == 'client' and equipement.client_id != current_user.client_id:
            return jsonify({"error": "Accès refusé"}), 403
        
        success = camera_manager.stop_camera_stream(camera_id)
        return jsonify({"status": "success", "stopped": success})
        
    except Exception as e:
        logger.error(f"Erreur arrêt flux caméra {camera_id}: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@app.route('/api/cameras/streams_status')
@login_required
def streams_status_api():
    """API pour obtenir le statut de tous les flux de caméras"""
    try:
        status = camera_manager.get_streams_status()
        
        # Filtrer selon les permissions utilisateur
        if current_user.role == 'client':
            # Pour les clients, ne montrer que leurs caméras
            user_cameras = [eq.id for eq in Equipement.query.filter_by(client_id=current_user.client_id).all()]
            status = {k: v for k, v in status.items() if k in user_cameras}
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Erreur API statut streams: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

# Route pour la page de détail d'une caméra avec flux vidéo
@app.route('/camera/<int:camera_id>')
@login_required
def camera_detail(camera_id):
    """Page de détail d'une caméra avec flux vidéo"""
    try:
        equipement = Equipement.query.get(camera_id)
        if not equipement:
            flash('Caméra non trouvée.', 'error')
            return redirect(url_for('equipements'))
        
        # Vérifier les permissions
        if current_user.role == 'client' and equipement.client_id != current_user.client_id:
            flash('Accès refusé à cette caméra.', 'error')
            return redirect(url_for('equipements'))
        
        # Obtenir l'historique récent
        historique = db.session.query(HistoriquePing).filter_by(
            equipement_id=camera_id
        ).order_by(HistoriquePing.timestamp.desc()).limit(10).all()
        
        # Obtenir les alertes récentes
        alertes = db.session.query(Alerte).filter_by(
            equipement_id=camera_id
        ).order_by(Alerte.timestamp.desc()).limit(5).all()
        
        return render_template('camera_detail.html', 
                             equipement=equipement, 
                             historique=historique,
                             alertes=alertes)
        
    except Exception as e:
        logger.error(f"Erreur détail caméra {camera_id}: {e}")
        flash(f"Erreur lors du chargement de la caméra: {e}", "error")
        return redirect(url_for('equipements'))

# Routes pour la configuration RTSP
@app.route('/equipements/<int:equipement_id>/configure_stream', methods=['GET', 'POST'])
@login_required
def configure_stream(equipement_id):
    """Configuration du flux RTSP pour un équipement"""
    try:
        equipement = Equipement.query.get(equipement_id)
        if not equipement:
            flash('Équipement non trouvé.', 'error')
            return redirect(url_for('equipements'))
        
        # Vérifier les permissions
        if current_user.role == 'client' and equipement.client_id != current_user.client_id:
            flash('Accès refusé.', 'error')
            return redirect(url_for('equipements'))
        
        if request.method == 'POST':
            # Sauvegarder la configuration RTSP
            equipement.rtsp_url = request.form.get('rtsp_url')
            equipement.rtsp_username = request.form.get('rtsp_username')
            equipement.rtsp_password = request.form.get('rtsp_password')
            equipement.stream_enabled = bool(request.form.get('stream_enabled'))
            equipement.resolution = request.form.get('resolution', '640x480')
            equipement.fps = int(request.form.get('fps', 15))
            equipement.stream_quality = request.form.get('stream_quality', 'medium')
            
            db.session.commit()
            flash('Configuration RTSP sauvegardée avec succès.', 'success')
            return redirect(url_for('camera_detail', camera_id=equipement_id))
        
        return render_template('configure_stream.html', equipement=equipement)
        
    except Exception as e:
        logger.error(f"Erreur configuration stream {equipement_id}: {e}")
        flash(f"Erreur lors de la configuration: {e}", "error")
        return redirect(url_for('equipements'))

# Nettoyage automatique des flux morts (désactivé pour Windows)
@app.before_request
def cleanup_dead_streams():
    """Nettoie les flux morts avant chaque requête"""
    # Désactiver sur Windows pour éviter les erreurs OpenCV
    if os.environ.get('DISABLE_CAMERA_STREAMS') == '1':
        return
    
    # Ne nettoyer que de temps en temps pour éviter la surcharge
    import random
    if random.randint(1, 100) == 1:  # 1% de chance à chaque requête
        try:
            camera_manager.cleanup_dead_streams()
        except Exception as e:
            logger.debug(f"Erreur nettoyage streams: {e}")