import { Component, OnInit, signal, computed, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { LogService, Analysis } from '../../services/log.service';
import { SidebarComponent } from '../sidebar/sidebar.component';

@Component({
  selector: 'app-log-history',
  standalone: true,
  imports: [CommonModule, RouterModule, SidebarComponent, FormsModule],
  templateUrl: './log-history.component.html',
  styleUrls: ['./log-history.component.css']
})
export class LogHistoryComponent implements OnInit {
  // Signaux Angular 17 pour une gestion d'état réactive et performante
  private allAnalyses = signal<Analysis[]>([]);
  currentJobPublicId: string | null = null;
  searchQuery = signal<string>('');
  filterDate = signal<string>('');

  /**
   * Propriété calculée (Computed Signal) qui filtre automatiquement la liste
   * des analyses en fonction de la recherche textuelle et de la date.
   */
  filteredAnalyses = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    const date = this.filterDate();
    const data = this.allAnalyses();

    return data.filter(a => {
      // Filtrage par date de création
      if (date && a.created_at && !a.created_at.startsWith(date)) {
        return false;
      }

      // Filtrage multi-critères (Serveur, Fichier, Statut, Type de source)
      if (!query) return true;

      const targetMatch = (a.job_name || a.server_ip || 'Machine Locale').toLowerCase().includes(query);
      const fileMatch = (a.file_path || '').toLowerCase().includes(query);
      const statusMatch = (a.ai_status || '').toLowerCase().includes(query);
      const typeMatch = (a.source_type || '').toLowerCase().includes(query);

      return targetMatch || fileMatch || statusMatch || typeMatch;
    });
  });

  constructor(
    private logService: LogService,
    private cdr: ChangeDetectorRef,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      this.currentJobPublicId = params['job_id'] || null;
      this.loadAnalyses(this.currentJobPublicId);
    });
  }

  /**
   * Appelle le backend pour récupérer toutes les analyses passées.
   * Les données sont ensuite formatées pour assurer la cohérence de l'affichage.
   */
  loadAnalyses(jobId?: string | null): void {
    this.logService.getAnalyses(jobId).subscribe({
      next: (data) => {
        if (data.status === 'success') {
          const mapped = (data.analyses || []).map((analysis) => ({
            ...analysis,
            stats: analysis.stats || { errors: 0, warnings: 0, info: 0, total: 0 },
            ai_status: analysis.ai_status || 'Sain',
            ai_score: analysis.ai_score ?? 0,
            ai_menaces: analysis.ai_menaces ?? 0
          }));
          this.allAnalyses.set(mapped);
          this.cdr.detectChanges();
        }
      },
      error: (err) => console.error('Erreur chargement historique:', err)
    });
  }

  /** Met à jour le signal de recherche textuelle */
  onSearchChange(value: string): void {
    this.searchQuery.set(value);
  }

  /** Met à jour le signal de filtrage par date */
  onDateChange(value: string): void {
    this.filterDate.set(value);
  }

  /** Réinitialise le filtre de date */
  clearDateFilter(): void {
    this.filterDate.set('');
  }

  /** Réinitialise tous les filtres de recherche */
  resetFilters(): void {
    this.searchQuery.set('');
    this.filterDate.set('');
  }

  getTargetDisplay(analysis: Analysis): string {
    return analysis.job_name || analysis.server_ip || 'Audit Local';
  }

  /** Formate la date ISO en format lisible français (JJ/MM/AAAA HH:mm) */
  formatDate(dateStr: string | null): string {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /** Retourne la classe CSS pour le badge de statut IA */
  getStatusClass(status: string | null): string {
    const base = 'px-3 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-widest border transition-all duration-300 ';
    if (!status) return base + 'bg-slate-500/20 text-slate-400 border-slate-500/20';
    
    const s = status.toLowerCase();
    if (s.includes('critique') || s.includes('error')) return base + 'bg-rose-500/20 text-rose-400 border-rose-500/20';
    if (s.includes('attention') || s.includes('moyen') || s.includes('warning')) return base + 'bg-amber-500/20 text-amber-400 border-amber-500/20';
    return base + 'bg-emerald-500/20 text-emerald-400 border-emerald-500/20';
  }

  /** Redirige vers la page de rapport détaillé de l'analyse via son UUID public */
  viewDetails(analysis: Analysis): void {
    window.location.href = `/report?id=${analysis.id}`;
  }

  /** Supprime une analyse après confirmation via son UUID public */
  deleteAnalysis(analysis: Analysis): void {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette analyse ? Cette action est irréversible.')) {
      this.logService.deleteAnalysis(analysis.id).subscribe({
        next: () => this.loadAnalyses(),
        error: (err) => console.error('Erreur suppression:', err)
      });
    }
  }
}
