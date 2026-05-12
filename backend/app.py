import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_login import LoginManager
from dotenv import load_dotenv
import logging
from sqlalchemy.exc import IntegrityError

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

def setup_database(app):
    """
    Initialise la base de données et crée l'administrateur par défaut.
    Gère les accès concurrents entre les workers Gunicorn.
    """
    with app.app_context():
        try:
            db.create_all()
            
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
                admin_user.set_password(os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin@12345'))
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

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erreur lors de l'initialisation de la DB : {e}")

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

    # Initialisation de la DB et du Scheduler
    setup_database(app)
    init_scheduler(app)

    return app

# Instance pour Gunicorn
app = create_app()

if __name__ == '__main__':
    # Écoute sur 0.0.0.0 pour Docker
    app.run(host='0.0.0.0', port=5000)
