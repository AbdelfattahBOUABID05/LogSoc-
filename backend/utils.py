import os
import smtplib
import ssl
import json
import re
import dns.resolver
import traceback
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from cryptography.fernet import Fernet
from openai import OpenAI
import logging
from fpdf import FPDF
from flask import current_app
from utils_security import decrypt_data
import qrcode
import io
import base64
import threading
import tempfile

logger = logging.getLogger(__name__)

def send_report_email_async(app, smtp_config, recipient, subject, html_body, pdf_bytes, filename):
    """Envoie un rapport par email de manière asynchrone."""
    def send_thread(app_context):
        with app_context:
            try:
                import smtplib
                import ssl
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                from email.mime.application import MIMEApplication

                logger.info(f"Tentative d'envoi d'email à {recipient} via {smtp_config['server']}:{smtp_config['port']}")
                
                msg = MIMEMultipart("mixed")
                msg['Subject'] = subject
                msg['To'] = recipient
                # Utilisation de l'email virtuel pour le 'From' et l'email réel pour le 'Reply-To'
                msg['From'] = smtp_config.get('display_user') or smtp_config['user']
                msg['Reply-To'] = smtp_config['user']
                msg.attach(MIMEText(html_body, 'html'))
                
                if pdf_bytes:
                    attachment = MIMEApplication(pdf_bytes)
                    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(attachment)

                context = ssl.create_default_context()
                
                # Connexion au serveur SMTP avec retry logic
                server = None
                max_retries = 3
                retry_delay = 5 # secondes
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Tentative d'envoi {attempt + 1}/{max_retries}...")
                        server = smtplib.SMTP(smtp_config['server'], smtp_config['port'], timeout=30)
                        server.set_debuglevel(1)
                        
                        if smtp_config.get('use_tls'):
                            logger.info("Démarrage de TLS...")
                            server.starttls(context=context)
                        
                        if smtp_config.get('password'):
                            logger.info(f"Tentative de connexion pour l'utilisateur: {smtp_config['user']}")
                            server.login(smtp_config['user'], smtp_config['password'])
                        
                        server.send_message(msg)
                        logger.info(f"Email envoyé avec succès à {recipient}")
                        break # Succès, on sort de la boucle de retry
                        
                    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, ConnectionError) as e:
                        logger.warning(f"Erreur réseau temporaire (tentative {attempt + 1}): {str(e)}")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay)
                        else:
                            raise e
                    except smtplib.SMTPAuthenticationError:
                        logger.error(f"Erreur d'authentification SMTP pour {smtp_config['user']}. Vérifiez le mot de passe d'application.")
                        break # Pas de retry pour une erreur d'authentification
                    except Exception as e:
                        logger.error(f"Erreur SMTP spécifique: {str(e)}")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay)
                        else:
                            raise e
                    finally:
                        if server:
                            try:
                                server.quit()
                            except:
                                pass
                            server = None
                            
            except Exception as e:
                logger.error(f"Erreur critique envoi email asynchrone: {str(e)}")

    threading.Thread(
        target=send_thread,
        args=(app.app_context(),)
    ).start()

