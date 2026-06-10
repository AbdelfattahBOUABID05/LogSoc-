import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { LogService } from '../../services/log.service';
import { NotificationService } from '../../services/notification.service';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  templateUrl: './jobs.component.html',
  styleUrls: ['./jobs.component.css']
})
export class JobsComponent implements OnInit {
  // Liste des tâches planifiées récupérées depuis le serveur
  jobs: any[] = [];
  showCreateModal = false;
  togglingJobId: number | null = null;
  
  // Variables pour le support Cron personnalisé
  isCustomCron = false;
  cronExpression = '';
  
  // Objet représentant une nouvelle tâche à planifier
  newJob = {
    name: '',
    target_ip: '',
    log_path: '/var/log/syslog',
    frequency: 'daily',
    custom_interval: 30,
    custom_unit: 'minutes',
    cron_expression: '',
    ssh_user: '',
    ssh_pass: ''
  };

  constructor(
    private logService: LogService,
    private notify: NotificationService,
    private router: Router
  ) {}

  ngOnInit(): void {
    // Chargement initial des jobs à l'ouverture du composant
    this.fetchScheduledJobs();
  }

  /** Gère le basculement vers l'affichage du champ Cron personnalisé */
  onPlanificationChange(event: any): void {
    const value = event.target.value;
    this.isCustomCron = (value === 'custom');
    if (!this.isCustomCron) {
      this.cronExpression = '';
    }
  }

  /** Récupère la liste des jobs programmés pour l'utilisateur actuel */
  fetchScheduledJobs(): void {
    this.logService.getJobs().subscribe({
      next: (data: any) => {
        if (data.status === 'success') {
          this.jobs = data.jobs;
        }
      },
      error: (err: any) => {
        console.error('Error fetching jobs:', err);
        this.notify.error('Impossible de charger la liste des jobs.');
      }
    });
  }

  /** Envoie une demande de création de nouveau job au backend */
  createJob(): void {
    if (!this.newJob.name || !this.newJob.target_ip || !this.newJob.ssh_user || !this.newJob.ssh_pass) {
      this.notify.warning('Veuillez remplir tous les champs obligatoires.');
      return;
    }

    // Ajout de l'expression Cron si nécessaire
    const payload = { 
      ...this.newJob,
      cron_expression: this.isCustomCron ? this.cronExpression : null 
    };

    this.logService.createJob(payload).subscribe({
      next: (res: any) => {
        this.notify.success(res.message || 'Demande de job créée avec succès.');
        this.showCreateModal = false;
        this.fetchScheduledJobs();
        // Réinitialisation du formulaire après succès
        this.newJob = { 
          name: '',
          target_ip: '', 
          log_path: '/var/log/syslog', 
          frequency: 'daily', 
          custom_interval: 30,
          custom_unit: 'minutes',
          cron_expression: '',
          ssh_user: '',
          ssh_pass: ''
        };
      },
      error: (err: any) => {
        this.notify.error('Erreur lors de la création du job.');
      }
    });
  }

  /** Active ou désactive un job existant */
  toggleJob(id: number): void {
    this.togglingJobId = id;
    this.logService.toggleJob(id).subscribe({
      next: (res: any) => {
        this.notify.success(res.message || 'Statut du job mis à jour.');
        this.fetchScheduledJobs();
        this.togglingJobId = null;
      },
      error: (err: any) => {
        this.notify.error('Erreur lors de la modification du job.');
        this.togglingJobId = null;
      }
    });
  }

  /** Supprime définitivement un job planifié */
  deleteJob(id: number): void {
    if (confirm('Voulez-vous vraiment supprimer ce job ?')) {
      this.logService.deleteJob(id).subscribe({
        next: (res: any) => {
          this.notify.success(res.message || 'Job supprimé avec succès.');
          this.fetchScheduledJobs();
        },
        error: (err: any) => {
          this.notify.error('Erreur lors de la suppression.');
        }
      });
    }
  }

  getStatusClass(status: string): string {
    const base = 'px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border ';
    switch(status.toLowerCase()) {
      case 'active': return base + 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
      case 'inactive': return base + 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      case 'pending': return base + 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      default: return base + 'bg-slate-500/10 text-slate-500 border-slate-500/20';
    }
  }

  viewJobHistory(jobId: string): void {
    this.router.navigate(['/history'], { queryParams: { job_id: jobId } });
  }
}
