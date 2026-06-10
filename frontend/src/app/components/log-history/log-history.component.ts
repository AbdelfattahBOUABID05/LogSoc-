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
  filterType = signal<string>('all');
  filterStatus = signal<string>('all');

  currentPage: number = 1;
  itemsPerPage: number = 5;

  /**
   * Propriété calculée (Computed Signal) qui filtre automatiquement la liste
   * des analyses en fonction de la recherche textuelle et de la date.
   */
  filteredAnalyses = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    const date = this.filterDate();
    const type = this.filterType();
    const status = this.filterStatus();
    const data = this.allAnalyses();

    return data.filter(a => {
      // Filtrage par date de création
      if (date && a.created_at && !a.created_at.startsWith(date)) {
        return false;
      }

      // Filtrage par Type d'Analyse
      if (type !== 'all') {
        if (type === 'ssh' && a.source_type !== 'ssh') return false;
        if (type === 'locale' && a.source_type !== 'upload') return false;
        if (type === 'jobs' && a.source_type !== 'scheduled') return false;
      }

      // Filtrage par Statut IA
      if (status !== 'all') {
        const s = (a.ai_status || '').toLowerCase();
        if (status === 'menace' && !s.includes('menace')) return false;
        if (status === 'attention' && !s.includes('attention')) return false;
        if (status === 'normal' && !s.includes('normal')) return false;
      }

      // Filtrage multi-critères textuel
      if (!query) return true;

      const targetMatch = (a.job_name || a.server_ip || 'Machine Locale').toLowerCase().includes(query);
      const fileMatch = (a.file_path || '').toLowerCase().includes(query);
      const statusMatch = (a.ai_status || '').toLowerCase().includes(query);
      const typeMatch = (a.source_type || '').toLowerCase().includes(query);

      return targetMatch || fileMatch || statusMatch || typeMatch;
    });
  });

  /**
   * Getter pour la pagination
   */
  get paginatedLogs(): Analysis[] {
    const startIndex = (this.currentPage - 1) * this.itemsPerPage;
    return this.filteredAnalyses().slice(startIndex, startIndex + this.itemsPerPage);
  }

  get totalPages(): number {
    return Math.ceil(this.filteredAnalyses().length / this.itemsPerPage);
  }

  nextPage(): void {
    if (this.currentPage < this.totalPages) {
      this.currentPage++;
    }
  }

  prevPage(): void {
    if (this.currentPage > 1) {
      this.currentPage--;
    }
  }

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
    this.currentPage = 1;
  }

  /** Met à jour le signal de filtrage par date */
  onDateChange(value: string): void {
    this.filterDate.set(value);
    this.currentPage = 1;
  }

  /** Réinitialise le filtre de date */
  clearDateFilter(): void {
    this.filterDate.set('');
    this.currentPage = 1;
  }

  /** Met à jour le filtre par Type d'Analyse */
  onTypeChange(value: string): void {
    this.filterType.set(value);
    this.currentPage = 1;
  }

  /** Met à jour le filtre par Statut IA */
  onStatusChange(value: string): void {
    this.filterStatus.set(value);
    this.currentPage = 1;
  }

  /** Réinitialise tous les filtres de recherche */
  resetFilters(): void {
    this.searchQuery.set('');
    this.filterDate.set('');
    this.filterType.set('all');
    this.filterStatus.set('all');
    this.currentPage = 1;
  }getTargetDisplay(analysis: Analysis): string {
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