def encrypt_ssh_password(password: str) -> str:
    """Chiffre un mot de passe SSH."""
    if not password:
        return ""
    try:
        fernet_key = os.getenv("FERNET_KEY") or os.getenv("SECRET_KEY")
        if not fernet_key:
            return password
        
        import base64
        import hashlib
        key = base64.urlsafe_b64encode(hashlib.sha256(fernet_key.encode()).digest())
        f = Fernet(key)
        return f.encrypt(password.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        return password

def decrypt_ssh_password(token: str) -> str:
    """Déchiffre un mot de passe SSH."""
    if not token:
        return ""
    try:
        fernet_key = os.getenv("FERNET_KEY") or os.getenv("SECRET_KEY")
        if not fernet_key:
            return token
            
        import base64
        import hashlib
        key = base64.urlsafe_b64encode(hashlib.sha256(fernet_key.encode()).digest())
        f = Fernet(key)
        return f.decrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        return token

def encrypt_admin_password(password: str) -> str:
    """Chiffre un mot de passe pour la console Admin."""
    if not password:
        return ""
    try:
        # Utilisation de MASTER_CONSOLE_KEY spécifiquement pour l'admin
        fernet_key = os.getenv("MASTER_CONSOLE_KEY") or os.getenv("SECRET_KEY")
        if not fernet_key:
            return password
        
        import base64
        import hashlib
        key = base64.urlsafe_b64encode(hashlib.sha256(fernet_key.encode()).digest())
        f = Fernet(key)
        return f.encrypt(password.encode()).decode()
    except Exception as e:
        logger.error(f"Admin Encryption error: {str(e)}")
        return password

def decrypt_admin_password(token: str) -> str:
    """Déchiffre un mot de passe pour la console Admin."""
    if not token:
        return ""
    try:
        fernet_key = os.getenv("MASTER_CONSOLE_KEY") or os.getenv("SECRET_KEY")
        if not fernet_key:
            return token
            
        import base64
        import hashlib
        key = base64.urlsafe_b64encode(hashlib.sha256(fernet_key.encode()).digest())
        f = Fernet(key)
        return f.decrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Admin Decryption error: {str(e)}")
        return token

def file_metadata(filepath: str) -> dict:
    return {
        "filename": os.path.basename(filepath),
        "filesize": os.path.getsize(filepath),
        "last_modified": datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc).isoformat()
    }

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def log_action(username: str, action: str, details: str = None) -> None:
    """
    Enregistre une action dans l'historique d'audit (AuditLog).
    """
    from models import db, AuditLog
    try:
        new_log = AuditLog(
            username=username,
            action=action,
            details=details
        )
        db.session.add(new_log)
        db.session.commit()
        logger.info(f"[AUDIT] {username} executed {action}")
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de l'audit : {str(e)}")
        db.session.rollback()

def save_audit(action: str, details: str = None, username: str = None) -> None:
    """
    Enregistre une action d'audit en récupérant automatiquement l'utilisateur courant.
    """
    from flask import request
    if not username:
        # Tente de récupérer l'utilisateur depuis la requête (défini par token_required)
        user = getattr(request, 'current_user', None)
        username = user.username if user else "System"
    
    log_action(username, action, details)

def _looks_like_cursor_key(value: str | None) -> bool:
    return bool(value and str(value).strip().startswith("crsr_"))

