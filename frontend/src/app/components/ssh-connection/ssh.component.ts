import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { LogService } from '../../services/log.service';
import { SidebarComponent } from '../sidebar/sidebar.component';

@Component({
  selector: 'app-ssh-connection',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule, SidebarComponent],
  templateUrl: './ssh.component.html',
  styleUrls: ['./ssh.component.css']
})
export class SshComponent implements OnInit, AfterViewChecked {
  @ViewChild('terminalContainer') private terminalContainer!: ElementRef;

  // Formulaire pour les identifiants et paramètres de connexion SSH
  sshForm: FormGroup;
  loading = false;
  error = '';
  success = false;
  showPassword = false;
  lastAnalysisId: number | null = null;
  recentConnections: any[] = [];
  
  // Variables pour le terminal virtuel SOC
  terminalLogs: string[] = [];

  constructor(private fb: FormBuilder, private logService: LogService) {
    // Initialisation du formulaire avec des valeurs par défaut sécurisées
    this.sshForm = this.fb.group({
      host: ['', [Validators.required]],
      user: ['', [Validators.required]],
      pass: ['', [Validators.required]],
      filePath: ['/var/log/syslog', [Validators.required]],
      numLines: [],
      auditDate: ['']
    });
  }

  ngOnInit(): void {
    // Chargement de l'historique local des connexions récentes
    this.loadRecent();
    this.addTerminalLog('Système SOC prêt pour l\'analyse distante.');
  }

  ngAfterViewChecked(): void {
    // Garde le terminal défilé vers le bas pour voir les derniers logs
    this.scrollToBottom();
  }

  /** Fait défiler le conteneur du terminal vers le bas */
  private scrollToBottom(): void {
    try {
      this.terminalContainer.nativeElement.scrollTop = this.terminalContainer.nativeElement.scrollHeight;
    } catch (err) {}
  }

  /** Ajoute une ligne horodatée dans la console virtuelle */
  addTerminalLog(msg: string): void {
    const time = new Date().toLocaleTimeString();
    this.terminalLogs.push(`[${time}] ${msg}`);
  }

  /** Récupère les connexions SSH enregistrées dans le cache du navigateur */
  loadRecent(): void {
    this.recentConnections = this.logService.getRecentConnections();
  }

  /** Remplit automatiquement le formulaire à partir d'une connexion récente */
  fillForm(conn: any): void {
    this.sshForm.patchValue({
      host: conn.host,
      user: conn.user,
      pass: conn.pass,
      filePath: conn.filePath,
      numLines: conn.numLines || 100,
      auditDate: conn.auditDate || conn.specificDate || ''
    });
    this.addTerminalLog(`Configuration chargée pour l'hôte : ${conn.host}`);
  }

  /** Déclenche le processus d'analyse SSH via le backend Python */
  startAnalysis(): void {
    if (this.sshForm.invalid) return;

    this.loading = true;
    this.error = '';
    this.success = false;
    this.terminalLogs = [];
    
    this.addTerminalLog(`ATTENTE : Tentative de connexion SSH vers ${this.sshForm.value.host}...`);

    this.logService.analyzeSSH(this.sshForm.value).subscribe({
      next: (response) => {
        this.loading = false;
        if (response?.status === 'success') {
          this.success = true;
          this.lastAnalysisId = response.analysis_id || null;
          this.addTerminalLog(`SUCCÈS : Analyse terminée avec succès. ID Rapport : ${this.lastAnalysisId}`);
          
          // Sauvegarde locale pour la prochaine utilisation
          this.logService.saveConnection(this.sshForm.value);
          this.loadRecent();
          return;
        }
        this.error = response?.message || "Erreur lors de l'analyse SSH";
        this.addTerminalLog(`ERREUR : ${this.error}`);
      },
      error: (err) => {
        this.loading = false;
        this.error = err.error?.message || "Erreur de connexion au serveur SOC";
        this.addTerminalLog(`ERREUR : ${this.error}`);
      }
    });
  }
}
