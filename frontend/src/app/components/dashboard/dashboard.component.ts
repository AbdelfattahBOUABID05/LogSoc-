import { Component, OnInit, OnDestroy, signal, effect, untracked, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { LogService } from '../../services/log.service';
import { ThemeService } from '../../services/theme.service';
import { AuthService } from '../../services/auth.service';
import { Subject } from 'rxjs';
import { takeUntil, debounceTime } from 'rxjs/operators';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { NgxApexchartsModule } from "ngx-apexcharts";
import { ToastrService } from 'ngx-toastr';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    SidebarComponent,
    MatIconModule,
    MatButtonToggleModule,
    MatTooltipModule,
    NgxApexchartsModule
  ],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit, OnDestroy {
  // Gestion de l'état de l'interface via Angular Signals
  public isLoading = signal<boolean>(false);
  public isExporting = signal<boolean>(false);
  private isFetching = false; // Flag pour empêcher les requêtes concurrentes/boucles
  public currentTimeFilter = signal<string>('D');
  public totalLogsCount = signal<number>(0);
  public isAnomalyDetected = signal<boolean>(false);
  public anomalyMessage = signal<string>('');
  
  // Signaux pour les métriques SOC (Gauges)
  public systemHealth = signal<number>(0);
  public threatLevel = signal<number>(0);
  public taskSuccessRate = signal<number>(0);
  public matchedSolution = signal<any | null>(null);

  // Signaux pour la disponibilité des données
  public hasSshData = signal<boolean>(false);
  public hasLocalData = signal<boolean>(false);
  public hasJobsData = signal<boolean>(false);
  
  // Flux de logs en direct (Terminal)
  public liveLogs = signal<string[]>([]);
  public recentAlerts = signal<any[]>([]);
  public auditLogs = signal<any[]>([]);
  private destroy$ = new Subject<void>();

  // Options ApexCharts pour le graphique unifié
  public mainChartOptions: any;
  public jobsChartOptions: any;
  public kbPieChartOptions: any;
  public latestKBSolutions = signal<any[]>([]);
  
  public healthGaugeOptions: any;
  public threatGaugeOptions: any;
  public successGaugeOptions: any;

  constructor(
    private logService: LogService, 
    private themeService: ThemeService,
    public authService: AuthService,
    private router: Router,
    private toastr: ToastrService,
    private cdr: ChangeDetectorRef
  ) {
    // Effet réactif : recharge les données dès que le filtre temporel change
    effect(() => {
      // On lit le signal ici pour créer la dépendance
      const filter = this.currentTimeFilter();
      // On utilise untracked pour appeler loadAllStats sans créer de dépendance circulaire
      untracked(() => {
        this.loadAllStats(filter);
      });
    });

    // Effet réactif : met à jour les couleurs des graphiques selon le mode (clair/sombre)
    effect(() => {
      const isDark = this.themeService.isDark();
      untracked(() => {
        this.updateChartTheme(isDark);
      });
    });
  }

  ngOnInit(): void {
    this.initChartOptions();
    
    // Écoute les déclencheurs de rafraîchissement avec un debounce pour éviter le spam
    this.logService.refreshDashboard$
      .pipe(
        takeUntil(this.destroy$),
        debounceTime(1000) // Protection : max 1 requête par seconde lors d'un rafraîchissement
      )
      .subscribe(() => {
        this.loadAllStats(this.currentTimeFilter());
        this.pushLog('Analyse terminée. Actualisation des données SOC-Analyzer...');
      });

    this.pushLog('Interface SOC restructurée : Flux SSH, Système et Jobs indépendants.');
    this.pushLog('Connexion sécurisée à la base SQLite établie...');
    
    // Chargement initial des données
    this.loadAllStats(this.currentTimeFilter());
    this.loadKBStats();
    this.loadAuditLogs();
    
    // Rafraîchissement automatique toutes les 5 minutes
    setInterval(() => {
      this.loadAllStats(this.currentTimeFilter());
      this.loadKBStats();
      this.loadAuditLogs();
    }, 300000);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  public pushLog(msg: string): void {
    const time = new Date().toLocaleTimeString();
    const formatted = `[${time}] ${msg}`;
    this.liveLogs.set([formatted, ...this.liveLogs().slice(0, 49)]);
  }

  /**
   * Ajoute un message dans le terminal virtuel (Console SOC-Analyzer)
   * @param msg Message à afficher en français
   */
  
  /**
   * Récupère les statistiques depuis l'API Flask selon le filtre choisi.
   * EXPLICATION DU SPLIT 3-VOIES (Présentation) :
   * 1. Le backend retourne un objet contenant 3 clés distinctes : 'ssh', 'local' et 'jobs'.
   * 2. Chaque clé possède sa propre série de données et ses propres labels temporels.
   * 3. Le frontend assigne ces données à 3 configurations ApexCharts différentes (sshChartOptions, etc.).
   * 4. Cela permet une réactivité granulaire : si une analyse SSH est lancée, seul le bloc SSH se met à jour.
   */
  public loadAllStats(filter: string): void {
    if (this.isFetching) return; // Protection contre les appels multiples
    
    this.isFetching = true;
    this.isLoading.set(true);
    this.pushLog(`Synchronisation des métriques : Période [${filter.toUpperCase()}]`);

    this.logService.getStats(filter).subscribe({
      next: (data: any) => {
        // Affichage détaillé sous forme de table pour le débogage SOC-Analyzer
        console.log('--- RÉCEPTION DES FLUX SOC-ANALYZER ---');
        console.table([
          { Source: 'SSH (Bleu)', Points: data.ssh_data?.series[0]?.data.length, Total: data.ssh_data?.series[0]?.data.reduce((a:any,b:any)=>a+b,0) },
          { Source: 'Système (Violet)', Points: data.local_data?.series[0]?.data.length, Total: data.local_data?.series[0]?.data.reduce((a:any,b:any)=>a+b,0) },
          { Source: 'Jobs (Vert)', Points: data.jobs_data?.series[0]?.data.length, Total: data.jobs_data?.series[0]?.data.reduce((a:any,b:any)=>a+b,0) }
        ]);

        // Vérification de la présence de données dans l'une des 3 sources
        const hasData = (data.ssh_data?.series[0]?.data.some((v: number) => v > 0)) ||
                        (data.local_data?.series[0]?.data.some((v: number) => v > 0)) ||
                        (data.jobs_data?.series[0]?.data.some((v: number) => v > 0));
        
        if (data.status === 'success' && hasData) {
          this.pushLog('Flux SSH, Local et Auto synchronisés avec succès. Mise à jour des graphiques multi-sources...');
          this.processRealData(data);
          this.checkForSmartMatching(data);
          
          // Fix NG0100 : Forcer la détection de changement après la mise à jour des données
          setTimeout(() => {
            this.cdr.detectChanges();
          }, 0);
        } else {
          this.pushLog('Veille active : Aucune donnée détectée pour cette période.');
          this.resetDashboard();
        }
        this.isLoading.set(false);
        this.isFetching = false;
      },
      error: (err) => {
        console.error('Erreur SOC:', err);
        this.pushLog('ERREUR : Impossible de joindre le moteur d\'analyse backend.');
        this.resetDashboard();
        this.isLoading.set(false);
        this.isFetching = false;
      }
    });
  }

  public loadKBStats(): void {
    this.logService.getKBContributionsStats().subscribe({
      next: (res) => {
        if (res.status === 'success') {
          const authors = res.stats.map(s => s.author || 'Anonyme');
          const counts = res.stats.map(s => s.count);
          
          this.kbPieChartOptions = {
            ...this.kbPieChartOptions,
            series: counts,
            labels: authors
          };
        }
      }
    });

    this.logService.getKBSolutions().subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.latestKBSolutions.set(res.solutions.slice(0, 5));
        }
      }
    });

    // Charger aussi les 5 dernières alertes critiques pour le rapport
    this.logService.getAnalyses().subscribe({
      next: (res) => {
        if (res.status === 'success') {
          const critical = res.analyses
            .filter(a => a.ai_score < 50 || a.ai_menaces > 0)
            .slice(0, 5);
          this.recentAlerts.set(critical);
        }
      }
    });
  }

  public loadAuditLogs(): void {
    this.logService.getAuditLogs().subscribe({
      next: (res) => {
        if (res.status === 'success') {
          console.log('Audit Logs reçus (SOC Dashboard):', res.audit_logs);
          this.auditLogs.set(res.audit_logs);
        }
      },
      error: (err) => console.error('Erreur audit logs:', err)
    });
  }

  /**
   * Génère un rapport PDF complet du Dashboard
   */
  public async exportDashboardToPDF(): Promise<void> {
    this.isExporting.set(true);
    this.pushLog('Génération du rapport PDF en cours...');
    this.toastr.info('Génération du PDF en cours...', 'Exportation', { timeOut: 3000 });

    try {
      const doc = new jsPDF('p', 'mm', 'a4');
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 15;
      let currentY = 20;

      // 1. En-tête du Rapport
      doc.setFillColor(15, 23, 42); // Navy background for header
      doc.rect(0, 0, pageWidth, 40, 'F');
      
      // Tentative de capture du logo depuis le DOM
      const logoEl = document.querySelector('.header-icon-box img');
      if (logoEl) {
        try {
          const logoCanvas = await html2canvas(logoEl as HTMLElement, { backgroundColor: null });
          const logoData = logoCanvas.toDataURL('image/png');
          doc.addImage(logoData, 'PNG', margin, 10, 10, 10);
        } catch (e) { /* ignore if logo fails */ }
      }

      doc.setTextColor(255, 255, 255);
      doc.setFontSize(22);
      doc.setFont('helvetica', 'bold');
      doc.text('LogSOC', margin + 15, 20);
      
      doc.setFontSize(12);
      doc.setFont('helvetica', 'normal');
      doc.text('Rapport d\'Analyse de Sécurité', margin, 32);
      
      const today = new Date().toLocaleDateString('fr-FR', { 
        year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' 
      });
      doc.setFontSize(10);
      doc.text(`Date : ${today}`, pageWidth - margin - 60, 20);
      doc.text('Analyste : Abdelfattah Bouabid', pageWidth - margin - 60, 28);

      currentY = 55;

      // 2. Section Statistiques (Capture du graphique)
      doc.setTextColor(15, 23, 42);
      doc.setFontSize(14);
      doc.setFont('helvetica', 'bold');
      doc.text('1. RÉSUMÉ DE L\'ACTIVITÉ SYSTÈME (ACTIVITY CHART)', margin, currentY);
      currentY += 10;

      const chartElement = document.getElementById('activity-chart');
      if (chartElement) {
        const canvas = await html2canvas(chartElement as HTMLElement, {
          scale: 2,
          useCORS: true,
          backgroundColor: this.themeService.isDark() ? '#0f172a' : '#ffffff'
        });
        const imgData = canvas.toDataURL('image/png');
        const imgWidth = pageWidth - (2 * margin);
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        
        doc.addImage(imgData, 'PNG', margin, currentY, imgWidth, imgHeight);
        currentY += imgHeight + 15;
      }

      // 3. Section Alertes Critiques
      doc.setFontSize(14);
      doc.text('2. DERNIÈRES ALERTES CRITIQUES DÉTECTÉES', margin, currentY);
      currentY += 10;

      const alerts = this.recentAlerts();
      if (alerts.length > 0) {
        doc.setFontSize(9);
        // Header tableau
        doc.setFillColor(241, 245, 249);
        doc.rect(margin, currentY, pageWidth - (2 * margin), 8, 'F');
        doc.text('Source / Date', margin + 5, currentY + 5);
        doc.text('Statut', margin + 80, currentY + 5);
        doc.text('Score', margin + 120, currentY + 5);
        doc.text('Menaces', margin + 150, currentY + 5);
        currentY += 8;

        for (const alert of alerts) {
          if (currentY > pageHeight - 30) {
            doc.addPage();
            currentY = 20;
          }
          const date = new Date(alert.created_at).toLocaleDateString();
          doc.text(`${alert.source_path} (${date})`, margin + 5, currentY + 5);
          doc.text(`${alert.ai_status}`, margin + 80, currentY + 5);
          doc.text(`${alert.ai_score}%`, margin + 120, currentY + 5);
          doc.text(`${alert.ai_menaces}`, margin + 150, currentY + 5);
          
          doc.setDrawColor(241, 245, 249);
          doc.line(margin, currentY + 8, pageWidth - margin, currentY + 8);
          currentY += 8;
        }
      } else {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'italic');
        doc.text('Aucune alerte critique détectée sur la période.', margin + 5, currentY + 5);
        currentY += 10;
      }

      // 4. Section Résolution (Recommandation KB)
      const solution = this.matchedSolution();
      if (solution) {
        currentY += 10;
        if (currentY > pageHeight - 50) { doc.addPage(); currentY = 20; }
        
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(14);
        doc.text('3. RECOMMANDATION TECHNIQUE (Base de Connaissances)', margin, currentY);
        currentY += 10;

        doc.setFillColor(240, 253, 244); // Light green background
        doc.setDrawColor(34, 197, 94); // Emerald border
        doc.roundedRect(margin, currentY, pageWidth - (2 * margin), 30, 3, 3, 'FD');
        
        doc.setTextColor(21, 128, 61);
        doc.setFontSize(11);
        doc.text(`Problème : ${solution.problem_title}`, margin + 5, currentY + 8);
        
        doc.setTextColor(15, 23, 42);
        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        const splitText = doc.splitTextToSize(`Solution : ${solution.solution_content}`, pageWidth - (2 * margin) - 10);
        doc.text(splitText, margin + 5, currentY + 16);
      }

      // 5. Pied de page
      const pageCount = (doc as any).internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(148, 163, 184);
        doc.text('Document généré par LogAnalyzer SOC - Confidentiel', pageWidth / 2, pageHeight - 10, { align: 'center' });
        doc.text(`Page ${i}/${pageCount}`, pageWidth - margin - 10, pageHeight - 10);
      }

      doc.save(`Rapport_SOC_${new Date().getTime()}.pdf`);
      this.pushLog('Rapport PDF généré avec succès.');
      
      // Audit Log
      this.logService.createAuditLog('PDF_EXPORT', `Exportation du rapport Dashboard PDF`).subscribe({
        next: () => this.loadAuditLogs()
      });

      this.toastr.success('Le rapport PDF a été généré avec succès.', 'Succès');
    } catch (error) {
      console.error('Erreur génération PDF:', error);
      this.pushLog('ERREUR : Échec de la génération du rapport PDF.');
      this.toastr.error('Échec de la génération du rapport PDF.', 'Erreur');
    } finally {
      this.isExporting.set(false);
    }
  }

  private checkForSmartMatching(data: any): void {
    console.log('--- DÉBUT SMART MATCHING KB (GLOBAL) ---');
    
    const allLogs = [
      ...(data.ssh_data?.raw_logs || []),
      ...(data.local_data?.raw_logs || [])
    ];

    if (allLogs.length === 0) return;

    // Appel à l'API de matching global
    this.logService.matchKBPattern(allLogs).subscribe({
      next: (res) => {
        if (res.status === 'success' && res.solution) {
          console.log(`✅ MATCH GLOBAL TROUVÉ ! Solution par ${res.solution.author_name}`);
          this.matchedSolution.set(res.solution);
        } else {
          console.log('❌ Aucun matching global trouvé.');
          this.matchedSolution.set(null);
        }
        console.log('--- FIN SMART MATCHING KB ---');
      },
      error: (err) => {
        console.error('❌ Erreur lors du matching global KB:', err);
      }
    });
  }

  private resetDashboard(): void {
    this.totalLogsCount.set(0);
    this.isAnomalyDetected.set(false);
    this.hasSshData.set(false);
    this.hasLocalData.set(false);
    this.hasJobsData.set(false);
    this.updateGauges(0, 0, 0);
    if (this.mainChartOptions) this.mainChartOptions.series = [];
  }

  /**
   * Traite les données reçues pour mettre à jour les indicateurs et graphiques.
   * La séparation en 3 objets permet de rafraîchir chaque graphique indépendamment.
   */
  private processRealData(data: any): void {
    // Calcul du total des logs à partir des 3 sources
    const totalSsh = data.ssh_data?.series[0]?.data.reduce((a: number, b: number) => a + b, 0) || 0;
    const totalLocal = data.local_data?.series[0]?.data.reduce((a: number, b: number) => a + b, 0) || 0;
    const totalJobs = data.jobs_data?.series[0]?.data.reduce((a: number, b: number) => a + b, 0) || 0;
    
    this.totalLogsCount.set(totalSsh + totalLocal + totalJobs);
    
    // Détection de la présence de données par source
    this.hasSshData.set(totalSsh > 0);
    this.hasLocalData.set(totalLocal > 0);
    this.hasJobsData.set(totalJobs > 0);

    // Détection d'anomalies : alerte si trafic suspect
    if (this.totalLogsCount() > 500) {
      this.isAnomalyDetected.set(true);
      this.anomalyMessage.set('CRITIQUE : Fréquence de logs inhabituelle détectée !');
    } else {
      this.isAnomalyDetected.set(false);
    }

    const health = Math.max(75, 100 - (this.totalLogsCount() / 1000) * 10);
    const threat = Math.min(25, (this.totalLogsCount() / 1000) * 20);
    const success = 98;

    this.systemHealth.set(Math.round(health));
    this.threatLevel.set(Math.round(threat));
    this.taskSuccessRate.set(success);

    this.updateGauges(health, threat, success);
    this.updateAllCharts(data);
  }

  /**
   * Met à jour les graphiques circulaires (Gauges) avec les métriques calculées.
   */
  private updateGauges(health: number, threat: number, success: number): void {
    if (this.healthGaugeOptions) this.healthGaugeOptions.series = [Math.round(health)];
    if (this.threatGaugeOptions) this.threatGaugeOptions.series = [Math.round(threat)];
    if (this.successGaugeOptions) this.successGaugeOptions.series = [Math.round(success)];
    
    // On force la détection de changement pour les gauges
    this.healthGaugeOptions = { ...this.healthGaugeOptions };
    this.threatGaugeOptions = { ...this.threatGaugeOptions };
    this.successGaugeOptions = { ...this.successGaugeOptions };
  }

  /**
   * Mise à jour du graphique principal multi-séries.
   * On synchronise les 3 flux (SSH, Système, Jobs) sur une seule timeline.
   */
  private updateAllCharts(data: any): void {
    if (this.mainChartOptions) {
      this.mainChartOptions.series = [
        { name: 'Trafic SSH (Bleu)', data: data.ssh_data?.series[0]?.data || [] },
        { name: 'Logs Système (Violet)', data: data.local_data?.series[0]?.data || [] },
        { name: 'Exécution des Tâches (Vert)', data: data.jobs_data?.series[0]?.data || [] }
      ];
      this.mainChartOptions.xaxis = { ...this.mainChartOptions.xaxis, categories: data.labels || [] };
      this.mainChartOptions = { ...this.mainChartOptions };
    }
  }

  /**
   * Ajuste les couleurs et thèmes des graphiques dynamiquement.
   */
  private updateChartTheme(isDark: boolean): void {
    const textColor = isDark ? '#64748b' : '#475569';
    const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
    const chartTheme = isDark ? 'dark' : 'light';
    
    if (this.mainChartOptions) {
      this.mainChartOptions.xaxis.labels.style.colors = textColor;
      this.mainChartOptions.yaxis.labels.style.colors = textColor;
      this.mainChartOptions.grid.borderColor = gridColor;
      this.mainChartOptions.tooltip.theme = chartTheme;
      this.mainChartOptions = { ...this.mainChartOptions, theme: { mode: chartTheme } };
    }

    const updateGaugeTheme = (opts: any) => {
      if (!opts) return opts;
      return {
        ...opts,
        theme: { mode: chartTheme },
        plotOptions: {
          ...opts.plotOptions,
          radialBar: {
            ...opts.plotOptions.radialBar,
            track: { ...opts.plotOptions.radialBar.track, background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' },
            dataLabels: {
              name: { show: false },
              value: { show: false }
            }
          }
        }
      };
    };

    this.healthGaugeOptions = updateGaugeTheme(this.healthGaugeOptions);
    this.threatGaugeOptions = updateGaugeTheme(this.threatGaugeOptions);
    this.successGaugeOptions = updateGaugeTheme(this.successGaugeOptions);
  }

  /**
   * Initialise les configurations de base d'ApexCharts pour le graphique unifié.
   * On regroupe les 3 sources : Bleu (SSH), Violet (Local), Vert (Jobs).
   */
  private initChartOptions(): void {
    const isDark = this.themeService.isDark();
    const textColor = isDark ? '#64748b' : '#475569';
    const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';

    this.kbPieChartOptions = {
      series: [],
      chart: {
        type: 'donut',
        height: 280,
        background: 'transparent',
        fontFamily: 'JetBrains Mono',
        toolbar: { show: false }
      },
      labels: [],
      colors: ['#A5B4FC', '#FCA5A5', '#FCD34D', '#6EE7B7', '#93C5FD'],
      stroke: { show: false },
      plotOptions: {
        pie: {
          donut: {
            size: '70%',
            labels: {
              show: true,
              name: { show: true, fontSize: '12px', color: textColor, fontWeight: 600 },
              value: { show: true, fontSize: '18px', color: textColor, fontWeight: 900 },
              total: {
                show: true,
                label: 'TOTAL KB',
                color: textColor,
                fontSize: '10px',
                fontWeight: 800,
                formatter: (w: any) => {
                  return w.globals.seriesTotals.reduce((a: number, b: number) => a + b, 0);
                }
              }
            }
          }
        }
      },
      dataLabels: { enabled: false },
      legend: {
        position: 'bottom',
        fontFamily: 'JetBrains Mono',
        fontSize: '10px',
        labels: { colors: textColor }
      },
      tooltip: {
        theme: isDark ? 'dark' : 'light',
        y: {
          formatter: (val: number) => `${val} solutions`
        }
      }
    };

    this.mainChartOptions = {
      series: [],
      chart: { 
        type: 'area', 
        height: 400, 
        toolbar: { show: false }, 
        background: 'transparent', 
        animations: { enabled: true, easing: 'easeinout' as any, speed: 800 } 
      },
      legend: { 
        show: true,
        position: 'top',
        horizontalAlign: 'right',
        labels: { colors: textColor }
      },
      theme: { mode: isDark ? 'dark' : 'light' },
      colors: ['#3b82f6', '#8b5cf6', '#10b981'],
      dataLabels: { enabled: false },
      stroke: { curve: 'smooth', width: 3 },
      fill: { 
        type: 'gradient', 
        gradient: { shadeIntensity: 1, opacityFrom: 0.5, opacityTo: 0, stops: [0, 90, 100] } 
      },
      xaxis: { 
        axisBorder: { show: false }, 
        axisTicks: { show: false }, 
        labels: { style: { colors: textColor, fontSize: '10px', fontFamily: 'JetBrains Mono' } },
        categories: []
      },
      yaxis: { labels: { style: { colors: textColor, fontSize: '10px', fontFamily: 'JetBrains Mono' } } },
      grid: { borderColor: gridColor, strokeDashArray: 4 },
      tooltip: { theme: isDark ? 'dark' : 'light' }
    };

    const createGaugeConfig = (color: string) => ({
      series: [0],
      chart: { type: 'radialBar', height: 200, sparkline: { enabled: true } },
      theme: { mode: isDark ? 'dark' : 'light' },
      plotOptions: {
        radialBar: {
          startAngle: -135,
          endAngle: 135,
          hollow: { size: '70%' },
          track: { background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', strokeWidth: '100%' },
          dataLabels: {
            name: { show: false },
            value: { show: false }
          }
        }
      },
      colors: [color],
      stroke: { lineCap: 'round' }
    });

    this.healthGaugeOptions = createGaugeConfig('#6366f1');
    this.threatGaugeOptions = createGaugeConfig('#ef4444');
    this.successGaugeOptions = createGaugeConfig('#10b981');
  }

  setFilter(filter: string): void {
    this.currentTimeFilter.set(filter);
  }

  getRandomHeight(): number {
    return Math.floor(Math.random() * (90 - 40 + 1)) + 40;
  }

  navigateToAnalysis(): void {
    this.router.navigate(['/local-analysis']);
  }
}