def _resolve_ai_config():
    raw_gemini = (os.getenv("GEMINI_API_KEY") or "").strip()
    raw_cursor = (os.getenv("CURSOR_API_KEY") or "").strip()
    raw_openai = (os.getenv("OPENAI_API_KEY") or "").strip()

    cursor_key = raw_cursor or (raw_gemini if _looks_like_cursor_key(raw_gemini) else "")
    gemini_key = "" if _looks_like_cursor_key(raw_gemini) else raw_gemini
    openai_key = raw_openai

    cursor_base = (os.getenv("CURSOR_API_BASE_URL") or "https://api.cursor.sh/v1").strip()
    cursor_model = (os.getenv("CURSOR_MODEL") or "gpt-4o-mini").strip()
    return {
        "cursor_key": cursor_key,
        "cursor_base": cursor_base,
        "cursor_model": cursor_model,
        "openai_key": openai_key,
        "openai_base": (os.getenv("OPENAI_BASE_URL") or "").strip() or None,
        "openai_model": (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
        "gemini_key": gemini_key,
    }

def _openai_style_completion(*, api_key: str, base_url: str | None, model_name: str, prompt: str) -> str:
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a senior SOC analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()

def _heuristic_security_summary(log_text: str) -> dict:
    text = str(log_text or "")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    low = text.lower()
    error_hits = sum(1 for t in (" error", "failed", "critical", "denied", "panic", "fatal") if t in low)
    warn_hits = sum(1 for t in (" warning", "warn", "timeout", "retry", "degraded") if t in low)
    auth_hits = sum(1 for t in ("auth", "sudo", "ssh", "login", "invalid user", "permission") if t in low)
    failed_pass_hits = sum(1 for t in ("failed password",) if t in low)

    score = 100 - (error_hits * 5) - (warn_hits * 2) - (failed_pass_hits * 20)
    score = max(0, min(100, score))

    if score > 80:
        status = "Sain"
        level = "LOW"
    elif score >= 50:
        status = "Attention"
        level = "MEDIUM"
    else:
        status = "Critique"
        level = "HIGH"

    if error_hits >= 3 or failed_pass_hits >= 3:
        level = "CRITICAL"

    summary = (
        f"Automated security analysis processed {len(lines)} log lines. "
        f"Detected {error_hits} critical/error indicators, {warn_hits} warning indicators, "
        f"and {auth_hits} authentication signals including {failed_pass_hits} failed login attempts. "
        "Review repeated failures and access anomalies, then validate related services."
    )
    return {
        "ai_insights": summary, 
        "security_level": level,
        "score": score,
        "status": status,
        "menaces": error_hits + failed_pass_hits,
        "severity_counts": {"Critique": error_hits, "Moyen": warn_hits, "Faible": auth_hits},
        "activity_trend": [],
        "audit_points": [
            f"Détection de {error_hits} erreurs critiques.",
            f"Détection de {warn_hits} avertissements.",
            f"Détection de {failed_pass_hits} échecs d'authentification."
        ]
    }

def get_gemini_model():
    """Helper to get Gemini model globally using latest stable model."""
    import google.generativeai as genai
    from google.api_core import exceptions
    
    cfg = _resolve_ai_config()
    api_key = cfg.get("gemini_key")
    if not api_key:
        logger.error("GEMINI_API_KEY non configurée dans l'environnement")
        raise RuntimeError("Missing GEMINI_API_KEY")
        
    try:
        # Utilisation de la configuration stable du SDK
        genai.configure(api_key=api_key)
        # Utilisation de gemini-1.5-flash-latest pour la stabilité
        return genai.GenerativeModel("gemini-1.5-flash-latest")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de Google Generative AI : {str(e)}")
        raise

def generate_security_summary_text(log_text: str, top_patterns: list = None) -> str:
    patterns_str = ""
    if top_patterns:
        patterns_str = "\nTop 10 Recurring Patterns (Message, Occurrences):\n" + \
                       "\n".join([f"- {p[0]}: {p[1]}" for p in top_patterns])

    prompt = (
        "Analyze security-relevant logs and return ONLY valid JSON.\n"
        "STRICT JSON FORMAT REQUIRED. No markdown, no extra text.\n\n"
        "Required JSON keys:\n"
        "  \"ai_status\": \"Critique|Attention|Normal\",\n"
        "  \"ai_score\": <int 0-100>,\n"
        "  \"ai_menaces\": <int>,\n"
        "  \"severity_counts\": {\"Critique\": X, \"Moyen\": Y, \"Faible\": Z},\n"
        "  \"activity_trend\": [f1, f2, f3, ...], (list of frequencies over time)\n"
        "  \"audit_points\": [\"Point 1\", \"Point 2\", ...], (key audit findings)\n"
        "  \"ai_insights\": \"Short summary paragraph\",\n"
        "  \"security_level\": \"LOW|MEDIUM|HIGH|CRITICAL\",\n"
        "  \"corrective_actions\": [\"Action 1\", \"Action 2\"],\n"
        "  \"prevention_steps\": [\"Prevention 1\", \"Prevention 2\"]\n\n"
        "Rules:\n"
        "- If 'Failed password' is found, reduce score by 20 points per attempt.\n"
        "- ai_status mapping: score > 80 -> Normal, 50-80 -> Attention, < 50 -> Critique.\n"
        f"{patterns_str}\n"
        f"LOGS:\n{log_text}\n"
    )

    cfg = _resolve_ai_config()

    # Tentative avec Cursor AI
    cursor_key = cfg["cursor_key"]
    if cursor_key:
        try:
            configured_base = cfg.get("cursor_base", "https://api.cursor.sh/v1")
            preferred = cfg.get("cursor_model", "gpt-4o-mini")
            model_candidates = [preferred, "gpt-4o-mini"]
            base_candidates = [configured_base, "https://api.cursor.sh/v1"]

            for base_url in base_candidates:
                for candidate in model_candidates:
                    if not candidate: continue
                    try:
                        return _openai_style_completion(
                            api_key=cursor_key,
                            base_url=base_url,
                            model_name=candidate,
                            prompt=prompt,
                        )
                    except Exception as model_err:
                        logger.warning(f"[Cursor AI Warning] {str(model_err)}")
        except Exception as e:
            logger.error(f"[Cursor AI Error] {str(e)}")

    # Fallback OpenAI
    openai_key = cfg["openai_key"]
    if openai_key:
        try:
            openai_base = cfg.get("openai_base")
            openai_model = cfg.get("openai_model", "gpt-4o-mini")
            return _openai_style_completion(
                api_key=openai_key,
                base_url=openai_base,
                model_name=openai_model,
                prompt=prompt,
            )
        except Exception as e:
            logger.error(f"[OpenAI Fallback Error] {str(e)}")

    # Fallback Gemini (Principal)
    try:
        from google.api_core import exceptions as google_exceptions
        model = get_gemini_model()
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except google_exceptions.NotFound:
        logger.error("Modèle Gemini non trouvé (404). Vérifiez le nom du modèle.")
        raise
    except google_exceptions.PermissionDenied:
        logger.error("Accès refusé à l'API Gemini. Vérifiez votre API Key.")
        raise
    except Exception as e:
        logger.error(f"[Gemini Error] {str(e)}")
        raise

def generate_security_summary(*, model, log_text: str, top_patterns: list = None):
    try:
        text = generate_security_summary_text(log_text, top_patterns)
        print("DEBUG - IA Response:", text)
    except Exception as e:
        print(f"Error calling AI: {str(e)}")
        res = _heuristic_security_summary(log_text)
        res.update({
            "ai_status": res.get("status", "Attention"),
            "ai_score": res.get("score", 70),
            "ai_menaces": res.get("menaces", 0),
            "corrective_actions": [],
            "prevention_steps": []
        })
        return res

    parsed = {}
    try:
        parsed = json.loads(text)
    except Exception:
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
        except Exception as re_err:
            print(f"Regex Parsing Error: {str(re_err)}")

    ai_insights = str(parsed.get("ai_insights", "")).strip() or text[:600]
    security_level = str(parsed.get("security_level", "MEDIUM")).strip().upper()
    if security_level not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        security_level = "MEDIUM"
    
    return {
        "ai_insights": ai_insights,
        "security_level": security_level,
        "score": int(parsed.get("ai_score", parsed.get("score", 70))),
        "status": str(parsed.get("ai_status", parsed.get("status", "Attention"))),
        "menaces": int(parsed.get("ai_menaces", parsed.get("menaces", 0))),
        "severity_counts": parsed.get("severity_counts", {"Critique": 0, "Moyen": 0, "Faible": 0}),
        "activity_trend": parsed.get("activity_trend", []),
        "audit_points": parsed.get("audit_points", []),
        "corrective_actions": parsed.get("corrective_actions", []),
        "prevention_steps": parsed.get("prevention_steps", [])
    }

def parse_log_line(line: str) -> dict:
    """Parse une ligne de log brute en dictionnaire (Timestamp, Message, Source)."""
    if not isinstance(line, str): return line
    
    # Format ISO: 2026-04-08T14:56:03.123Z host service[pid]: message
    iso_match = re.match(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})?)\s+(?P<host>\S+)\s+(?P<src>[^:]+):\s*(?P<msg>.*)$", line)
    if iso_match:
        return {
            "timestamp": iso_match.group("ts"),
            "message": iso_match.group("msg"),
            "source": iso_match.group("src")
        }
    
    # Format Syslog classique: Apr  8 14:56:03 host service[pid]: message
    syslog_match = re.match(r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<src>[^:]+):\s*(?P<msg>.*)$", line)
    if syslog_match:
        return {
            "timestamp": syslog_match.group("ts"),
            "message": syslog_match.group("msg"),
            "source": syslog_match.group("src")
        }
    
    # Par défaut si on ne reconnaît pas le format
    return {
        "timestamp": "N/A",
        "message": line,
        "source": "SOC"
    }

