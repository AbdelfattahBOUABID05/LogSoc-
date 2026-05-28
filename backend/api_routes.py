from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user, login_user, logout_user
from datetime import datetime, timezone, timedelta
import os
import requests
import paramiko
import base64
from itsdangerous import URLSafeTimedSerializer
from werkzeug.utils import secure_filename
from functools import wraps
from utils_security import encrypt_data, decrypt_data
import time

from models import db, Analysis, User, Notification, AnalysisJob, SavedSSHConnection, AdminSavedConnection, SolutionKB

# Cache simple pour le rate limiting de l'endpoint /stats
stats_cache = {}

from utils import (
    generate_security_summary,
    generate_pdf_report_bytes,
    encrypt_ssh_password,
    decrypt_ssh_password,
    encrypt_admin_password,
    decrypt_admin_password,
    generate_user_qr_base64,
    send_report_email_async,
    log_action,
    save_audit
)

api = Blueprint('api', __name__, url_prefix='/api')


def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Extraction du token depuis l'en-tête Authorization
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                parts = auth_header.split()
                if len(parts) == 2:
                    token = parts[1]
        
        if not token:
            current_app.logger.warning("Accès refusé : Token manquant")
            return jsonify({'status': 'error', 'message': 'Token manquant'}), 401
        
        try:
            s = get_serializer()
            # On tente de charger l'ID utilisateur. Salt doit correspondre à celui du login.
            user_id = s.loads(token, salt='auth-token', max_age=86400) # Expire après 24h
            
            user = db.session.get(User, user_id)
            if not user:
                current_app.logger.warning(f"Accès refusé : Utilisateur {user_id} inexistant")
                return jsonify({'status': 'error', 'message': 'Utilisateur non trouvé'}), 401
            
            request.current_user = user
        except Exception as e:
            current_app.logger.error(f"Erreur d'authentification : {str(e)}")
            return jsonify({'status': 'error', 'message': 'Token invalide ou expiré'}), 401
        
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if request.current_user.role != "Admin":
            return jsonify({'status': 'error', 'message': 'Accès réservé aux administrateurs'}), 403
        return f(*args, **kwargs)
    return decorated


def _compute_severity_counts(analysis: Analysis | None) -> dict:
    if not analysis:
        return {"high": 0, "medium": 0, "low": 0}
    meta = analysis.meta or {}
    if isinstance(meta.get("severity_counts"), dict):
        counts = meta["severity_counts"]
        return {
            "high": int(counts.get("high", counts.get("Critique", 0))),
            "medium": int(counts.get("medium", counts.get("Moyen", 0))),
            "low": int(counts.get("low", counts.get("Faible", 0)))
        }
    stats = analysis.stats or {}
    return {
        "high": int(stats.get("errors", 0)),
        "medium": int(stats.get("warnings", 0)),
        "low": int(stats.get("info", 0))
    }

@api.route('/auth/me', methods=['GET'])
@token_required
def get_me():
    user = request.current_user
    return jsonify({
        "status": "success",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "email": user.email,
            "isFirstLogin": user.is_first_login
        }
    })

@api.route('/jobs/<int:id>/toggle', methods=['POST'])
@token_required
def toggle_job(id):
    from scheduler import scheduler as apscheduler
    job = db.session.get(AnalysisJob, id)
    if not job:
        return jsonify({"status": "error", "message": "Job introuvable"}), 404
    
    # Inverser le statut
    if job.status == 'active':
        job.status = 'inactive'
        # Suspendre dans APScheduler
        job_id = f"analysis_job_{job.id}"
        if apscheduler.get_job(job_id):
            apscheduler.pause_job(job_id)
    else:
        job.status = 'active'
        # Reprendre dans APScheduler
        job_id = f"analysis_job_{job.id}"
        if apscheduler.get_job(job_id):
            apscheduler.resume_job(job_id)
        else:
            # Si le job n'est pas dans le scheduler, le rajouter
            from scheduler import schedule_job
            schedule_job(job)

    db.session.commit()
    return jsonify({
        "status": "success", 
        "new_status": job.status,
        "message": f"Job {'activé' if job.status == 'active' else 'désactivé'}"
    })

@api.route('/notifications', methods=['GET'])
@token_required
def get_notifications():
    user = request.current_user
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(50).all()
    
    return jsonify({
        "status": "success",
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "link": n.link
            }
            for n in notifications
        ]
    })

@api.route('/notifications/<int:notif_id>/read', methods=['POST'])
@token_required
def mark_notification_read(notif_id):
    user = request.current_user
    notification = Notification.query.filter_by(id=notif_id, user_id=user.id).first()
    
    if not notification:
        return jsonify({"status": "error", "message": "Notification introuvable"}), 404
        
    notification.is_read = True
    db.session.commit()
    return jsonify({"status": "success"})

@api.route('/login', methods=['POST'])
def login():
    """
    Gère l'authentification des utilisateurs.
    Vérifie les identifiants et génère un token JWT sécurisé pour la session.
    """
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password')):
        s = get_serializer()
        # Génération du token avec un sel spécifique pour la sécurité
        token = s.dumps(user.id, salt='auth-token')
        
        # Audit Log
        save_audit('LOGIN', 'Connexion réussie', username=user.username)
        
        return jsonify({
            "status": "success", 
            "message": "Connexion réussie",
            "token": token,
            "username": user.username,
            "role": user.role,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "isFirstLogin": user.is_first_login
        })
    return jsonify({"status": "error", "message": "Identifiants invalides"}), 401

@api.route('/logout', methods=['POST'])
@token_required
def logout():
    """Clôture la session utilisateur côté client"""
    return jsonify({"status": "success", "message": "Déconnexion réussie"})

