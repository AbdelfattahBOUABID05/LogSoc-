from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(db.Model, UserMixin):
    """
    Modèle représentant un utilisateur du système SOC.
    Gère l'authentification, les rôles (Admin/Analyseur) et les paramètres de notification.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Admin") # Admin | Analyseur
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Configuration SMTP pour l'envoi des rapports d'audit par email
    email_sender = db.Column(db.String(255), nullable=True)
    email_password_enc = db.Column(db.String(255), nullable=True)
    smtp_server = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True)
    signature_path = db.Column(db.String(255), nullable=True)
    is_first_login = db.Column(db.Boolean, default=True, nullable=False)

    # Paramètres de notifications push/email
    email_notifications_enabled = db.Column(db.Boolean, default=False)
    notification_email = db.Column(db.String(255), nullable=True)

    def set_password(self, password: str) -> None:
        """Hache le mot de passe avant de l'enregistrer"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Vérifie si le mot de passe fourni correspond au hachage stocké"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur possède les privilèges Administrateur"""
        return (self.role or "").lower() == "admin"


class Analysis(db.Model):
    """
    Modèle stockant les résultats d'un audit de logs.
    Contient les statistiques, les segments analysés et les scores IA.
    """
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    source_type = db.Column(db.String(20), nullable=False)  # ssh | upload | scheduled
    source_path = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255), nullable=True) # Chemin physique du fichier log
    server_ip = db.Column(db.String(64), nullable=True)

    # Données brutes de l'analyse (JSON)
    stats = db.Column(db.JSON, nullable=False)    # {errors: X, warnings: Y, info: Z, total: W}
    segments = db.Column(db.JSON, nullable=False) # Lignes de logs catégorisées
    meta = db.Column(db.JSON, nullable=False)     # Insights IA, recommandations, etc.

    # Scores calculés par le moteur d'Intelligence Artificielle (Gemini)
    ai_score = db.Column(db.Integer, nullable=True)
    ai_status = db.Column(db.String(20), nullable=True)
    ai_menaces = db.Column(db.Integer, nullable=True)

    user = db.relationship("User", backref=db.backref("analyses", lazy="dynamic"))
    job = db.relationship("AnalysisJob", backref=db.backref("history", lazy="dynamic"))


class AnalysisJob(db.Model):
    """
    Modèle pour la planification d'audits automatiques.
    Définit la cible SSH et la fréquence (horaire, journalière, etc.).
    """
    __tablename__ = "analysis_jobs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Paramètres de connexion et cible
    target_ip = db.Column(db.String(64), nullable=False)
    log_path = db.Column(db.String(255), nullable=False, default="/var/log/syslog")
    frequency = db.Column(db.String(20), nullable=False)  # hourly, daily, weekly, monthly, custom
    custom_interval = db.Column(db.Integer, nullable=True)
    custom_unit = db.Column(db.String(10), nullable=True)
    
    # Statut du cycle de vie de la tâche
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, active, refused, stopped
    
    admin_notified = db.Column(db.Boolean, default=False)
    user_notified = db.Column(db.Boolean, default=False)
    
    # Identifiants SSH (Mot de passe chiffré pour la sécurité)
    ssh_username = db.Column(db.String(128), nullable=True)
    ssh_password_enc = db.Column(db.String(255), nullable=True)
    
    # Suivi temporel des exécutions
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_run_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_run_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    refusal_reason = db.Column(db.Text, nullable=True)
    
    notify_on_anomaly = db.Column(db.Boolean, default=True)
    notification_email = db.Column(db.String(255), nullable=True)
    
    user = db.relationship("User", backref=db.backref("scheduled_jobs", lazy="dynamic"))

    def __repr__(self):
        return f"<AnalysisJob {self.id} - {self.target_ip} - {self.status}>"


class SavedServer(db.Model):
    """Serveurs SSH enregistrés pour Quick Connect et Analyse Globale"""
    __tablename__ = "saved_servers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    ip = db.Column(db.String(64), nullable=False)
    encrypted_username = db.Column(db.String(255), nullable=False) # Nom d'utilisateur chiffré
    encrypted_password = db.Column(db.String(255), nullable=False) # Mot de passe chiffré
    log_path = db.Column(db.String(255), nullable=False, default="/var/log/syslog")
    
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("saved_servers", lazy="dynamic"))

    def __repr__(self):
        return f"<SavedServer {self.ip}>"


class SavedSSHConnection(db.Model):
    """Connexions SSH récentes pour l'auto-complétion"""
    __tablename__ = "saved_ssh_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    host = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(128), nullable=False)
    encrypted_password = db.Column(db.Text, nullable=False)
    
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("ssh_connections", lazy="dynamic"))

    def __repr__(self):
        return f"<SavedSSHConnection {self.host} ({self.username})>"


class AdminSavedConnection(db.Model):
    """Connexions SSH enregistrées spécifiquement pour la Console Admin"""
    __tablename__ = "admin_saved_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    host = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(128), nullable=False)
    encrypted_password = db.Column(db.Text, nullable=False)
    
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("admin_ssh_connections", lazy="dynamic"))

    def __repr__(self):
        return f"<AdminSavedConnection {self.host} ({self.username})>"


class Notification(db.Model):
    """Système de notifications internes pour les utilisateurs"""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False, default="info") # info, success, warning, error
    
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Métadonnées optionnelles (ex: ID du job lié)
    link = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    def __repr__(self):
        return f"<Notification {self.id} for User {self.user_id}>"


class SolutionKB(db.Model):
    """
    Modèle pour la Base de Connaissances (Knowledge Base).
    Stocke les solutions aux problèmes récurrents détectés dans les logs.
    """
    __tablename__ = "solutions_kb"

    id = db.Column(db.Integer, primary_key=True)
    problem_title = db.Column(db.String(255), nullable=False)
    log_pattern = db.Column(db.String(255), nullable=False) # Chaîne spécifique à matcher
    solution_content = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(100), nullable=False, default='Admin')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "problem_title": self.problem_title,
            "log_pattern": self.log_pattern,
            "solution_content": self.solution_content,
            "author_name": self.author_name,
            "created_at": self.created_at.isoformat()
        }


class AuditLog(db.Model):
    """
    Modèle pour l'historique des activités (Audit Logs).
    Permet de surveiller les actions des utilisateurs et administrateurs.
    """
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }
