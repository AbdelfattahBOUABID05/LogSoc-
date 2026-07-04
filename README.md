LogAnalyzer SOC - Monitoring & Web Analytics (V2.0)
🌟 Vue d'ensemble

LogAnalyzer SOC est une solution Full-stack d'ingénierie système et de monitoring web, conçue pour l'observabilité avancée. L'application combine une architecture REST performante et un moteur d'analyse de flux en temps réel pour une gestion efficace des infrastructures informatiques.

- **Backend** : API REST Flask sécurisée avec traitement asynchrone et insights par IA.
- **Frontend** : Interface Single Page Application (SPA) développée avec Angular 17 et Tailwind CSS pour une visualisation de données fluide.

### Fonctionnalités Principales

- **Analyse de logs en temps réel** :
  - SSH : Connexion à des serveurs distants pour analyser les logs système
  - Local : Upload et analyse de fichiers de logs locaux
  - Planifié : Jobs récurrents pour l'analyse automatisée
- **Intelligence Artificielle** :
  - Intégration de Google Gemini pour évaluer les menaces
  - Score de sécurité et résumé des risques
- **Gestion des Utilisateurs et Sécurité** :
  - Rôles (Admin, Analyste)
  - Authentification sécurisée avec tokens
  - Chiffrement des identifiants
- **Rapports et Notifications** :
  - Génération de rapports PDF
  - Envoi par email
  - Notifications en temps réel
- **Base de Connaissances** :
  - Smart matching des solutions aux erreurs connues
- **Tableau de bord** :
  - Visualisation des métriques (charts, graphs)
  - Suivi de l'activité en temps réel

## Architecture du Projet

```
logsoc/
├── backend/               # Backend Flask
│   ├── app.py             # Application principale
│   ├── config.py          # Configuration
│   ├── models.py          # Modèles de données (SQLAlchemy)
│   ├── api_routes.py      # Endpoints API
│   ├── scheduler.py       # Jobs planifiés
│   ├── requirements.txt   # Dépendances Python
│   └── Dockerfile
├── frontend/              # Frontend Angular
│   ├── src/app/
│   │   ├── components/    # Composants Angular
│   │   ├── services/      # Services (auth, API, etc.)
│   │   └── app.routes.ts  # Routes
│   ├── angular.json
│   ├── package.json       # Dépendances Node
│   └── Dockerfile
├── docker-compose.yml     # Déploiement complet avec Docker
└── README.md
```

🔑 Accès par Défaut

Pour votre première connexion après initialisation de la base de données :

- **Email** : `admin@local`
- **Mot de passe** : `Admin@12345`

🖥️ Configuration du Nœud Cible (SSH)

Pour que l'analyse système fonctionne correctement, le serveur que vous souhaitez monitorer (ex: Ubuntu, Debian) doit être configuré comme suit :

1. **Installer le serveur SSH** :
   ```bash
   sudo apt update && sudo apt install openssh-server -y
   ```

2. **Activer le service** :
   ```bash
   sudo systemctl enable ssh && sudo systemctl start ssh
   ```

3. **Droits de lecture sur les flux** :
   Ajoutez l'utilisateur au groupe `adm` (observabilité) :
   ```bash
   sudo usermod -aG adm [votre_utilisateur]
   ```

4. **Pare-feu** :
   Assurez-vous que le port de communication (22 par défaut) est ouvert :
   ```bash
   sudo ufw allow ssh
   ```

🚀 Déploiement

### Déploiement avec Docker Compose (Recommandé)

Ceci est la méthode la plus simple et la plus fiable pour lancer l'application complète (Base de données, Backend et Frontend) en quelques minutes.

#### Prérequis

Assurez-vous d'avoir installé :
- **Docker** : [Télécharger Docker](https://www.docker.com/get-started)
- **Docker Compose** : Inclus avec Docker Desktop sur Windows/macOS

Vérifiez les installations :
```bash
docker --version
docker-compose --version
```

#### Étape 1 : Créer le fichier `.env`

Copiez le modèle ci-dessous et créez un fichier `.env` **à la racine du projet** (même niveau que `docker-compose.yml`) :

```env
# Configuration Base de données PostgreSQL
POSTGRES_USER=logsoc
POSTGRES_PASSWORD=VotreMotDePasseSecurise123!
POSTGRES_DB=logsoc
DB_USER=logsoc
DB_PASSWORD=VotreMotDePasseSecurise123!
DB_NAME=logsoc

# Backend
SECRET_KEY=remplacez_cette_chaîne_par_une_cle_secrete_tres_longue_et_securisee
GEMINI_API_KEY=VotreCleApiGoogleGemini
DATABASE_URL=postgresql://logsoc:VotreMotDePasseSecurise123!@db:5432/logsoc

# Configuration Email (exemple Mailtrap - optionnel)
SMTP_SERVER=sandbox.smtp.mailtrap.io
SMTP_PORT=2525
SMTP_USER=VotreUsernameMailtrap
SMTP_PASSWORD=VotreMotDePasseMailtrap
MAIL_USE_TLS=True
```

**Notes importantes** :
- Remplacez `VotreMotDePasseSecurise123!` par un mot de passe sécurisé
- Remplacez `remplacez_cette_chaîne_par_une_cle_secrete_tres_longue_et_securisee` par une chaîne aléatoire sécurisée
- Si vous n'avez pas de clé Google Gemini, vous pouvez laisser `GEMINI_API_KEY` vide (l'analyse IA ne fonctionnera pas)

