import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ActivatedRoute } from '@angular/router';
import { LogService, KBSolution } from '../../services/log.service';
import { AuthService } from '../../services/auth.service';
import { SidebarComponent } from '../sidebar/sidebar.component';

@Component({
  selector: 'app-knowledge-base',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatIconModule,
    MatTooltipModule,
    SidebarComponent
  ],
  templateUrl: './knowledge-base.component.html',
  styleUrls: ['./knowledge-base.component.css']
})
export class KnowledgeBaseComponent implements OnInit {
  public solutions = signal<KBSolution[]>([]);
  public isLoading = signal<boolean>(false);
  public highlightedId = signal<number | null>(null);
  
  // Modèle pour le formulaire
  public newSolution: KBSolution = {
    problem_title: '',
    log_pattern: '',
    solution_content: '',
    author_name: ''
  };

  constructor(
    private logService: LogService,
    private authService: AuthService,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      if (params['highlight']) {
        this.highlightedId.set(+params['highlight']);
      }
    });
    this.loadSolutions();
  }

  loadSolutions(): void {
    this.isLoading.set(true);
    this.logService.getKBSolutions().subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.solutions.set(res.solutions);
          
          // Petit délai pour scroller vers l'élément mis en évidence
          if (this.highlightedId()) {
            setTimeout(() => {
              const el = document.getElementById(`sol-${this.highlightedId()}`);
              if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            }, 500);
          }
        }
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Erreur chargement KB:', err);
        this.isLoading.set(false);
      }
    });
  }

  saveSolution(): void {
    if (!this.newSolution.problem_title || !this.newSolution.log_pattern || !this.newSolution.solution_content) {
      return;
    }

    // Récupérer l'auteur actuel
    const firstName = localStorage.getItem('firstName');
    const lastName = localStorage.getItem('lastName');
    const author = (firstName && lastName) ? `${firstName} ${lastName}` : (localStorage.getItem('username') || 'Anonyme');
    
    this.newSolution.author_name = author;

    this.isLoading.set(true);
    this.logService.createKBSolution(this.newSolution).subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.solutions.set([res.solution, ...this.solutions()]);
          // Reset form
          this.newSolution = {
            problem_title: '',
            log_pattern: '',
            solution_content: '',
            author_name: ''
          };
        }
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Erreur sauvegarde solution:', err);
        this.isLoading.set(false);
      }
    });
  }

  deleteSolution(id: number | undefined): void {
    if (!id) return;
    
    if (confirm('Voulez-vous vraiment supprimer cette solution ?')) {
      this.logService.deleteKBSolution(id).subscribe({
        next: (res) => {
          if (res.status === 'success') {
            this.solutions.set(this.solutions().filter(s => s.id !== id));
          }
        },
        error: (err) => console.error('Erreur suppression solution:', err)
      });
    }
  }

  canDelete(solution: KBSolution): boolean {
    const role = localStorage.getItem('role')?.toLowerCase();
    if (role === 'admin') return true;

    const firstName = localStorage.getItem('firstName');
    const lastName = localStorage.getItem('lastName');
    const currentUser = (firstName && lastName) ? `${firstName} ${lastName}` : (localStorage.getItem('username') || 'Anonyme');
    
    return solution.author_name === currentUser;
  }
}
