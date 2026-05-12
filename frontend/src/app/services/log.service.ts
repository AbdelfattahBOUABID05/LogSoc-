import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, Subject, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { CryptoService } from './crypto.service';

// Phase 1 : Nouvelles interfaces SOC
export interface SocStatEntry {
  timestamp: string;
  critical: number;
  warning: number;
  info: number;
}

export interface KBSolution {
  id?: number;
  problem_title: string;
  log_pattern: string;
  solution_content: string;
  author_name?: string;
  created_at?: string;
}

export interface SocStatsResponse {
  ssh_data: {
    labels: string[];
    series: any[];
  };
  local_data: {
    labels: string[];
    series: any[];
  };
  jobs_data: {
    labels: string[];
    series: any[];
  };
}

// Interfaces existantes pour la compatibilité
export interface Analysis {
  id: number;
  created_at: string;
  source_type: string;
  source_path: string;
  server_ip: string;
  stats: {
    errors: number;
    warnings: number;
    info: number;
    total: number;
  };
  segments: any;
  meta: any;
  severity_counts?: {
    high: number;
    medium: number;
    low: number;
  };
  ai_score: number;
  ai_status: string;
  ai_menaces: number;
  file_path?: string;
}

export interface DashboardSummary {
  total_audits: number;
  active_servers: number;
  critical_threats: number;
  system_health: number;
}

export interface StatsDetail {
  labels: string[];
  critique: number[];
  avertissement: number[];
  info: number[];
  total_logs: number;
}

export interface StatsResponse {
  status: string;
  labels: string[];
  critique: number[];
  avertissement: number[];
  info: number[];
  sshStats?: StatsDetail;
  localStats?: StatsDetail;
  jobsStats?: StatsDetail;
  total_logs: number;
  total_errors: number;
  total_warnings: number;
  summary: DashboardSummary;
  analysis_data?: Analysis | null;
  meta?: any;
  severity_counts?: {
    high: number;
    medium: number;
    low: number;
  };
}

export interface DashboardResponse {
  status: string;
  analysis_data: Analysis | null;
  meta?: any;
  severity_counts?: {
    high: number;
    medium: number;
    low: number;
  };
  summary: DashboardSummary;
  recent_activities: any[];
}

export interface AnalysesResponse {
  status: string;
  count: number;
  analyses: Analysis[];
}

export interface SettingsPayload {
  emailNotifications: boolean;
  notificationEmail: string;
  smtpServer: string;
  smtpPort: number;
  smtpUser: string;
  smtpPassword?: string;
}

export interface Job {
  id: number;
  user_id: number;
  username: string;
  target_ip: string;
  log_path: string;
  frequency: string;
  status: string;
  created_at: string;
}

export interface JobApprovalResponse {
  status: string;
  message: string;
}

export interface Notification {
  id: number;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  is_read: boolean;
  created_at: string;
  link?: string;
}

export interface NotificationsResponse {
  status: string;
  notifications: Notification[];
}

@Injectable({
  providedIn: 'root'
})
export class LogService {
  /**
   * Point d'entrée de l'API Flask.
   * Récupéré depuis le fichier d'environnement.
   */
  private apiUrl = environment.apiUrl;
  private STORAGE_KEY = 'recent_ssh_connections';

  // Sujet permettant de notifier les composants qu'une mise à jour des données est nécessaire
  private refreshDashboardSource = new Subject<void>();
  refreshDashboard$ = this.refreshDashboardSource.asObservable();

  constructor(private http: HttpClient, private crypto: CryptoService) {}

  /**
   * Déclenche un rafraîchissement global du tableau de bord (Gauges + Graphiques)
   */
  triggerRefresh(): void {
    this.refreshDashboardSource.next();
  }

