import { Component, OnInit, signal, computed, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { LogService, Analysis } from '../../services/log.service';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-log-history',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, MatIconModule],
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
    private route: ActivatedRoute,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      this.currentJobPublicId = params['job_id'] || null;
      this.loadAnalyses(this.currentJobPublicId);
    });
  }

  /** Charge les analyses depuis le backend */
  loadAnalyses(jobId: string | null = null): void {
    this.logService.getAnalyses(jobId).subscribe({
      next: (data: any) => {
        if (data.status === 'success') {
          this.allAnalyses.set(data.analyses);
          this.currentPage = 1;
        }
      },
      error: (err: any) => {
        console.error('Error loading history:', err);
      }
    });
  }

  /** Réinitialise tous les filtres actifs */
  resetFilters(): void {
    this.searchQuery.set('');
    this.filterDate.set('');
    this.filterType.set('all');
    this.filterStatus.set('all');
    this.currentPage = 1;
  }

  onSearchChange(value: string): void {
    this.searchQuery.set(value);
    this.currentPage = 1;
  }

  onDateChange(value: string): void {
    this.filterDate.set(value);
    this.currentPage = 1;
  }

  onTypeChange(value: string): void {
    this.filterType.set(value);
    this.currentPage = 1;
  }

  onStatusChange(value: string): void {
    this.filterStatus.set(value);
    this.currentPage = 1;
  }

  clearDateFilter(): void {
    this.filterDate.set('');
    this.currentPage = 1;
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  getTargetDisplay(a: Analysis): string {
    if (a.job_name) return a.job_name;
    if (a.server_ip) return a.server_ip;
    return 'Machine Locale';
  }

  getStatusClass(status: string | null): string {
    const base = 'px-3 py-1.5 rounded-xl font-black text-[9px] uppercase tracking-widest border ';
    if (!status) return base + 'bg-slate-500/10 text-slate-500 border-slate-500/20';
    
    const s = status.toLowerCase();
    if (s.includes('menace')) return base + 'bg-red-500/10 text-red-500 border-red-500/20';
    if (s.includes('attention')) return base + 'bg-amber-500/10 text-amber-500 border-amber-500/20';
    return base + 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
  }

  viewDetails(a: Analysis): void {
    this.router.navigate(['/report'], { queryParams: { id: a.id } });
  }

  deleteAnalysis(a: Analysis): void {
    if (confirm('Voulez-vous supprimer cet audit de l\'historique ?')) {
      this.logService.deleteAnalysis(a.id).subscribe({
        next: (res: any) => {
          this.loadAnalyses(this.currentJobPublicId);
        }
      });
    }
  }
}
