from datetime import datetime, timedelta
from app import db
from sqlalchemy import func
from flask_login import UserMixin
import hashlib

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nom_utilisateur = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(32), nullable=False)  # MD5 hash
    nom_complet = db.Column(db.String(200))
    role = db.Column(db.String(20), default='client')  # 'admin', 'client'
    statut = db.Column(db.String(20), default='en_attente')  # 'en_attente', 'approuve', 'refuse'
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    derniere_connexion = db.Column(db.DateTime)
    actif = db.Column(db.Boolean, default=True)
    
    # Relation avec le client (si c'est un utilisateur client)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    def __repr__(self):
        return f'<User {self.nom_utilisateur}>'
    
    def set_password(self, mot_de_passe):
        """Crypte le mot de passe avec MD5"""
        self.mot_de_passe_hash = hashlib.md5(mot_de_passe.encode('utf-8')).hexdigest()
    
    def check_password(self, mot_de_passe):
        """Vérifie le mot de passe"""
        return self.mot_de_passe_hash == hashlib.md5(mot_de_passe.encode('utf-8')).hexdigest()
    
    def update_last_login(self):
        """Met à jour la date de dernière connexion"""
        self.derniere_connexion = datetime.utcnow()
        db.session.commit()

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.Text)
    telephone = db.Column(db.String(20))
    email = db.Column(db.String(100), nullable=False)  # Email obligatoire pour les notifications
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)
    
    # Relation avec les équipements
    equipements = db.relationship('Equipement', backref='client', lazy=True, cascade='all, delete-orphan')
    
    # Relation avec les utilisateurs
    users = db.relationship('User', backref='client', lazy=True)
    
    def __repr__(self):
        return f'<Client {self.nom}>'
    
    @property
    def nb_equipements_total(self):
        return db.session.query(Equipement).filter_by(client_id=self.id, actif=True).count()
    
    @property
    def nb_equipements_en_ligne(self):
        equipements = db.session.query(Equipement).filter_by(client_id=self.id, actif=True).all()
        return len([eq for eq in equipements if eq.est_en_ligne])
    
    @property
    def nb_equipements_hors_ligne(self):
        equipements = db.session.query(Equipement).filter_by(client_id=self.id, actif=True).all()
        return len([eq for eq in equipements if not eq.est_en_ligne])

class Equipement(db.Model):
    __tablename__ = 'equipements'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    type_equipement = db.Column(db.String(50), nullable=False)  # DVR, Camera, etc.
    adresse_ip = db.Column(db.String(45), nullable=False)
    port = db.Column(db.Integer, default=80)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    dernier_ping = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)
    
    # Champs pour les flux RTSP/IP
    rtsp_url = db.Column(db.String(500))  # URL RTSP complète
    rtsp_username = db.Column(db.String(100))  # Nom d'utilisateur pour l'authentification RTSP
    rtsp_password = db.Column(db.String(100))  # Mot de passe pour l'authentification RTSP
    stream_enabled = db.Column(db.Boolean, default=False)  # Flux vidéo activé
    resolution = db.Column(db.String(20), default='640x480')  # Résolution préférée
    fps = db.Column(db.Integer, default=15)  # Images par seconde
    stream_quality = db.Column(db.String(20), default='medium')  # low, medium, high
    
    # Relation avec l'historique des pings
    historique_pings = db.relationship('HistoriquePing', backref='equipement', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Equipement {self.nom} - {self.adresse_ip}>'
    
    @property
    def est_en_ligne(self):
        """Vérifie si l'équipement est considéré comme en ligne (ping < 2 minutes)"""
        if not self.dernier_ping:
            return False
        
        timeout = datetime.utcnow() - timedelta(minutes=2)
        return self.dernier_ping > timeout
    
    @property
    def statut_texte(self):
        return "En ligne" if self.est_en_ligne else "Hors ligne"
    
    @property
    def duree_depuis_dernier_ping(self):
        """Retourne la durée depuis le dernier ping en format lisible"""
        if not self.dernier_ping:
            return "Jamais"
        
        delta = datetime.utcnow() - self.dernier_ping
        
        if delta.days > 0:
            return f"{delta.days} jour(s)"
        elif delta.seconds > 3600:
            heures = delta.seconds // 3600
            return f"{heures} heure(s)"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute(s)"
        else:
            return "< 1 minute"
    
    @property
    def rtsp_stream_url(self):
        """Construit l'URL RTSP complète avec authentification"""
        if not self.rtsp_url:
            return None
        
        if self.rtsp_username and self.rtsp_password:
            # Format: rtsp://username:password@host:port/path
            if '://' in self.rtsp_url:
                protocol, rest = self.rtsp_url.split('://', 1)
                return f"{protocol}://{self.rtsp_username}:{self.rtsp_password}@{rest}"
        
        return self.rtsp_url
    
    @property
    def has_stream_capability(self):
        """Vérifie si cet équipement peut diffuser de la vidéo"""
        return bool(self.rtsp_url and self.stream_enabled)
    
    def get_stream_resolution(self):
        """Retourne la résolution sous forme de tuple (largeur, hauteur)"""
        if self.resolution and 'x' in self.resolution:
            try:
                w, h = self.resolution.split('x')
                return int(w), int(h)
            except ValueError:
                pass
        return 640, 480  # Résolution par défaut

class HistoriquePing(db.Model):
    __tablename__ = 'historique_pings'
    
    id = db.Column(db.Integer, primary_key=True)
    equipement_id = db.Column(db.Integer, db.ForeignKey('equipements.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    statut = db.Column(db.String(20), nullable=False)  # 'success', 'timeout', 'error'
    reponse_ms = db.Column(db.Integer)  # Temps de réponse en millisecondes
    message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<HistoriquePing {self.equipement_id} - {self.statut} - {self.timestamp}>'

class Alerte(db.Model):
    __tablename__ = 'alertes'
    
    id = db.Column(db.Integer, primary_key=True)
    equipement_id = db.Column(db.Integer, db.ForeignKey('equipements.id'), nullable=False)
    type_alerte = db.Column(db.String(50), nullable=False)  # 'hors_ligne', 'retour_en_ligne'
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    lue = db.Column(db.Boolean, default=False)
    
    # Relation avec l'équipement
    equipement = db.relationship('Equipement', backref='alertes')
    
    def __repr__(self):
        return f'<Alerte {self.type_alerte} - {self.equipement_id}>'