  /**
   * Récupère les statistiques agrégées pour le graphique multi-séries.
   * @param timeRange Période choisie : H (Heure), D (Jour), M (Mois), Y (Année)
   */
  getStats(timeRange: string = 'D'): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/stats?time_range=${timeRange}`);
  }

  /**
   * Lance une analyse de logs via une connexion SSH distante
   */
  analyzeSSH(payload: any): Observable<{ status: string; message: string; analysis_id?: number }> {
    return this.http.post<{ status: string; message: string; analysis_id?: number }>(
      `${this.apiUrl}/ssh/analyze`,
      payload
    ).pipe(
      tap(() => this.triggerRefresh())
    );
  }

  /**
   * Téléverse et analyse un fichier de logs local
   */
  uploadLogFile(file: File, numLines: number | null): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    if (numLines !== null) {
      formData.append('numLines', numLines.toString());
    }
    return this.http.post(`${this.apiUrl}/analyze-local`, formData).pipe(
      tap(() => this.triggerRefresh())
    );
  }

  /**
   * Récupère les paramètres de configuration de l'utilisateur (Notifications, SMTP)
   */
  getSettings(): Observable<{ status: string; settings: SettingsPayload }> {
    return this.http.get<{ status: string; settings: SettingsPayload }>(`${this.apiUrl}/settings`);
  }

  /**
   * Enregistre les nouveaux paramètres utilisateur
   */
  saveSettings(settings: SettingsPayload): Observable<{ status: string; message: string }> {
    return this.http.post<{ status: string; message: string }>(
      `${this.apiUrl}/settings`,
      settings
    );
  }

  // ========== MÉTHODES POUR LES JOBS (TÂCHES PLANIFIÉES) ==========

  /** Récupère la liste des jobs de l'utilisateur */
  getJobs(): Observable<{ status: string; jobs: any[] }> {
    return this.http.get<{ status: string; jobs: any[] }>(`${this.apiUrl}/jobs`);
  }

  /** Crée une nouvelle tâche d'analyse automatisée */
  createJob(jobData: any): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/jobs`, jobData).pipe(
      tap(() => this.triggerRefresh())
    );
  }

  /** Supprime une tâche planifiée */
  deleteJob(id: number): Observable<{ status: string; message: string }> {
    return this.http.delete<{ status: string; message: string }>(`${this.apiUrl}/jobs/${id}`).pipe(
      tap(() => this.triggerRefresh())
    );
  }

  /** Active ou désactive un job */
  toggleJob(id: number): Observable<{ status: string; new_status: string; message: string }> {
    return this.http.post<{ status: string; new_status: string; message: string }>(`${this.apiUrl}/jobs/${id}/toggle`, {}).pipe(
      tap(() => this.triggerRefresh())
    );
  }

  // ========== MÉTHODES POUR LA BASE DE CONNAISSANCES (KB) ==========

  /** Récupère toutes les solutions de la base de connaissances */
  getKBSolutions(): Observable<{ status: string; solutions: KBSolution[] }> {
    return this.http.get<{ status: string; solutions: KBSolution[] }>(`${this.apiUrl}/kb/solutions`);
  }

  /** Recherche un matching global dans la KB pour une liste de logs */
  matchKBPattern(logs: string[]): Observable<{ status: string; solution: KBSolution | null }> {
    return this.http.post<{ status: string; solution: KBSolution | null }>(`${this.apiUrl}/kb/match-pattern`, { logs });
  }

  getKBContributionsStats(): Observable<{ status: string; stats: { author: string; count: number }[] }> {
    return this.http.get<{ status: string; stats: { author: string; count: number }[] }>(`${this.apiUrl}/stats/kb-contributions`);
  }

  /** Ajoute une nouvelle solution à la base de connaissances */
  createKBSolution(solution: KBSolution): Observable<{ status: string; message: string; solution: KBSolution }> {
    return this.http.post<{ status: string; message: string; solution: KBSolution }>(`${this.apiUrl}/kb/solutions`, solution);
  }

  /** Supprime une solution de la base de connaissances */
  deleteKBSolution(id: number): Observable<{ status: string; message: string }> {
    return this.http.delete<{ status: string; message: string }>(`${this.apiUrl}/kb/solutions/${id}`);
  }

  // ========== ANALYSES ET HISTORIQUE ==========

  /** Récupère le résumé complet du dashboard (totaux, santé, alertes) */
  getDashboard(): Observable<DashboardResponse> {
    return this.http.get<DashboardResponse>(`${this.apiUrl}/dashboard`);
  }

  /** Récupère l'historique de toutes les analyses */
  getAnalyses(): Observable<AnalysesResponse> {
    return this.http.get<AnalysesResponse>(`${this.apiUrl}/analyses`);
  }

  /** Récupère les détails d'une analyse via son identifiant */
  getAnalysis(id: number): Observable<{ status: string; analysis: Analysis }> {
    return this.http.get<{ status: string; analysis: Analysis }>(`${this.apiUrl}/analyses/${id}`);
  }

  /** Supprime définitivement une analyse de l'historique */
  deleteAnalysis(id: number): Observable<{ status: string; message: string }> {
    return this.http.delete<{ status: string; message: string }>(`${this.apiUrl}/analyses/${id}`);
  }

  /** Génère et récupère le flux binaire du rapport PDF */
  downloadAnalysisPdf(id: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/analyses/${id}/pdf`, {
      responseType: 'blob'
    });
  }

  // ========== SYSTÈME DE NOTIFICATIONS ==========

  /** Récupère les notifications de l'utilisateur */
  getNotifications(): Observable<NotificationsResponse> {
    return this.http.get<NotificationsResponse>(`${this.apiUrl}/notifications`);
  }

  /** Marque une notification comme lue */
  markNotificationAsRead(notifId: number): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.apiUrl}/notifications/${notifId}/read`, {});
  }

  // ========== ADMINISTRATION SOC ==========

  /** (Admin uniquement) Récupère les jobs en attente de validation */
  getAdminJobs(): Observable<{ status: string; jobs: Job[] }> {
    return this.http.get<{ status: string; jobs: Job[] }>(`${this.apiUrl}/admin/jobs`);
  }

  /** (Admin uniquement) Approuve ou refuse un job planifié */
  approveAdminJob(jobId: number, action: 'approve' | 'refuse', reason?: string): Observable<JobApprovalResponse> {
    return this.http.post<JobApprovalResponse>(`${this.apiUrl}/admin/jobs/${jobId}/approve`, { action, reason });
  }

  // ========== GESTION DU CACHE ET CONNEXIONS RÉCENTES ==========

  /** Enregistre localement les informations de connexion SSH pour l'auto-complétion */
  saveConnection(conn: any): void {
    let currentHistory = this.getRecentConnections();
    currentHistory = currentHistory.filter(h => h.host !== conn.host);
    currentHistory.unshift(conn);
    const updatedHistory = currentHistory.slice(0, 3);
    const encryptedData = this.crypto.encryptObject(updatedHistory);
    localStorage.setItem(this.STORAGE_KEY, encryptedData);
  }

  /** Récupère l'historique des connexions SSH depuis le stockage local */
  getRecentConnections(): any[] {
    const encryptedData = localStorage.getItem(this.STORAGE_KEY);
    if (!encryptedData) return [];
    try {
      const decrypted = this.crypto.decryptObject(encryptedData);
      return Array.isArray(decrypted) ? decrypted : [];
    } catch (e) {
      console.error('Erreur SSH History:', e);
      return [];
    }
  }

  /** Envoie un rapport d'audit par email */
  sendReportEmail(payload: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/email/send-report`, payload);
  }

  // ========== AUDIT LOGS (ADMIN) ==========

  /** Récupère les derniers logs d'audit (Admin uniquement) */
  getAuditLogs(): Observable<{ status: string; audit_logs: any[] }> {
    return this.http.get<{ status: string; audit_logs: any[] }>(`${this.apiUrl}/admin/audit-logs`);
  }

  /** Enregistre manuellement une action d'audit depuis le frontend */
  createAuditLog(action: string, details: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/admin/audit-logs`, { action, details });
  }
}
