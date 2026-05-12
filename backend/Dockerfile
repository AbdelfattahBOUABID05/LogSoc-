# Utilisation d'une image Python légère
FROM python:3.11-slim

# Définition du répertoire de travail
WORKDIR /app

# Installation des dépendances système nécessaires (PDF, SSH, DB, Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    libjpeg-dev \
    zlib1g-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier des dépendances Python
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code source
COPY . .

# Créer les répertoires nécessaires
RUN mkdir -p instance static/reports

# Variables d'environnement par défaut
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Exposer le port du backend
EXPOSE 5000

# Utilisation de Gunicorn pour la production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
