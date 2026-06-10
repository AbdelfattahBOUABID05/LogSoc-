import random
import uuid
from datetime import datetime, timedelta, timezone
from app import create_app
from extensions import db
from models import User, Analysis, AuditLog

# Initialisation de l'application Flask pour accéder au contexte SQLAlchemy
app = create_app()

def seed_database():
    with app.app_context():
        print("🔍 Recherche de l'utilisateur administrateur...")
        user = User.query.filter_by(role='Admin').first()
        if not user:
            print("❌ Aucun utilisateur Admin trouvé. Veuillez d'abord lancer l'application pour créer l'admin par défaut.")
            return

        print("🗑️ Nettoyage des anciennes données (Analyses et Audits)...")
        # On supprime les anciennes analyses pour repartir sur une base propre pour le dashboard
        db.session.query(Analysis).delete()
        db.session.query(AuditLog).delete()
        db.session.commit()

        base_date = datetime.now(timezone.utc)
        all_objects = []
        batch_size = 10000
        total_generated = 0

        print(f"🚀 Début de la génération de données sur 730 jours (2 ans)...")

        # Boucle sur 730 jours (2 ans)
        for i in range(730):
            # On recule jour par jour
            current_date = base_date - timedelta(days=i)
            
            # Génération d'un nombre aléatoire de logs par jour (vagues réalistes)
            # On utilise une fonction sinus pour simuler une variation saisonnière/hebdomadaire
            variation = int(200 * (1 + random.random())) # Variation aléatoire de base
            logs_per_day = random.randint(300, 1200) + variation
            
            if i % 30 == 0:
                print(f"📅 Traitement du jour -{i} ({current_date.strftime('%Y-%m-%d')})...")

            for _ in range(logs_per_day):
                # Calcul d'une heure aléatoire dans la journée
                h = random.randint(0, 23)
                m = random.randint(0, 59)
                s = random.randint(0, 59)
                log_time = current_date.replace(hour=h, minute=m, second=s)

                # Sélection du type de source (SSH, System, Task)
                source_choice = random.choice(['ssh', 'upload', 'scheduled'])
                
                # Détermination du statut (95% success, 5% failed)
                is_failed = random.random() < 0.05
                
                if is_failed:
                    ai_status = random.choice(['Menace Détectée', 'Attention'])
                    ai_score = random.randint(10, 50)
                    ai_menaces = random.randint(1, 10)
                    # Stats avec erreurs/alertes
                    stats = {
                        "errors": random.randint(5, 20),
                        "warnings": random.randint(10, 30),
                        "info": random.randint(50, 100),
                        "total": 1 # Chaque entrée représente 1 événement pour le graph
                    }
                else:
                    ai_status = 'Normal'
                    ai_score = random.randint(85, 100)
                    ai_menaces = 0
                    # Stats clean
                    stats = {
                        "errors": 0,
                        "warnings": random.randint(0, 2),
                        "info": random.randint(10, 50),
                        "total": 1
                    }

                # Création de l'objet Analysis
                analysis = Analysis(
                    public_id=str(uuid.uuid4()),
                    user_id=user.id,
                    created_at=log_time,
                    source_type=source_choice,
                    source_path="Simulation Demo",
                    server_ip="192.168.1.100" if source_choice == 'ssh' else None,
                    stats=stats,
                    segments={"ERROR": [], "WARNING": [], "INFO": []},
                    meta={"status": ai_status, "score": ai_score, "menaces": ai_menaces},
                    ai_score=ai_score,
                    ai_status=ai_status,
                    ai_menaces=ai_menaces
                )
                
                all_objects.append(analysis)
                total_generated += 1

                # Insertion par paquets (Bulk Insert) pour la performance
                if len(all_objects) >= batch_size:
                    db.session.bulk_save_objects(all_objects)
                    db.session.commit()
                    all_objects = []
                    print(f"✅ Paquet de {batch_size} inséré... (Total: {total_generated})")

        # Insertion des objets restants
        if all_objects:
            db.session.bulk_save_objects(all_objects)
            db.session.commit()

        print(f"✨ GÉNÉRATION TERMINÉE ! {total_generated} analyses créées avec succès.")
        
        # Ajout de quelques entrées dans l'AuditLog pour l'historique récent
        print("📝 Ajout de quelques entrées d'audit récentes...")
        audit_samples = [
            AuditLog(username=user.username, action="LOGIN", details="Connexion démo", timestamp=datetime.now(timezone.utc)),
            AuditLog(username=user.username, action="SSH_ANALYZE", details="Scan automatique", timestamp=datetime.now(timezone.utc) - timedelta(minutes=10)),
            AuditLog(username=user.username, action="REPORT_GEN", details="Export PDF", timestamp=datetime.now(timezone.utc) - timedelta(hours=1))
        ]
        db.session.add_all(audit_samples)
        db.session.commit()

if __name__ == "__main__":
    seed_database()