@api.route('/analyses', methods=['GET'])
@token_required
def get_analyses():
    """
    Récupère la liste des analyses effectuées par l'utilisateur.
    Supporte le filtrage par période (24h, 7j, 30j).
    """
    user = request.current_user
    period = request.args.get('period', '7d')
    job_public_id = request.args.get('job_id')  # On récupère l'ID public (UUID)
    now = datetime.now(timezone.utc)
    until = now

    if period == '24h':
        since = now - timedelta(hours=24)
    elif period == '7d':
        since = now - timedelta(days=7)
    elif period == '30d':
        since = now - timedelta(days=30)
    else:
        since = now - timedelta(days=7)

    # Requête avec filtrage temporel et tri décroissant (plus récent en premier)
    query = Analysis.query.filter(
        Analysis.user_id == user.id,
        Analysis.created_at >= since,
        Analysis.created_at <= until
    )
    
    if job_public_id:
        # On filtre par le public_id du Job associé
        query = query.join(AnalysisJob).filter(AnalysisJob.public_id == job_public_id)

    analyses = query.order_by(Analysis.created_at.desc()).limit(100).all()

    return jsonify({
        "status": "success",
        "count": len(analyses),
        "analyses": [
            {
                "id": a.public_id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "source_type": a.source_type,
                "source_path": a.source_path,
                "file_path": a.file_path,
                "server_ip": a.server_ip,
                "job_id": a.job_id,
                "job_name": a.job.name if a.job else None,
                "stats": a.stats,
                "ai_score": a.ai_score,
                "ai_status": a.ai_status,
                "ai_menaces": a.ai_menaces
            }
            for a in analyses
        ]
    })

@api.route('/analyses/<string:public_id>', methods=['GET'])
@token_required
def get_analysis(public_id):
    """Récupère les détails complets d'une analyse spécifique via son ID public (UUID)"""
    user = request.current_user
    a = Analysis.query.filter_by(public_id=public_id, user_id=user.id).first()
    if not a:
        return jsonify({"status": "error", "message": "Analyse introuvable"}), 404

    return jsonify({
        "status": "success",
        "analysis": {
            "id": a.public_id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "source_type": a.source_type,
            "source_path": a.source_path,
            "file_path": a.file_path,
            "server_ip": a.server_ip,
            "stats": a.stats,
            "segments": a.segments,
            "meta": a.meta,
            "ai_score": a.ai_score,
            "ai_status": a.ai_status,
            "ai_menaces": a.ai_menaces
        }
    })

@api.route('/analyses/<string:public_id>/pdf', methods=['GET'])
@token_required
def get_analysis_pdf(public_id):
    user = request.current_user
    a = Analysis.query.filter_by(public_id=public_id, user_id=user.id).first()
    if not a:
        return jsonify({"status": "error", "message": "Analyse introuvable"}), 404
    
    from flask import make_response
    pdf_bytes = generate_pdf_report_bytes(a)
    if not pdf_bytes:
        return jsonify({"status": "error", "message": "Erreur lors de la génération du PDF"}), 500
    
    # Audit Log
    save_audit(
        action="EXPORT_PDF",
        details=f"Rapport PDF généré pour l'analyse (Public ID: {public_id}, Source: {a.source_path})"
    )
        
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Rapport_Audit_{public_id}.pdf'
    return response

@api.route('/analyses/<string:public_id>', methods=['DELETE'])
@token_required
def delete_analysis(public_id):
    user = request.current_user
    a = Analysis.query.filter_by(public_id=public_id, user_id=user.id).first()
    if not a:
        return jsonify({"status": "error", "message": "Analyse introuvable"}), 404
    
    db.session.delete(a)
    db.session.commit()
    return jsonify({"status": "success", "message": "Analyse supprimée"})

