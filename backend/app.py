import os
import uuid
from flask import Flask, jsonify
from flask_cors import CORS
from flask_login import LoginManager
from dotenv import load_dotenv
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect, text

from config import Config
from extensions import db, scheduler
from scheduler import init_scheduler
from models import User
from api_routes import api as api_blueprint

# Chargement des variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_analysis_public_id_schema():
    """
    Met à niveau le schéma de `analyses` sur une base déjà existante.
    `db.create_all()` ne modifie pas les tables créées auparavant, donc on
    ajoute explicitement `public_id` si la colonne n'existe pas encore.
    """
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if "analyses" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("analyses")}
    if "public_id" not in columns:
        logger.info("Migration: ajout de la colonne analyses.public_id")
        db.session.execute(text("ALTER TABLE analyses ADD COLUMN public_id VARCHAR(36)"))
        db.session.commit()

    missing_rows = db.session.execute(
        text("SELECT id FROM analyses WHERE public_id IS NULL OR public_id = ''")
    ).fetchall()

    if missing_rows:
        logger.info("Migration: génération des public_id manquants pour les analyses existantes")
        for row in missing_rows:
            db.session.execute(
                text("UPDATE analyses SET public_id = :public_id WHERE id = :id"),
                {"public_id": str(uuid.uuid4()), "id": row.id},
            )
        db.session.commit()

    # Un index unique protège contre les doublons côté base sans impacter la logique existante.
    db.session.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_analyses_public_id ON analyses (public_id)")
    )
    db.session.commit()


def ensure_analysis_job_schema():
    """
    Met à niveau le schéma de `analysis_jobs` sur une base déjà existante.
    Ajoute `name` et `public_id` si nécessaires.
    """
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if "analysis_jobs" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("analysis_jobs")}
    
    # Gestion de la colonne 'name'
    if "name" not in columns:
        logger.info("Migration: ajout de la colonne analysis_jobs.name")
        db.session.execute(text("ALTER TABLE analysis_jobs ADD COLUMN name VARCHAR(150)"))
        db.session.commit()

    unnamed_rows = db.session.execute(
        text("SELECT id, target_ip FROM analysis_jobs WHERE name IS NULL OR name = ''")
    ).fetchall()
    if unnamed_rows:
        logger.info("Migration: génération des noms manquants pour les jobs existants")
        for row in unnamed_rows:
            default_name = f"Job {row.id} - {row.target_ip}"
            db.session.execute(
                text("UPDATE analysis_jobs SET name = :name WHERE id = :id"),
                {"name": default_name, "id": row.id},
            )
        db.session.commit()

    # Gestion de la colonne 'public_id'
    if "public_id" not in columns:
        logger.info("Migration: ajout de la colonne analysis_jobs.public_id")
        db.session.execute(text("ALTER TABLE analysis_jobs ADD COLUMN public_id VARCHAR(36)"))
        db.session.commit()

    missing_uuids = db.session.execute(
        text("SELECT id FROM analysis_jobs WHERE public_id IS NULL OR public_id = ''")
    ).fetchall()
    if missing_uuids:
        logger.info("Migration: génération des public_id manquants pour les jobs existants")
        for row in missing_uuids:
            db.session.execute(
                text("UPDATE analysis_jobs SET public_id = :public_id WHERE id = :id"),
                {"public_id": str(uuid.uuid4()), "id": row.id},
            )
        db.session.commit()

    # Index unique pour public_id
    db.session.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_analysis_jobs_public_id ON analysis_jobs (public_id)")
    )
    db.session.commit()


def create_default_admin():
    """Crée l'administrateur par défaut si nécessaire."""
    admin_username = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    admin_user = User.query.filter_by(username=admin_username).first()
    
    if not admin_user:
        logger.info(f"Création de l'administrateur par défaut : {admin_username}")
        admin_user = User(
            username=admin_username,
            email=os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@soc.local'),
            first_name='Admin',
            last_name='SOC',
            role='Admin',
            is_first_login=False
        )
        admin_user.set_password(os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin'))
        db.session.add(admin_user)
        
        try:
            db.session.commit()
            logger.info("✅ Administrateur par défaut créé avec succès.")
        except IntegrityError:
            db.session.rollback()
            logger.info("ℹ️ L'administrateur a déjà été créé par un autre worker.")
    else:
        if admin_user.role != 'Admin':
            admin_user.role = 'Admin'
            db.session.commit()
            logger.info("🔄 Rôle Admin mis à jour.")
        else:
            logger.info("ℹ️ Compte Admin configuré.")


def setup_database(app):
    """
    Initialise la base de données et crée l'administrateur par défaut.
    Gère les accès concurrents entre les workers Gunicorn.
    """
    with app.app_context():
        try:
            db.create_all()
            ensure_analysis_public_id_schema()
            ensure_analysis_job_schema()
            create_default_admin()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base : {e}")
            db.session.rollback()

def create_app():
    """Application Factory pour initialiser Flask proprement."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialisation des extensions
    db.init_app(app)
    
    # Configuration de Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.unauthorized_handler(lambda: (jsonify({"status": "error", "message": "Non autorisé"}), 401))
    login_manager.user_loader(lambda user_id: db.session.get(User, int(user_id)))

    # Configuration de CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # Enregistrement des Blueprints
    app.register_blueprint(api_blueprint)

    # Gestion globale des erreurs pour garantir des réponses JSON
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"status": "error", "error": "Not Found", "message": "La ressource demandée n'existe pas"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({"status": "error", "error": "Internal Server Error", "message": "Une erreur interne est survenue"}), 500

    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify({"status": "error", "error": "Unauthorized", "message": "Authentification requise"}), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({"status": "error", "error": "Forbidden", "message": "Accès refusé"}), 403

    # Initialisation de la DB et du Scheduler
    setup_database(app)
    init_scheduler(app)

    return app




# Instance pour Gunicorn
app = create_app()

if __name__ == '__main__':
    # Écoute sur 0.0.0.0 pour Docker
    app.run(host='0.0.0.0', port=5000)
