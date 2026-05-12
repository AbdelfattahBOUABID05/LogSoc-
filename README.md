LogAnalyzer SOC - Monitoring & Web Analytics (V2.0)
🌟 Vue d'ensemble

LogAnalyzer SOC est une solution Full-stack d'ingénierie système et de monitoring web, conçue pour l'observabilité avancée. L'application combine une architecture REST performante et un moteur d'analyse de flux en temps réel pour une gestion efficace des infrastructures informatiques.

    Backend : API REST Flask sécurisée avec traitement asynchrone et insights par IA.

    Frontend : Interface Single Page Application (SPA) développée avec Angular 17 et Tailwind CSS pour une visualisation de données fluide.

🔑 Accès par Défaut

Pour votre première connexion après l'initialisation de la base de données :

    Email : admin@soc.com

    Mot de passe : Admin@123

    Note : Le système vous demandera obligatoirement de changer ce mot de passe lors de votre première session pour des raisons de conformité système.

🖥️ Configuration du Nœud Cible (SSH)

Pour que l'analyse système fonctionne correctement, le serveur que vous souhaitez monitorer (ex: Ubuntu, Debian) doit être configuré comme suit :

    Installer le serveur SSH :
    Bash

    sudo apt update && sudo apt install openssh-server -y

    Activer le service :
    Bash

    sudo systemctl enable ssh && sudo systemctl start ssh

    Droits de lecture sur les flux :
    L'utilisateur utilisé pour la connexion doit avoir le droit de lire /var/log/syslog.
    Bash

    # Ajouter l'utilisateur au groupe 'adm' (observabilité)
    sudo usermod -aG adm [votre_utilisateur]

    Pare-feu :
    Assurez-vous que le port de communication (22 par défaut) est ouvert :
    Bash

    sudo ufw allow ssh

🚀 Déploiement & Architecture
Backend (Flask API)

    Accéder au dossier : cd backend

    Installer les dépendances : pip install -r requirements.txt

    Variables d'environnement (.env) :
    Extrait de code

    SECRET_KEY=votre_cle_flask
    FERNET_KEY=votre_cle_de_chiffrement_aes
    GEMINI_API_KEY=votre_cle_google_ai
    DATABASE_URL=sqlite:///loganalyzer.db

    Lancer le serveur : flask run --port=5000

Frontend (Angular SPA)

    Accéder au dossier : cd frontend

    Installer : npm install

    Lancer : npm start (Accès : http://localhost:4200)

🛠️ Endpoints API & Observabilité
Méthode	Endpoint	Description
POST	/api/auth/login	Authentification et session
POST	/api/ssh/analyze	Analyse de flux en temps réel via SSH
POST	/api/auth/change-password	Sécurité : Gestion du cycle de vie des identifiants
GET	/api/dashboard	Métriques de performance et insights IA
GET	/api/analyses/:id/pdf	Génération du rapport d'analyse système
🛡️ Intégrité des Données

    Chiffrement des Flux : Les identifiants de connexion sont protégés par un chiffrement symétrique AES-256.

    Authentification : Utilisation de l'algorithme bcrypt pour le hachage des mots de passe.

    Observabilité : Monitoring granulaire des accès et des performances serveurs.