#### Étape 2 : Lancer les services

Ouvrez un terminal, allez à la racine du projet et exécutez :

```bash
docker-compose up -d --build
```

- `-d` : Lance les conteneurs en arrière-plan
- `--build` : Force la reconstruction des images (utile si vous avez modifié le code)

#### Étape 3 : Vérifier le statut des conteneurs

Pour vérifier que tous les services fonctionnent correctement :

```bash
docker-compose ps
```

Vous devriez voir 3 conteneurs en statut `Up` :
- `logsoc-db-1` (Base de données)
- `logsoc-backend-1` (Backend Flask)
- `logsoc-frontend-1` (Frontend Angular)

#### Étape 4 : Accéder à l'application

Ouvrez votre navigateur et allez à l'adresse :
**http://localhost**

Connectez-vous avec les identifiants par défaut :
- **Email** : `admin@local`
- **Mot de passe** : `Admin@12345`

#### Commandes Utiles Docker Compose

- **Voir les logs** :
  ```bash
  docker-compose logs -f  # -f pour suivre les logs en temps réel
  ```

- **Arrêter les services** :
  ```bash
  docker-compose down
  ```

- **Arrêter et supprimer les volumes (perte des données)** :
  ```bash
  docker-compose down -v
  ```

- **Redémarrer les services** :
  ```bash
  docker-compose restart
  ```

### Développement Local (Sans Docker)

#### Prérequis

- **Python** 3.11+
- **Node.js** 18+ et npm
- **PostgreSQL** (ou SQLite pour développement simple)

#### Backend (Flask)

1. **Accéder au dossier backend** :
   ```bash
   cd backend
   ```

2. **Créer un environnement virtuel** :
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # OU
   .\venv\Scripts\activate  # Windows
   ```

3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement** :
   Créez un fichier `.env` dans le dossier `backend/`.

5. **Lancer le serveur** :
   ```bash
   flask run --port=5000
   ```

#### Frontend (Angular)

1. **Accéder au dossier frontend** :
   ```bash
   cd frontend
   ```

2. **Installer les dépendances** :
   ```bash
   npm install
   ```

3. **Lancer le serveur de développement** :
   ```bash
   npm start
   ```

4. **Accéder à l'interface** :
   Ouvrez votre navigateur à l'adresse : **http://localhost:4200**

🛠️ Endpoints API & Observabilité

| Méthode | Endpoint                   | Description                                                                 |
|---------|----------------------------|-----------------------------------------------------------------------------|
| POST    | `/api/login`               | Authentification et récupération du token                                  |
| POST    | `/api/logout`              | Déconnexion                                                                |
| GET     | `/api/auth/me`             | Obtenir les informations de l'utilisateur actuel                           |
| POST    | `/api/ssh/analyze`         | Analyse de logs via SSH                                                    |
| POST    | `/api/analyze-local`       | Analyse de fichiers de logs locaux (upload)                                |
| GET     | `/api/analyses`            | Récupérer la liste des analyses                                            |
| GET     | `/api/analyses/:public_id` | Récupérer les détails d'une analyse spécifique                             |
| GET     | `/api/analyses/:public_id/pdf` | Télécharger le rapport PDF d'une analyse                               |
| GET     | `/api/dashboard`           | Métriques du tableau de bord                                               |
| GET     | `/api/stats`               | Statistiques agrégées (pour les graphs)                                    |
| GET/POST| `/api/settings`            | Gérer les paramètres utilisateur                                           |
| GET/POST| `/api/jobs`                | Gérer les jobs planifiés                                                   |
| POST    | `/api/email/send-report`   | Envoyer un rapport par email                                               |

## Technologies Utilisées

### Backend
- **Framework** : Flask
- **ORM** : SQLAlchemy
- **Base de données** : PostgreSQL (production), SQLite (développement)
- **Jobs planifiés** : Flask-APScheduler
- **IA** : Google Gemini
- **PDF** : FPDF
- **SSH** : Paramiko

### Frontend
- **Framework** : Angular 17+
- **Styling** : Tailwind CSS
- **Graphiques** : ApexCharts, Chart.js
- **UI** : Angular Material
- **Notifications** : ngx-toastr, SweetAlert2

🛡️ Intégrité des Données

- **Chiffrement des Flux** : Les identifiants de connexion sont protégés par chiffrement symétrique.
- **Authentification** : Utilisation de bcrypt pour le hachage des mots de passe.
- **Tokens** : Gestion de sessions sécurisées avec tokens signés.
- **Audit** : Journalisation détaillée de toutes les actions des utilisateurs.