@api.route('/stats', methods=['GET'])
@token_required
def get_stats():
    """
    Cette route génère les statistiques agrégées pour le tableau de bord SOC.
    Elle regroupe les données par période (H, D, M, Y) et sépare 
    les sources (SSH, Local, Jobs) pour un affichage multi-séries.
    """
    user = request.current_user
    
    # Protection contre le spam (Rate Limiting simple : 1 requête par seconde par utilisateur)
    now_ts = time.time()
    last_call = stats_cache.get(user.id, 0)
    if now_ts - last_call < 1:
        return jsonify({"status": "warning", "message": "Trop de requêtes. Veuillez patienter."}), 429
    stats_cache[user.id] = now_ts

    # Récupération du paramètre de filtrage temporel (H, D, M, Y)
    # H: 24h (Heure par Heure), D: 7 ou 30 jours (Jour par Jour)
    # M: Mois en cours (Jour par Jour), Y: Année (Mois par Mois)
    time_range = request.args.get('time_range', 'D').upper() 
    now = datetime.now(timezone.utc)
    until = now

    # Configuration dynamique de la fenêtre temporelle et du formatage SQL
    if time_range == 'H':
        since = now - timedelta(hours=24)
        group_fmt = '%Y-%m-%d %H:00' # Groupement par heure
        step = timedelta(hours=1)
        label_fmt = '%H:00'          # Affichage: 14:00
    elif time_range == 'D':
        since = now - timedelta(days=7) # Par défaut 7 jours pour le mode "D"
        group_fmt = '%Y-%m-%d'       # Groupement par jour
        step = timedelta(days=1)
        label_fmt = '%d %b'          # Affichage: 03 Mai
    elif time_range == 'M':
        # Derniers 30 jours pour le mode "M"
        since = now - timedelta(days=30)
        group_fmt = '%Y-%m-%d'
        step = timedelta(days=1)
        label_fmt = '%d %b'
    elif time_range == 'Y':
        since = now - timedelta(days=365)
        group_fmt = '%Y-%m'          # Groupement par mois pour l'année
        step = timedelta(days=30)
        label_fmt = '%b %Y'          # Affichage: Mai 2026
    else:
        since = now - timedelta(days=7)
        group_fmt = '%Y-%m-%d'
        step = timedelta(days=1)
        label_fmt = '%d %b'

    def _get_isolated_source_stats(source_type):
        """
        Fonction interne pour isoler les statistiques d'une source spécifique.
        Source_type peut être 'ssh', 'local' (upload), ou 'job' (scheduled).
        Mappage corrigé pour correspondre aux tags de l'Historique.
        """
        # Mappage des types de source pour correspondre à la base de données (source_type)
        if source_type == 'local':
            db_source = 'upload'
        elif source_type == 'job':
            db_source = 'scheduled'
        else:
            db_source = 'ssh'
        
        # Requête SQL isolée par utilisateur et type de source
        analyses = Analysis.query.filter(
            Analysis.user_id == user.id,
            Analysis.source_type == db_source,
            Analysis.created_at >= since,
            Analysis.created_at <= until
        ).order_by(Analysis.created_at.asc()).all()

        # Initialisation des "buckets" temporels
        buckets = {}
        labels_map = {} 
        cursor = since
        while cursor <= until:
            key = cursor.strftime(group_fmt)
            display_label = cursor.strftime(label_fmt)
            buckets[key] = 0
            labels_map[key] = display_label
            cursor += step
        
        # Remplissage avec le nombre total de logs détectés
        for a in analyses:
            key = a.created_at.strftime(group_fmt)
            if key in buckets:
                astats = a.stats or {}
                # Si 'total' est absent ou 0, on essaie de compter les segments ou on met 1 par défaut
                count = int(astats.get('total', 0))
                if count == 0 and a.segments:
                    count = sum(len(v) for v in a.segments.values())
                if count == 0:
                    count = 1 # Au moins un point pour l'analyse
                
                buckets[key] += count
            
        sorted_keys = sorted(buckets.keys())
        
        return {
            "labels": [labels_map[k] for k in sorted_keys],
            "data": [buckets[k] for k in sorted_keys]
        }

    # Récupération des 3 séries distinctes demandées par le frontend
    ssh_data = _get_isolated_source_stats('ssh')
    local_data = _get_isolated_source_stats('local')
    job_data = _get_isolated_source_stats('job')

    # RÉPLICATION DU SPLIT 3-VOIES (Backend) :
    # Chaque source est isolée pour garantir que le frontend puisse s'abonner 
    # à des flux de données indépendants. Utile pour la scalabilité et le temps réel.
    ssh_data = _get_isolated_source_stats('ssh')
    local_data = _get_isolated_source_stats('local')
    job_data = _get_isolated_source_stats('job')

    # Retourne 3 objets distincts au lieu d'une liste de séries.
    # Format exigé : ssh_data, local_data, jobs_data
    return jsonify({
        "status": "success",
        "labels": ssh_data['labels'],
        "ssh_data": {
            "labels": ssh_data['labels'],
            "series": [{"name": "Activité SSH", "data": ssh_data['data']}]
        },
        "local_data": {
            "labels": local_data['labels'],
            "series": [{"name": "Analyse des Logs Système", "data": local_data['data']}]
        },
        "jobs_data": {
            "labels": job_data['labels'],
            "series": [{"name": "Statistiques des Jobs", "data": job_data['data']}]
        }
    })

@api.route('/dashboard', methods=['GET'])
@token_required
def get_dashboard():
    user = request.current_user
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    last_analysis = Analysis.query.filter_by(
        user_id=user.id
    ).order_by(Analysis.created_at.desc()).first()

    recent_analyses = Analysis.query.filter(
        Analysis.user_id == user.id,
        Analysis.created_at >= seven_days_ago
    ).order_by(Analysis.created_at.desc()).limit(5).all()

    total_audits = Analysis.query.filter_by(user_id=user.id).count()
    active_servers = db.session.query(Analysis.server_ip).filter(
        Analysis.user_id == user.id,
        Analysis.server_ip != None
    ).distinct().count()

    critical_threats = sum((a.ai_menaces if a.ai_menaces is not None else 0) for a in recent_analyses)
    scores = [(a.ai_score if a.ai_score is not None else 70) for a in recent_analyses]
    system_health = round(sum(scores) / len(scores)) if scores else 100

    results = None
    if last_analysis:
        severity_counts = _compute_severity_counts(last_analysis)
        meta = dict(last_analysis.meta or {})
        meta["severity_counts"] = severity_counts
        results = {
            "analysis_id": last_analysis.public_id,
            "created_at": last_analysis.created_at.isoformat() if last_analysis.created_at else None,
            "server_ip": last_analysis.server_ip,
            "ai_score": last_analysis.ai_score,
            "ai_status": last_analysis.ai_status,
            "ai_menaces": last_analysis.ai_menaces,
            "meta": meta,
            "stats": last_analysis.stats,
            "severity_counts": severity_counts
        }

    return jsonify({
        "status": "success",
        "analysis_data": results,
        "meta": results["meta"] if results else {},
        "severity_counts": results["severity_counts"] if results else {"high": 0, "medium": 0, "low": 0},
        "summary": {
            "total_audits": total_audits,
            "active_servers": active_servers,
            "critical_threats": critical_threats,
            "system_health": system_health
        },
        "recent_activities": [
            {
                "id": a.id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "server_ip": a.server_ip,
                "ai_status": a.ai_status,
                "ai_score": a.ai_score
            }
            for a in recent_analyses
        ]
    })

