import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router, NavigationEnd, NavigationStart } from '@angular/router';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { LoadingComponent } from './components/loading/loading.component';
import { ThemeService } from './services/theme.service';
import { LogService, Notification } from './services/log.service';
import { AuthService } from './services/auth.service';
import { LoadingService } from './services/loading.service';
import { MatIconModule } from '@angular/material/icon';
import { filter } from 'rxjs/operators';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule, SidebarComponent, MatIconModule, LoadingComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  pageTitle = 'Dashboard';
  pageSubtitle = 'Observabilité Globale';
  pageIcon = 'dashboard';

  notifications: Notification[] = [];
  unreadCount = 0;
  showNotifications = false;

  constructor(
    public themeService: ThemeService,
    private logService: LogService,
    private authService: AuthService,
    private router: Router,
    private loadingService: LoadingService
  ) {}

  ngOnInit(): void {
    // Show loading on initial app load
    this.loadingService.showAndHide(1500);

    this.updateHeaderInfo(this.router.url);
    this.loadNotifications();

    this.router.events.pipe(
      filter(event => event instanceof NavigationStart)
    ).subscribe(() => {
      // Show loading on route change start
      this.loadingService.show();
    });

    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      this.updateHeaderInfo(event.url);
      this.showNotifications = false;
      // Hide loading on route change end (after a short delay for smoothness)
      setTimeout(() => this.loadingService.hide(), 800);
    });

    setInterval(() => {
      if (this.shouldShowLayout()) {
        this.loadNotifications();
      }
    }, 60000);
  }

  public shouldShowLayout(): boolean {
    const isLoginRoute = this.router.url === '/login' || this.router.url === '/';
    return this.authService.isLoggedIn() && !isLoginRoute;
  }

  private updateHeaderInfo(url: string): void {
    if (url.includes('dashboard')) {
      this.pageTitle = 'Tableau de bord';
      this.pageSubtitle = 'Observabilité Globale';
      this.pageIcon = 'dashboard';
    } else if (url.includes('ssh')) {
      this.pageTitle = 'Analyse SSH';
      this.pageSubtitle = 'Forensics Distant';
      this.pageIcon = 'terminal';
    } else if (url.includes('local')) {
      this.pageTitle = 'Analyse Locale';
      this.pageSubtitle = 'Inspection de Fichiers';
      this.pageIcon = 'upload_file';
    } else if (url.includes('jobs')) {
      this.pageTitle = 'Gestion des Jobs';
      this.pageSubtitle = 'Automatisation SOC';
      this.pageIcon = 'task';
    } else if (url.includes('history')) {
      this.pageTitle = 'Historique SOC';
      this.pageSubtitle = 'Archives & Forensics';
      this.pageIcon = 'history';
    } else if (url.includes('knowledge-base')) {
      this.pageTitle = 'Base de Connaissances';
      this.pageSubtitle = 'Solutions & Résolutions';
      this.pageIcon = 'library_books';
    } else if (url.includes('profile')) {
      this.pageTitle = 'Mon Profil';
      this.pageSubtitle = 'Expert SOC';
      this.pageIcon = 'account_circle';
    } else if (url.includes('settings')) {
      this.pageTitle = 'Paramètres';
      this.pageSubtitle = 'Configuration Système';
      this.pageIcon = 'settings';
    } else {
      this.pageTitle = 'LogSOC';
      this.pageSubtitle = 'Sécurité Intelligente';
      this.pageIcon = 'shield';
    }
  }

  isDark(): boolean {
    return this.themeService.isDark();
  }

  loadNotifications(): void {
    this.logService.getNotifications().subscribe({
      next: (res) => {
        this.notifications = res.notifications;
        this.unreadCount = this.notifications.filter(n => !n.is_read).length;
      }
    });
  }

  toggleNotifications(): void {
    this.showNotifications = !this.showNotifications;
  }

  onNotificationClick(notif: Notification): void {
    if (!notif.is_read) {
      this.logService.markNotificationAsRead(notif.id).subscribe(() => {
        notif.is_read = true;
        this.unreadCount = Math.max(0, this.unreadCount - 1);
      });
    }
    if (notif.link) {
      this.router.navigateByUrl(notif.link);
      this.showNotifications = false;
    }
  }
}
