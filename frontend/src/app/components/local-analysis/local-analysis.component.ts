import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { LogService } from '../../services/log.service';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { HttpEventType, HttpResponse } from '@angular/common/http';

@Component({
  selector: 'app-local-analysis',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, SidebarComponent],
  templateUrl: './local-analysis.component.html',
  styleUrls: ['./local-analysis.component.css']
})
export class LocalAnalysisComponent {
  // Gestion du fichier sélectionné et des paramètres d'analyse
  selectedFile: File | null = null;
  numLines: number | null = null;
  loading = false;
  error = '';
  isDragging = false;
  
  // Indicateurs de progression de l'analyse IA
  progressValue = 0;
  statusMessage = '';
  private processingInterval: any;

  constructor(
    private logService: LogService,
    private router: Router
  ) {}

  /** Gère le survol du fichier lors du Drag & Drop */
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = true;
  }

  /** Gère la sortie de la zone de Drag & Drop */
  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  /** Gère le dépôt du fichier dans la zone prévue */
  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFile(files[0]);
    }
  }

  /** Gère la sélection de fichier via l'explorateur Windows */
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFile(input.files[0]);
    }
  }

  /** Valide l'extension du fichier (seuls .log et .txt sont admis) */
  private handleFile(file: File): void {
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (extension === 'log' || extension === 'txt') {
      this.selectedFile = file;
      this.error = '';
    } else {
      this.error = 'Seuls les fichiers .log et .txt sont acceptés.';
      this.selectedFile = null;
    }
  }

  /** Supprime le fichier sélectionné */
  removeFile(event: Event): void {
    event.stopPropagation();
    this.selectedFile = null;
    this.progressValue = 0;
    this.error = '';
  }

  /** Envoie le fichier au backend Flask pour une analyse IA complète */
  upload(): void {
    if (!this.selectedFile) return;

    this.loading = true;
    this.error = '';
    this.progressValue = 0;
    this.statusMessage = 'Analyse par IA en cours (Moteur LogAnalyzer Gemini)...';
    this.startProcessingAnimation();

    this.logService.uploadLogFile(this.selectedFile, this.numLines).subscribe({
      next: (res: any) => {
        this.completeAnalysis(res);
      },
      error: (err: any) => {
        this.error = err.error?.message || 'Erreur lors de l\'envoi du fichier.';
        this.loading = false;
        this.stopProcessingAnimation();
      }
    });
  }

  /** Simule une progression visuelle pendant que l'IA analyse les logs */
  private startProcessingAnimation(): void {
    if (this.processingInterval) return;
    
    this.statusMessage = 'Analyse par IA en cours (Moteur LogAnalyzer Gemini)...';
    
    this.processingInterval = setInterval(() => {
      if (this.progressValue < 99) {
        this.progressValue += 1;
      }
    }, 800);
  }

  /** Finalise l'analyse et redirige vers le tableau de bord */
  private completeAnalysis(res: any): void {
    this.stopProcessingAnimation();
    this.progressValue = 100;
    
    if (res.status === 'success' && res.analysis_id) {
      this.statusMessage = 'Analyse terminée avec succès ! Redirection vers le centre de commande...';
      setTimeout(() => {
        this.router.navigate(['/dashboard']);
      }, 1500);
    } else {
      this.error = res.message || 'Erreur lors de l\'analyse du fichier.';
      this.loading = false;
    }
  }

  /** Arrête le timer de l'animation de progression */
  private stopProcessingAnimation(): void {
    if (this.processingInterval) {
      clearInterval(this.processingInterval);
      this.processingInterval = null;
    }
  }
}