@api.route('/ssh/analyze', methods=['POST'])
@token_required
def ssh_analyze():
    """
    Effectue une analyse de logs à distance via SSH.
    Se connecte au serveur, récupère les logs, les parse et génère un rapport IA.
    """
    user = request.current_user
    data = request.get_json()
    host = data.get('host')
    ssh_user = data.get('user')
    pwd = data.get('pass')
    file_path = data.get('filePath', '/var/log/syslog')
    num_lines = data.get('numLines')
    
    # Construction de la commande pour récupérer les logs
    if num_lines and str(num_lines).isdigit():
        cmd = f"tail -n {num_lines} {file_path}"
    else:
        # Si non spécifié, on lit tout le fichier (via cat)
        cmd = f"cat {file_path}"

    try:
        # Initialisation de la connexion SSH avec Paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=ssh_user, password=pwd, timeout=15)
        
        # Exécution efficace : streaming direct du flux SSH vers un fichier temporaire
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        temp_path = f"temp_ssh_{user.id}.log"
        with open(temp_path, "w", encoding="utf-8") as f:
            # Lecture par chunks pour ne pas saturer la RAM
            while True:
                chunk = stdout.read(1024 * 1024).decode('utf-8', errors='replace')
                if not chunk:
                    break
                f.write(chunk)
        
        ssh_err = stderr.read().decode('utf-8', errors='replace')
        ssh.close()

        # Pour l'IA, on récupère un échantillon (les 100000 premiers caractères) si le fichier est géant
        # pour éviter de faire planter generate_security_summary
        with open(temp_path, "r", encoding="utf-8", errors='ignore') as f:
            log_content = f.read(100000)

        if ssh_err and os.path.getsize(temp_path) == 0:
            if os.path.exists(temp_path): os.remove(temp_path)
            return jsonify({"status": "error", "message": f"Erreur SSH: {ssh_err}"}), 500

        # Parsing des logs via le moteur interne (lecture ligne par ligne optimisée)
        from src.parser import parse_log_file
        results = parse_log_file(temp_path)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # --- AUTOMATISATION : Smart Matching KB & Notifications ---
        kb_solutions = SolutionKB.query.all()
        matched_solutions = []
        
        critical_logs = results.get('ERROR', []) + results.get('WARNING', [])
        for log in critical_logs:
            for sol in kb_solutions:
                if sol.log_pattern.lower() in log.lower():
                    if sol.id not in [s['id'] for s in matched_solutions]:
                        matched_solutions.append({
                            "id": sol.id,
                            "title": sol.problem_title,
                            "author": sol.author_name
                        })
                        notif = Notification(
                            user_id=user.id,
                            title="Solution Détectée (SSH)",
                            message=f"Solution trouvée par {sol.author_name} pour ce problème : {sol.problem_title}",
                            type="success",
                            link=f"/knowledge-base?highlight={sol.id}"
                        )
                        db.session.add(notif)

        # Calcul des statistiques de base
        stats = {
            "errors": len(results.get('ERROR', [])),
            "warnings": len(results.get('WARNING', [])),
            "info": len(results.get('INFO', [])),
            "total": sum(len(v) for v in results.values()),
            "kb_matches": len(matched_solutions)
        }

        # Génération du résumé de sécurité par l'IA (sur l'échantillon prélevé)
        ai_metrics = generate_security_summary(model=None, log_text=log_content)
        
        # Enregistrement de l'analyse dans la base de données
        analysis = Analysis(
            user_id=user.id,
            source_type="ssh",
            source_path=host,
            file_path=file_path,
            server_ip=host,
            stats=stats,
            segments=results,
            meta=ai_metrics,
            ai_score=ai_metrics.get("score", 70),
            ai_status=ai_metrics.get("status", "Normal"),
            ai_menaces=ai_metrics.get("menaces", 0)
        )
        db.session.add(analysis)
        
        # Enregistrement de l'action dans l'audit (Dynamique)
        save_audit(
            action="SSH_ANALYZE",
            details=f"Analyse lancée sur le serveur {host} (Cible: {file_path})"
        )

        db.session.commit()

        return jsonify({"status": "success", "analysis_id": analysis.public_id})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de l'analyse SSH : {str(e)}"}), 500


@api.route('/settings', methods=['GET', 'POST'])
@token_required
def settings():
    user = request.current_user
    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "settings": {
                "emailNotifications": bool(user.email_notifications_enabled),
                "notificationEmail": user.notification_email or user.email or "",
                "smtpServer": user.smtp_server or "",
                "smtpPort": user.smtp_port or 587,
                "smtpUser": user.email_sender or "",
                "smtpPassword": ""
            }
        })

    data = request.get_json() or {}
    user.email_notifications_enabled = bool(data.get("emailNotifications", False))
    user.notification_email = (data.get("notificationEmail") or "").strip() or None
    user.smtp_server = (data.get("smtpServer") or "").strip() or None
    user.smtp_port = int(data.get("smtpPort", 587)) if data.get("smtpPort") is not None else None
    user.email_sender = (data.get("smtpUser") or "").strip() or None

    # Keep current behavior simple: only update password if explicitly provided.
    smtp_password = (data.get("smtpPassword") or "").strip()
    if smtp_password:
        user.email_password_enc = encrypt_data(smtp_password)

    db.session.commit()
    return jsonify({"status": "success", "message": "Paramètres enregistrés avec succès"})

