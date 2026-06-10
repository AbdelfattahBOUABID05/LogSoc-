-- 1. INSERT SAMPLE ANALYSES (REPORTS)
-- Assumes User ID 1 exists. Adjust user_id if necessary.
INSERT INTO analyses (public_id, user_id, created_at, source_type, source_path, file_path, server_ip, stats, segments, meta, ai_score, ai_status, ai_menaces)
VALUES 
(gen_random_uuid(), 1, NOW() - INTERVAL '2 hours', 'ssh', '192.168.1.45', '/var/log/auth.log', '192.168.1.45', 
 '{"errors": 42, "warnings": 15, "info": 230, "total": 287}', 
 '{"ERROR": ["Failed password for root", "Connection closed by authenticating user"], "WARNING": ["Invalid user admin from 10.0.0.5"], "INFO": ["Accepted password for dev"]}',
 '{"status": "Menace Détectée", "score": 35, "menaces": 8}', 35, 'Menace Détectée', 8),

(gen_random_uuid(), 1, NOW() - INTERVAL '1 day', 'upload', 'access_log_june.log', 'uploads/1_access_log.log', NULL, 
 '{"errors": 12, "warnings": 45, "info": 1200, "total": 1257}', 
 '{"ERROR": ["404 Not Found /admin/config"], "WARNING": ["Slow response time detected"], "INFO": ["GET /index.html 200"]}',
 '{"status": "Attention", "score": 62, "menaces": 2}', 62, 'Attention', 2),

(gen_random_uuid(), 1, NOW() - INTERVAL '3 days', 'scheduled', 'Production-Server-01', '/var/log/syslog', '10.50.0.12', 
 '{"errors": 2, "warnings": 5, "info": 5400, "total": 5407}', 
 '{"ERROR": ["Disk space low"], "WARNING": ["Swap usage increasing"], "INFO": ["System update checked"]}',
 '{"status": "Normal", "score": 92, "menaces": 0}', 92, 'Normal', 0),

(gen_random_uuid(), 1, NOW() - INTERVAL '5 days', 'ssh', '172.16.254.1', '/var/log/nginx/error.log', '172.16.254.1', 
 '{"errors": 0, "warnings": 2, "info": 850, "total": 852}', 
 '{"ERROR": [], "WARNING": ["Upstream timed out"], "INFO": ["Worker process started"]}',
 '{"status": "Normal", "score": 98, "menaces": 0}', 98, 'Normal', 0);

-- 2. INSERT SAMPLE AUDIT LOGS (ACTIVITY TRAIL)
INSERT INTO audit_logs (username, action, details, timestamp)
VALUES 
('admin', 'LOGIN', 'Connexion réussie de l''utilisateur admin', NOW() - INTERVAL '2 hours 10 minutes'),
('admin', 'SSH_ANALYZE', 'Analyse lancée sur le serveur 192.168.1.45 (Cible: /var/log/auth.log)', NOW() - INTERVAL '2 hours'),
('admin', 'LOCAL_UPLOAD', 'Upload du fichier access_log_june.log pour analyse', NOW() - INTERVAL '1 day'),
('admin', 'KB_SOLUTION_CREATE', 'Nouvelle solution ajoutée : Correction Brute Force SSH', NOW() - INTERVAL '12 hours'),
('admin', 'SETTINGS_UPDATE', 'Mise à jour des paramètres de notification SMTP', NOW() - INTERVAL '4 days');

-- 3. INSERT SAMPLE KNOWLEDGE BASE ENTRIES (SOLUTIONS KB)
INSERT INTO solutions_kb (problem_title, log_pattern, solution_content, author_name, created_at)
VALUES 
('Brute Force SSH Détecté', 'Failed password for root', 'Implémenter Fail2Ban avec un bannissement de 24h pour plus de 5 tentatives échouées en 5 minutes.', 'SOC Expert', NOW() - INTERVAL '10 days'),
('Erreur de Timeout API', 'Curl error 28', 'Vérifier la configuration du proxy sortant et s''assurer que le port 443 est ouvert vers les endpoints externes.', 'Network Admin', NOW() - INTERVAL '15 days'),
('404 Scan de Répertoires', '/admin/config', 'Configurer des règles WAF pour bloquer les scans automatisés sur les chemins sensibles et désactiver le directory listing.', 'Security Analyst', NOW() - INTERVAL '20 days');