def clean_text_for_pdf(text: str) -> str:
    """Nettoie le texte pour éviter les erreurs d'encodage FPDF (Latin-1)."""
    if not text: return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

class SOC_Report(FPDF):
    def __init__(self, qr_path=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.qr_path = qr_path
        # Définition des marges globales
        self.set_margins(10, 30, 10) # Gauche, Haut, Droite
        self.set_auto_page_break(auto=True, margin=25) # Marge basse pour le footer

    def header(self):
        # Chemins absolus vers les logos pour compatibilité Docker et local
        # On cherche d'abord dans le dossier backend/assets/img/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Chemin privilégié (backend/assets/img/)
        logo_shield_path = os.path.join(current_dir, "assets", "img", "logo.png")
        logo_awb_path = os.path.join(current_dir, "assets", "img", "logo-awb.png")

        # Fallback pour le développement local si les fichiers ne sont pas dans backend
        if not os.path.exists(logo_shield_path):
            base_dir = os.path.dirname(current_dir)
            logo_shield_path = os.path.join(base_dir, "frontend", "src", "assets", "img", "logo.png")
            
        if not os.path.exists(logo_awb_path):
            base_dir = os.path.dirname(current_dir)
            logo_awb_path = os.path.join(base_dir, "frontend", "src", "assets", "img", "logo-awb.png")

        # Sauvegarder l'état graphique et insérer les logos
        try:
            # Logo Tactix à gauche
            if os.path.exists(logo_shield_path):
                self.image(logo_shield_path, x=10, y=8, h=12)
            else:
                logger.warning(f"Logo Shield manquant au chemin : {logo_shield_path}")
            
            # Logo AWB à droite
            if os.path.exists(logo_awb_path):
                self.image(logo_awb_path, x=175, y=8, h=10)
            else:
                logger.warning(f"Logo AWB manquant au chemin : {logo_awb_path}")
        except Exception as e:
            logger.error(f"Erreur insertion logos PDF: {str(e)}")

        # Petit QR Code de Sécurité (15x15mm) - Authentification discrète
        # Positionné juste en dessous du logo AWB à droite
        if self.qr_path and os.path.exists(self.qr_path):
            try:
                self.image(self.qr_path, x=185, y=18, w=15)
            except Exception as e:
                logger.error(f"Erreur insertion petit QR PDF: {e}")

        # Ligne de séparation sous le header
        self.set_draw_color(221, 221, 221)
        self.set_line_width(0.2)
        self.line(10, 28, 200, 28)
        
        # On remet le curseur Y après le header pour ne pas empiéter sur le contenu
        self.set_y(32)

    def footer(self):
        # Positionnement à 15mm du bas
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        
        # Ligne au-dessus du footer
        self.set_draw_color(240, 240, 240)
        self.line(10, self.get_y(), 200, self.get_y())

        # Numéro de page à gauche
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="L")
        
        # Note d'authentification à droite
        self.set_x(-120)
        self.cell(110, 10, clean_text_for_pdf("Document Sécurisé par LogAnalyzer SOC - Certifié Conforme"), align="R")

    def draw_log_table(self, title, logs, header_color):
        """Dessine un tableau de logs avec en-tête coloré."""
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(header_color[0], header_color[1], header_color[2])
        self.cell(190, 10, clean_text_for_pdf(title), ln=True)
        
        # En-tête du tableau
        col_widths = [35, 125, 30] # Timestamp, Message, Source
        headers = ["Horodatage", "Message d'Analyse", "Source"]
        
        def print_header():
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(header_color[0], header_color[1], header_color[2])
            self.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                self.cell(col_widths[i], 8, clean_text_for_pdf(h), border=1, fill=True, align='C')
            self.ln()

        print_header()
        
        # Contenu du tableau
        self.set_font("Helvetica", "", 8)
        self.set_text_color(55, 65, 81)
        
        if not logs:
            self.cell(sum(col_widths), 10, clean_text_for_pdf("Aucun événement détecté dans cette catégorie."), border=1, align='C', ln=True)
        else:
            for log in logs:
                # Conversion si c'est une chaîne brute
                if isinstance(log, str):
                    log_data = parse_log_line(log)
                else:
                    log_data = log

                ts = log_data.get('timestamp', 'N/A')
                msg = log_data.get('message', 'N/A')
                src = log_data.get('source', 'SOC')
                
                # Calcul de la hauteur nécessaire pour le message multi-lignes
                line_height = 5
                # On utilise multi_cell sur une copie temporaire pour calculer la hauteur
                # NB: multi_cell dans fpdf2/fpdf peut calculer la hauteur nécessaire
                # On estime grossièrement ou on utilise une approche prudente
                msg_width = col_widths[1] - 2
                nb_lines = self.get_string_width(msg) / msg_width
                nb_lines = max(1, int(nb_lines) + 1)
                # Plus précis: compter les sauts de ligne explicites
                nb_lines += msg.count('\n')
                
                cell_height = nb_lines * line_height
                if cell_height < 8: cell_height = 8

                # Vérification de l'espace restant avant d'écrire la ligne
                if self.get_y() + cell_height > 265:
                    self.add_page()
                    print_header()
                    self.set_font("Helvetica", "", 8)
                    self.set_text_color(55, 65, 81)

                curr_x = self.get_x()
                curr_y = self.get_y()
                
                # Cellule Timestamp
                self.cell(col_widths[0], cell_height, clean_text_for_pdf(ts), border=1)
                
                # Cellule Message (Multi-ligne)
                # On sauvegarde le Y avant multi_cell
                self.multi_cell(col_widths[1], line_height, clean_text_for_pdf(msg), border=1)
                
                # Re-positionnement pour la cellule Source
                # multi_cell déplace le curseur en bas, on doit revenir à curr_y pour la colonne suivante
                final_y = self.get_y()
                self.set_xy(curr_x + col_widths[0] + col_widths[1], curr_y)
                self.cell(col_widths[2], cell_height, clean_text_for_pdf(src), border=1, ln=True)
                
                # On s'assure d'être au max des deux hauteurs pour la ligne suivante
                if self.get_y() < final_y:
                    self.set_y(final_y)

        self.ln(5)

