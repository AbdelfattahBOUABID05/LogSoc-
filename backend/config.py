import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "ma-cle-secrete-fixe-123")
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Taille maximale 16 Mo

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///log_analyzer.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@local")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@12345")

    # Configuration Email
    MAIL_SERVER = os.getenv("SMTP_SERVER", "sandbox.smtp.mailtrap.io")
    MAIL_PORT = int(os.getenv("SMTP_PORT", 2525))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
    MAIL_USERNAME = os.getenv("SMTP_USER", "b1d332e315f09f")
    MAIL_PASSWORD = os.getenv("SMTP_PASSWORD", "78b1eb63687425")