@api.route('/analyze-local', methods=['POST'])
@token_required
def analyze_local():
    """
    Route pour l'analyse de fichiers logs locaux (Upload).
    Incorpore désormais le Smart Matching avec la Base de Connaissances.
    """
    user = request.current_user
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Aucun fichier fourni"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Nom de fichier vide"}), 400

    filename = secure_filename(file.filename)
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Préfixer le nom du fichier avec l'ID utilisateur pour éviter les conflits
    file_path = os.path.join(upload_dir, f"{user.id}_{filename}")
    file.save(file_path)

    num_lines = request.form.get('numLines')

    try:
        from src.parser import parse_log_file
        
        # Lecture optimisée : Si numLines est défini, on utilise tail-like logic
        # Sinon, on lit tout le fichier ligne par ligne (efficace pour gros fichiers)
        if num_lines and str(num_lines).isdigit():
            with open(file_path, "r", encoding="utf-8", errors='replace') as f:
                lines = f.readlines()
            n = int(num_lines)
            log_content = "".join(lines[-n:])
        else:
            # Lecture intégrale efficace
            with open(file_path, "r", encoding="utf-8", errors='replace') as f:
                log_content = f.read()

        # On sauvegarde le contenu traité dans un fichier temporaire pour le parser
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log_content)

        # Pour l'IA, on limite la taille du texte à analyser (100k chars max)
        # pour éviter de saturer la RAM sur des fichiers géants
        ai_log_sample = log_content[:100000]

        results = parse_log_file(file_path)
        
        # --- AUTOMATISATION : Smart Matching KB & Notifications ---
        kb_solutions = SolutionKB.query.all()
        matched_solutions = []
        
        # On vérifie les logs d'erreurs et de warnings pour des solutions connues
        critical_logs = results.get('ERROR', []) + results.get('WARNING', [])
        
        for log in critical_logs:
            for sol in kb_solutions:
                if sol.log_pattern.lower() in log.lower():
                    if sol.id not in [s['id'] for s in matched_solutions]:
                        matched_solutions.append({
                            "id": sol.id,
                            "title": sol.problem_title,
                            "author": sol.author_name
                        })
                        # Création d'une notification pour l'utilisateur avec attribution
                        notif = Notification(
                            user_id=user.id,
                            title="Solution Détectée",
                            message=f"Solution trouvée par {sol.author_name} pour ce problème : {sol.problem_title}",
                            type="success",
                            link=f"/knowledge-base?highlight={sol.id}"
                        )
                        db.session.add(notif)
        
        # Calcul des statistiques
        stats = {
            "errors": len(results.get('ERROR', [])),
            "warnings": len(results.get('WARNING', [])),
            "info": len(results.get('INFO', [])),
            "total": sum(len(v) for v in results.values()),
            "kb_matches": len(matched_solutions)
        }

        # Analyse IA avec Gemini (sur l'échantillon prélevé)
        ai_metrics = generate_security_summary(model=None, log_text=ai_log_sample)
        
        # Sauvegarde dans le modèle Analysis
        analysis = Analysis(
            user_id=user.id,
            source_type="upload",
            source_path=filename,
            file_path=file_path,
            stats=stats,
            segments=results,
            meta=ai_metrics,
            ai_score=ai_metrics.get("score", 70),
            ai_status=ai_metrics.get("status", "Normal"),
            ai_menaces=ai_metrics.get("menaces", 0)
        )
        db.session.add(analysis)
        
        # Audit Log
        save_audit(
            action="LOCAL_ANALYZE",
            details=f"Analyse du fichier {filename} lancée ({stats.get('total', 0)} logs traités)"
        )

        db.session.commit()

        return jsonify({
            "status": "success", 
            "message": "Analyse terminée avec succès",
            "analysis_id": analysis.public_id,
            "kb_matches": matched_solutions
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Erreur lors de l'analyse : {str(e)}"}), 500
    finally:
        # Nettoyage du fichier temporaire
        if os.path.exists(file_path):
            os.remove(file_path)

@api.route('/upload', methods=['POST'])
@token_required
def upload_file():
    user = request.current_user
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Aucun fichier fourni"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Nom de fichier vide"}), 400

    filename = secure_filename(file.filename)
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, f"{user.id}_{filename}")
    file.save(file_path)

    try:
        from src.parser import parse_log_file
        results = parse_log_file(file_path)
        
        with open(file_path, "r", encoding="utf-8", errors='replace') as f:
            log_content = f.read()

        # Optimisation IA : Échantillon de 100k caractères
        ai_log_sample = log_content[:100000]

        stats = {
            "errors": len(results.get('ERROR', [])),
            "warnings": len(results.get('WARNING', [])),
            "info": len(results.get('INFO', [])),
            "total": sum(len(v) for v in results.values())
        }

        ai_metrics = generate_security_summary(model=None, log_text=ai_log_sample)
        
        analysis = Analysis(
            user_id=user.id,
            source_type="upload",
            source_path=filename,
            stats=stats,
            segments=results,
            meta=ai_metrics,
            ai_score=ai_metrics.get("score", 70),
            ai_status=ai_metrics.get("status", "Normal"),
            ai_menaces=ai_metrics.get("menaces", 0)
        )
        db.session.add(analysis)
        db.session.commit()

        return jsonify({"status": "success", "analysis_id": analysis.public_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- User: Jobs Management ---

@api.route('/jobs', methods=['GET'])
@token_required
def get_user_jobs():
    from models import AnalysisJob
    user = request.current_user
    jobs = AnalysisJob.query.filter_by(user_id=user.id).all()
    return jsonify({
        "status": "success",
        "jobs": [
            {
                "id": j.id,
                "public_id": j.public_id,
                "name": j.name,
                "target_ip": j.target_ip,
                "log_path": j.log_path,
                "frequency": j.frequency,
                "custom_interval": j.custom_interval,
                "custom_unit": j.custom_unit,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None
            }
            for j in jobs
        ]
    })

@api.route('/jobs', methods=['POST'])
@token_required
def create_user_job():
    from models import AnalysisJob, Notification
    user = request.current_user
    data = request.get_json()
    
    new_job = AnalysisJob(
        user_id=user.id,
        name=(data.get('name') or f"Job {data.get('target_ip')}").strip(),
        target_ip=data.get('target_ip'),
        log_path=data.get('log_path', '/var/log/syslog'),
        frequency=data.get('frequency', 'daily'),
        custom_interval=data.get('custom_interval') if data.get('frequency') == 'custom' else None,
        custom_unit=data.get('custom_unit') if data.get('frequency') == 'custom' else None,
        ssh_username=data.get('ssh_user'),
        ssh_password_enc=encrypt_data(data.get('ssh_pass')),
        status='pending'
    )
    db.session.add(new_job)
    db.session.flush() # Pour avoir l'ID du job

    # Audit Log
    save_audit(
        action="JOB_CREATED",
        details=f"Nouveau job planifié : {new_job.name} sur {new_job.target_ip} (Frequence: {new_job.frequency})"
    )

    # Alerter les admins
    admins = User.query.filter_by(role='Admin').all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="Nouvelle demande de Job",
            message=f"L'analyste {user.username} a cree la demande '{new_job.name}' pour {new_job.target_ip}.",
            type="info",
            link=f"/admin/jobs"
        )
        db.session.add(notif)

    db.session.commit()
    return jsonify({"status": "success", "message": "Demande de job créée et en attente de validation Admin"})

@api.route('/jobs/<int:job_id>', methods=['DELETE'])
@token_required
def delete_user_job(job_id):
    from models import AnalysisJob
    user = request.current_user
    job = AnalysisJob.query.filter_by(id=job_id, user_id=user.id).first()
    if not job:
        return jsonify({"status": "error", "message": "Job introuvable"}), 404
    
    # Retirer du scheduler si actif
    if job.status == 'active':
        from extensions import scheduler as apscheduler
        job_id_sched = f"analysis_job_{job.id}"
        if apscheduler.get_job(job_id_sched):
            apscheduler.remove_job(job_id_sched)

    # Audit Log
    save_audit(
        action="JOB_DELETED",
        details=f"Job #{job_id} supprimé (Cible: {job.target_ip})"
    )

    db.session.delete(job)
    db.session.commit()
    return jsonify({"status": "success", "message": "Job supprimé"})


@api.route('/email/send-report', methods=['POST'])
@token_required
def send_report_email():
    user = request.current_user
    data = request.get_json()
    public_id = data.get('analysis_id') # Le frontend enverra maintenant le public_id
    recipient = data.get('recipient') or data.get('email') or user.notification_email or user.email
    
    if not public_id or not recipient:
        return jsonify({"status": "error", "message": "ID d'analyse ou destinataire manquant"}), 400
        
    analysis = Analysis.query.filter_by(public_id=public_id, user_id=user.id).first()
    if not analysis:
        return jsonify({"status": "error", "message": "Analyse introuvable"}), 404
        
    # 1. Configuration SMTP
    # Authentication utilizes real Mailtrap credentials, while the display sender is virtual
    smtp_config = {
        'server': user.smtp_server or os.getenv("SMTP_SERVER", "sandbox.smtp.mailtrap.io"),
        'port': user.smtp_port or int(os.getenv("SMTP_PORT", 2525)),
        'user': os.getenv("SMTP_USER", "b1d332e315f09f"), # Mailtrap username
        'password': os.getenv("SMTP_PASSWORD", "78b1eb63687425"), # Mailtrap password
        'display_user': user.email_sender or "abdelfattahbouabid@pwd.pfe.ma", # Virtual domain for From
        'use_tls': os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    }

    # 2. Génération du PDF
    pdf_bytes = generate_pdf_report_bytes(analysis)
    if not pdf_bytes:
        return jsonify({"status": "error", "message": "Erreur lors de la génération du PDF"}), 500
        
    # 3. Préparation du contenu
    subject = data.get('subject') or f"Rapport d'Audit Logs SOC - {analysis.server_ip or 'Local'}"
    date_str = analysis.created_at.strftime('%d/%m/%Y %H:%M') if analysis.created_at else "N/A"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #4f46e5; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;">Rapport d'Audit SOC</h2>
            <p>Bonjour,</p>
            <p>Veuillez trouver ci-joint le rapport d'analyse technique généré par le système SOC LogAnalyzer.</p>
            <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>ID Analyse :</strong> {analysis.public_id}</p>
                <p style="margin: 5px 0;"><strong>Score Sécurité :</strong> {analysis.ai_score}/100</p>
                <p style="margin: 5px 0;"><strong>Statut :</strong> {analysis.ai_status}</p>
                <p style="margin: 5px 0;"><strong>Source :</strong> {analysis.server_ip if analysis.source_type == 'SSH' else 'Hôte Local'}</p>
                <p style="margin: 5px 0;"><strong>Date :</strong> {date_str}</p>
            </div>
            <p style="font-size: 12px; color: #64748b;">Ce document est confidentiel et authentifié par l'expert via QR Code.</p>
        </div>
    </body>
    </html>
    """
    
    # 4. Envoi asynchrone
    send_report_email_async(
        current_app._get_current_object(),
        smtp_config,
        recipient,
        subject,
        html_body,
        pdf_bytes,
        f"Rapport_Audit_{public_id}.pdf"
    )

    return jsonify({
        "status": "success", 
        "message": f"L'envoi du rapport à {recipient} a été initié en arrière-plan."
    })


# --- Admin: User Management ---

@api.route('/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    users = User.query.all()
    return jsonify({
        "status": "success",
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "firstName": u.first_name,
                "lastName": u.last_name,
                "role": u.role,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ]
    })

@api.route('/admin/users', methods=['POST'])
@admin_required
def admin_create_user():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'Analyseur')
    first_name = data.get('firstName')
    last_name = data.get('lastName')

    if not username or not email or not password:
        return jsonify({"status": "error", "message": "Données manquantes"}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"status": "error", "message": "Nom d'utilisateur ou email déjà utilisé"}), 400

    user = User(
        username=username,
        email=email,
        role=role,
        first_name=first_name,
        last_name=last_name
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"status": "success", "message": "Utilisateur créé avec succès"})

@api.route('/admin/users/<int:user_id>', methods=['PUT', 'DELETE'])
@admin_required
def admin_update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "Utilisateur introuvable"}), 404

    if request.method == 'DELETE':
        if user.id == request.current_user.id:
            return jsonify({"status": "error", "message": "Vous ne pouvez pas supprimer votre propre compte"}), 400
        db.session.delete(user)
        db.session.commit()
        return jsonify({"status": "success", "message": "Utilisateur supprimé"})

    data = request.get_json()
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    user.role = data.get('role', user.role)
    user.first_name = data.get('firstName', user.first_name)
    user.last_name = data.get('lastName', user.last_name)

    new_password = data.get('password')
    if new_password:
        user.set_password(new_password)

    db.session.commit()
    return jsonify({"status": "success", "message": "Utilisateur mis à jour"})


# --- Admin: Job Management ---

@api.route('/admin/jobs', methods=['GET'])
@admin_required
def admin_get_jobs():
    from models import AnalysisJob
    jobs = AnalysisJob.query.all()
    return jsonify({
        "status": "success",
        "jobs": [
            {
                "id": j.id,
                "user_id": j.user_id,
                "username": j.user.username,
                "target_ip": j.target_ip,
                "log_path": j.log_path,
                "frequency": j.frequency,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None
            }
            for j in jobs
        ]
    })

@api.route('/admin/jobs/<int:job_id>/approve', methods=['POST'])
@admin_required
def admin_approve_job(job_id):
    from models import AnalysisJob, Notification
    job = db.session.get(AnalysisJob, job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job introuvable"}), 404

    data = request.get_json()
    action = data.get('action') # approve | refuse
    reason = data.get('reason', '')

    if action == 'approve':
        job.status = 'active'
        job.approved_at = datetime.now(timezone.utc)
        
        # Planifier le job dans APScheduler
        from scheduler import schedule_job
        try:
            schedule_job(job)
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la planification du job {job.id}: {e}")
            return jsonify({"status": "error", "message": "Erreur lors de la planification technique du job"}), 500

        # Notification à l'utilisateur
        notif = Notification(
            user_id=job.user_id,
            title="Job Approuvé",
            message=f"Votre demande d'analyse pour {job.target_ip} a été approuvée.",
            type="success",
            link="/jobs"
        )
        db.session.add(notif)
        
    elif action == 'refuse':
        job.status = 'refused'
        job.refusal_reason = reason or 'Refusé par l\'administrateur'
        
        # Notification à l'utilisateur avec motif
        notif = Notification(
            user_id=job.user_id,
            title="Job Refusé",
            message=f"Votre demande pour {job.target_ip} a été refusée. Motif : {job.refusal_reason}",
            type="error",
            link="/jobs"
        )
        db.session.add(notif)
    else:
        return jsonify({"status": "error", "message": "Action invalide"}), 400

    db.session.commit()
    return jsonify({"status": "success", "message": f"Job {action}d avec succès"})


# --- Admin: Remote Console (SSH Terminal) ---

@api.route('/admin/console', methods=['POST'])
@admin_required
def admin_remote_console():
    user = request.current_user
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON invalide ou manquant"}), 400
            
        host = data.get('host')
        ssh_user = data.get('username') # Aligné avec le frontend
        pwd = data.get('password')      # Aligné avec le frontend
        cmd = data.get('command')

        if not all([host, ssh_user, pwd, cmd]):
            missing = [k for k, v in {'host': host, 'username': ssh_user, 'password': pwd, 'command': cmd}.items() if not v]
            return jsonify({
                "status": "error", 
                "message": f"Données SSH manquantes: {', '.join(missing)}",
                "received_keys": list(data.keys())
            }), 400

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=ssh_user, password=pwd, timeout=10)
        
        # Sauvegarde de la connexion Admin sur succès
        try:
            encrypted_pwd = encrypt_admin_password(pwd)
            existing_conn = AdminSavedConnection.query.filter_by(
                user_id=user.id, host=host, username=ssh_user
            ).first()
            
            if existing_conn:
                existing_conn.encrypted_password = encrypted_pwd
                existing_conn.last_used_at = datetime.now(timezone.utc)
            else:
                new_conn = AdminSavedConnection(
                    user_id=user.id,
                    host=host,
                    username=ssh_user,
                    encrypted_password=encrypted_pwd
                )
                db.session.add(new_conn)
            
            db.session.commit()
            
            # Limiter à 3 connexions pour la console admin
            admin_conns = AdminSavedConnection.query.filter_by(user_id=user.id)\
                .order_by(AdminSavedConnection.last_used_at.desc()).all()
            
            if len(admin_conns) > 3:
                for old_conn in admin_conns[3:]:
                    db.session.delete(old_conn)
                db.session.commit()
        except Exception as save_err:
            current_app.logger.error(f"Erreur sauvegarde Console Admin: {str(save_err)}")

        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8', errors='replace')
        error = stderr.read().decode('utf-8', errors='replace')
        ssh.close()

        # Enregistrement de l'action dans l'audit
        save_audit(
            action="SSH_COMMAND",
            details=f"Host: {host} | Command: {cmd}"
        )

        return jsonify({
            "status": "success",
            "output": output,
            "error": error
        })
    except Exception as e:
        current_app.logger.error(f"Erreur Console Admin: {str(e)}")
        return jsonify({"status": "error", "message": f"Erreur Console: {str(e)}"}), 500


@api.route('/admin/console/recent', methods=['GET'])
@admin_required
def get_admin_console_recent():
    user = request.current_user
    connections = AdminSavedConnection.query.filter_by(user_id=user.id)\
        .order_by(AdminSavedConnection.last_used_at.desc()).limit(3).all()
    
    return jsonify({
        "status": "success",
        "connections": [
            {
                "id": c.id,
                "host": c.host,
                "username": c.username,
                "password": decrypt_admin_password(c.encrypted_password),
                "last_used_at": c.last_used_at.isoformat()
            }
            for c in connections
        ]
    })


@api.route('/admin/audit-logs', methods=['GET'])
@admin_required
def get_audit_logs():
    """
    Récupère les 20 dernières actions d'audit pour le dashboard.
    """
    from models import AuditLog
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
    
    return jsonify({
        "status": "success",
        "audit_logs": [log.to_dict() for log in logs]
    })


@api.route('/admin/audit-logs', methods=['POST'])
@admin_required
def create_audit_log_route():
    """
    Permet au frontend d'enregistrer manuellement une action d'audit.
    """
    data = request.get_json()
    action = data.get('action')
    details = data.get('details')
    
    if not action:
        return jsonify({"status": "error", "message": "Action manquante"}), 400
        
    save_audit(
        action=action,
        details=details
    )
    
    return jsonify({"status": "success", "message": "Audit log enregistré"})


# --- User: Profile & Signature ---

@api.route('/kb/solutions', methods=['GET'])
@token_required
def get_kb_solutions():
    print("--- [API] RÉCUPÉRATION DES SOLUTIONS KB ---")
    solutions = SolutionKB.query.order_by(SolutionKB.created_at.desc()).all()
    print(f"Nombre de solutions trouvées en base : {len(solutions)}")
    
    result = [s.to_dict() for s in solutions]
    for s in result:
        print(f"  - Solution ID: {s['id']} | Pattern: '{s['log_pattern']}'")
        
    return jsonify({
        "status": "success",
        "solutions": result
    })

@api.route('/kb/solutions', methods=['POST'])
@token_required
def create_kb_solution():
    print("--- [API] CRÉATION D'UNE SOLUTION KB ---")
    data = request.get_json()
    title = data.get('problem_title')
    pattern = data.get('log_pattern')
    content = data.get('solution_content')
    author = data.get('author_name', 'Admin')
    
    print(f"Données reçues : Title='{title}', Pattern='{pattern}', Author='{author}'")

    if not title or not pattern or not content:
        print("❌ Erreur : Champs obligatoires manquants")
        return jsonify({"status": "error", "message": "Tous les champs sont obligatoires"}), 400

    new_solution = SolutionKB(
        problem_title=title,
        log_pattern=pattern,
        solution_content=content,
        author_name=author
    )
    db.session.add(new_solution)
    db.session.commit()
    print(f"✅ Solution créée avec succès. ID: {new_solution.id}")

    # Audit Log
    save_audit(
        action="KB_ADD",
        details=f"Nouvelle entrée ajoutée : {title} (Pattern: {pattern})"
    )

    return jsonify({
        "status": "success",
        "message": "Solution ajoutée à la base de connaissances",
        "solution": new_solution.to_dict()
    })

@api.route('/kb/solutions/<int:solution_id>', methods=['DELETE'])
@token_required
def delete_kb_solution(solution_id):
    solution = db.session.get(SolutionKB, solution_id)
    if not solution:
        return jsonify({"status": "error", "message": "Solution introuvable"}), 404

    db.session.delete(solution)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Solution supprimée avec succès"
    })

@api.route('/kb/match-pattern', methods=['POST'])
@token_required
def match_kb_pattern():
    """
    Recherche globale de solutions dans la KB pour un pattern de log donné.
    Utilisé par le 'Suggestion Center' du Dashboard.
    """
    data = request.get_json()
    logs = data.get('logs', [])
    
    if not logs:
        return jsonify({"status": "success", "solution": None})

    # Recherche dans toute la base de données (Global Search)
    kb_solutions = SolutionKB.query.all()
    
    for log in logs:
        for sol in kb_solutions:
            if sol.log_pattern.lower() in log.lower():
                return jsonify({
                    "status": "success",
                    "solution": sol.to_dict()
                })
    
    return jsonify({"status": "success", "solution": None})

@api.route('/stats/kb-contributions', methods=['GET'])
@token_required
def get_kb_contributions_stats():
    """
    Retourne les statistiques de contribution à la Base de Connaissances par auteur.
    """
    from sqlalchemy import func
    stats = db.session.query(
        SolutionKB.author_name, 
        func.count(SolutionKB.id).label('count')
    ).group_by(SolutionKB.author_name).all()
    
    return jsonify({
        "status": "success",
        "stats": [
            {"author": s.author_name, "count": s.count} for s in stats
        ]
    })

@api.route('/profile', methods=['GET'])
@token_required
def get_profile():
    user = request.current_user
    return jsonify({
        "status": "success",
        "username": user.username,
        "email": user.email,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "role": user.role,
        "signature_path": user.signature_path
    })

@api.route('/profile/change-password', methods=['POST'])
@token_required
def change_password():
    user = request.current_user
    data = request.get_json()
    old_pass = data.get('old')
    new_pass = data.get('new')

    if not user.check_password(old_pass):
        return jsonify({"status": "error", "message": "Ancien mot de passe incorrect"}), 400

    user.set_password(new_pass)
    user.is_first_login = False # Débloquer l'utilisateur après le premier changement de mot de passe
    db.session.commit()
    return jsonify({"status": "success", "message": "Mot de passe mis à jour"})

import logging

@api.route('/generate-qr', methods=['GET'])
@token_required
def generate_qr():
    """
    Retourne le QR Code de l'utilisateur courant au format Base64.
    Utilise 'request.current_user' injecté par le décorateur @token_required.
    """
    try:
        user = getattr(request, 'current_user', None)
        
        if not user:
            return jsonify({"status": "error", "message": "Utilisateur non authentifié"}), 401
            
        qr_code_base64 = generate_user_qr_base64(user)
        
        if not qr_code_base64:
            return jsonify({"status": "error", "message": "Erreur lors de la génération du QR Code"}), 500
            
        return jsonify({
            "status": "success",
            "qr_code": qr_code_base64
        })
    except Exception as e:
        logging.exception('QR ERROR')
        return jsonify({
            "status": "error",
            "message": f"Une erreur interne est survenue : {str(e)}"
        }), 500




