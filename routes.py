import logging
from datetime import datetime, timedelta
from flask import render_template, request, jsonify, flash, redirect, url_for, session, Response
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import Client, Equipement, HistoriquePing, Alerte, User
from email_service import email_service
from camera_stream import camera_manager, generate_stream_response

logger = logging.getLogger(__name__)

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