def generate_user_qr(user) -> bytes | None:
    """Génère les octets (PNG) d'un QR Code pour l'utilisateur Expert SOC."""
    try:
        # Robustesse : Vérification de l'utilisateur
        if not user or not hasattr(user, 'first_name') or not hasattr(user, 'last_name') or not hasattr(user, 'email'):
            logger.error("Tentative de génération de QR pour un utilisateur invalide ou None")
            return None

        # Données sécurisées : Nom, Prénom, Email uniquement
        qr_data = f"Expert SOC: {user.first_name} {user.last_name}\nEmail: {user.email}"
        
        # Configuration QR Code compatible Pillow 10+
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Génération de l'image (nécessite Pillow)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Récupération des octets via un buffer mémoire
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return buffered.getvalue()
    except Exception as e:
        logger.error(f"Erreur critique lors de la génération des octets du QR Code : {str(e)}")
        return None

def generate_user_qr_base64(user) -> str | None:
    """Génère un QR Code en Base64 pour l'utilisateur Expert SOC."""
    qr_bytes = generate_user_qr(user)
    if qr_bytes:
        qr_base64 = base64.b64encode(qr_bytes).decode('utf-8')
        return f"data:image/png;base64,{qr_base64}"
    return None

def generate_pdf_report_bytes(analysis, logs_list=None):
    """
    Génère un rapport PDF professionnel à partir d'une analyse.
    logs_list peut être passé optionnellement pour injecter des logs spécifiques.
    """
    qr_temp_file = None
    try:
        from models import User
        user = User.query.get(analysis.user_id)
        
        # Récupération sécurisée du QR Code de l'analyste
        qr_bytes = None
        if user:
            try:
                # Vérification de l'existence de la fonction dans le scope local/global
                if 'generate_user_qr' in globals():
                    qr_bytes = generate_user_qr(user)
                else:
                    logger.error("La fonction 'generate_user_qr' n'est pas définie dans le scope.")
            except Exception as qr_err:
                logger.error(f"Erreur lors de la génération du QR Code : {qr_err}")
        
        qr_path = None
        if qr_bytes:
            try:
                qr_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                qr_temp_file.write(qr_bytes)
                qr_temp_file.close()
                qr_path = qr_temp_file.name
            except Exception as tmp_err:
                logger.error(f"Erreur lors de la création du fichier QR temporaire : {tmp_err}")

        pdf = SOC_Report(qr_path=qr_path)
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # --- Section 1: Titre & Résumé ---
        # Positionnement initial sécurisé après le header
        pdf.set_y(35)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(190, 12, clean_text_for_pdf("Rapport d'Analyse des Systèmes et Flux Web"), align="C", ln=True)
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(75, 85, 99)
        pdf.cell(190, 10, clean_text_for_pdf("Compte-rendu d'Analyse Technique Officiel"), align="C", ln=True)
        pdf.ln(10)
        
        pdf.set_fill_color(249, 250, 251)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(190, 10, clean_text_for_pdf("1. Métadonnées de l'Analyse"), fill=True, ln=True)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(55, 65, 81)
        
        stats = analysis.stats or {}
        
        # Si logs_list est fourni, on recalcule les segments et stats pour le rapport
        segments = analysis.segments or {}
        if logs_list:
            segments = {'error': [], 'warning': [], 'info': []}
            for log in logs_list:
                level = str(log.get('level', 'info')).lower()
                if 'error' in level or 'crit' in level:
                    segments['error'].append(log)
                elif 'warn' in level:
                    segments['warning'].append(log)
                else:
                    segments['info'].append(log)
            
            # Mise à jour des stats pour l'affichage
            stats['total'] = len(logs_list)
            stats['errors'] = len(segments['error'])
            stats['warnings'] = len(segments['warning'])
            stats['info'] = len(segments['info'])

        analysis_date = analysis.created_at
        date_str = analysis_date.strftime('%d/%m/%Y %H:%M') if isinstance(analysis_date, datetime) else str(analysis_date)

        rows = [
            ("ID du Rapport", f"#{analysis.id}"),
            ("Analyste SOC", f"{user.first_name} {user.last_name}" if user else "Système"),
            ("Date de l'Analyse", date_str),
            ("Source des Logs", analysis.server_ip if analysis.source_type == 'ssh' else "Hôte Local"),
            ("Type d'Audit", analysis.source_type.upper()),
            ("Total lignes analysées", str(stats.get('total', 0)))
        ]
        
        for label, value in rows:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(50, 8, clean_text_for_pdf(label + " :"), border=0)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(140, 8, clean_text_for_pdf(value), border=0, ln=True)

        pdf.ln(10)

        # --- Section 2: Catégorisation des Logs ---
        # S'assurer qu'il y a de l'espace avant la section 2
        if pdf.get_y() > 240: pdf.add_page()
        
        pdf.set_fill_color(249, 250, 251)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(190, 10, clean_text_for_pdf("2. Détails des Événements par Catégorie"), fill=True, ln=True)
        pdf.ln(5)

        # Tableau des ERREURS (Rouge)
        pdf.draw_log_table("ERREURS DÉTECTÉES (CRITIQUE)", segments.get('error', segments.get('ERROR', [])), [220, 38, 38])
        
        # Tableau des AVERTISSEMENTS (Orange)
        pdf.set_y(pdf.get_y() + 5) # Espace avant le prochain tableau
        pdf.draw_log_table("AVERTISSEMENTS (ATTENTION)", segments.get('warning', segments.get('WARNING', [])), [217, 119, 6])
        
        # Tableau des INFOS (Bleu/Gris)
        pdf.set_y(pdf.get_y() + 5) # Espace avant le prochain tableau
        pdf.draw_log_table("FLUX D'INFORMATION (NORMAL)", segments.get('info', segments.get('INFO', [])), [59, 130, 246])

        # --- Section 3: IA Insights ---
        if analysis.meta and analysis.meta.get('ai_insights'):
            pdf.add_page() # Toujours sur une nouvelle page pour plus de clarté
            pdf.set_y(35)
            pdf.set_fill_color(249, 250, 251)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(17, 24, 39)
            pdf.cell(190, 10, clean_text_for_pdf("3. Analyse Prédictive & Insights IA"), fill=True, ln=True)
            pdf.ln(5)
            
            # Encadré pour la synthèse
            pdf.set_fill_color(243, 244, 246)
            pdf.set_draw_color(209, 213, 219)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(31, 41, 55)
            pdf.cell(190, 8, clean_text_for_pdf("Synthèse de Sécurité :"), border="LTR", fill=True, ln=True)
            
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(55, 65, 81)
            # Multi-cell avec bordures latérales et fond
            pdf.multi_cell(190, 6, clean_text_for_pdf(analysis.meta.get('ai_insights')), border="LR", fill=True)
            # Bordure basse
            pdf.cell(190, 2, "", border="T", ln=True)
            pdf.ln(15)

        # Signature Finale & Grand QR Code
        # Vérification de l'espace restant pour la signature
        if pdf.get_y() > 220:
            pdf.add_page()
            pdf.set_y(35)

        pdf.set_y(pdf.get_y() + 10) # Espace de sécurité
        curr_y = pdf.get_y()
        
        # Grand QR Code de Signature (40x40mm)
        if pdf.qr_path and os.path.exists(pdf.qr_path):
            try:
                # Isolé à droite
                pdf.image(pdf.qr_path, x=155, y=curr_y, w=40)
            except Exception as e:
                logger.error(f"Erreur insertion grand QR: {e}")

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(190, 8, clean_text_for_pdf("Expertise Validée numériquement par le SOC :"), ln=True, align="L")
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(190, 6, clean_text_for_pdf(f"{user.first_name} {user.last_name}" if user else "Analyste Certifié"), align="L", ln=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(140, 5, clean_text_for_pdf("Ce document est une preuve technique d'audit LogAnalyzer SOC. Scannez le QR code pour vérification."), align="L", ln=True)


        pdf_content = pdf.output(dest='S')
        if isinstance(pdf_content, str):
            return pdf_content.encode('latin-1')
        return bytes(pdf_content)

    except Exception as e:
        # Log détaillé avec traceback pour identifier la ligne exacte
        tb = traceback.format_exc()
        logger.error(f"Erreur critique lors de la génération du PDF : {str(e)}\nTraceback :\n{tb}")
        return None
    finally:
        if qr_temp_file and os.path.exists(qr_temp_file.name):
            try:
                os.unlink(qr_temp_file.name)
            except Exception as cleanup_err:
                logger.error(f"Erreur nettoyage fichier temporaire PDF: {cleanup_err}")

def send_user_notification(user, subject: str, html_content: str):
    """Envoie une notification par email à un utilisateur spécifique."""
    if not user or not user.email:
        return
        
    # Configuration SMTP privilégiant la base de données de l'utilisateur
    smtp_config = {
        'server': user.smtp_server or os.getenv('SMTP_SERVER', 'sandbox.smtp.mailtrap.io'),
        'port': user.smtp_port or int(os.getenv('SMTP_PORT', 2525)),
        'user': os.getenv('SMTP_USER', 'b1d332e315f09f'),
        'password': os.getenv('SMTP_PASSWORD', '78b1eb63687425'),
        'display_user': user.email_sender or "abdelfattahbouabid@pwd.pfe.ma",
        'use_tls': os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
    }
    
    if not smtp_config['user'] or not smtp_config['password']:
        logger.warning(f"Configuration SMTP incomplète pour l'utilisateur {user.username}. Notification email annulée.")
        return

    # Utilise la fonction asynchrone existante pour ne pas bloquer le thread principal
    from flask import current_app
    send_report_email_async(
        current_app._get_current_object(),
        smtp_config,
        user.email,
        subject,
        html_content,
        b"", # Pas de PDF pour une simple notification
        "notification.txt"
    )

def save_analysis(*, db, user_id: int, source_type: str, source_path: str, server_ip: str | None, stats: dict, segments: dict, meta: dict, log_content: str = ""):
    from models import Analysis
    analysis = Analysis(
        user_id=user_id,
        source_type=source_type,
        source_path=source_path,
        server_ip=server_ip,
        stats=stats,
        segments=segments,
        meta=meta,
        ai_score=meta.get("score", 70),
        ai_status=meta.get("status", "Attention"),
        ai_menaces=meta.get("menaces", 0)
    )
    db.session.add(analysis)
    db.session.commit()
    return analysis
