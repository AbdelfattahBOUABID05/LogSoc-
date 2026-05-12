import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { LogService, Notification } from '../../services/log.service';
import { NotificationService } from '../../services/notification.service';
import { ThemeService } from '../../services/theme.service';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [
    CommonModule, 
    RouterModule, 
    MatSlideToggleModule,
    MatIconModule,
    MatTooltipModule
  ],
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.css']
})
export class SidebarComponent implements OnInit {
  // Liste des notifications système (alertes de sécurité, succès de jobs)
  notifications: Notification[] = [];
  unreadCount = 0;
  showNotifications = false;

  constructor(
    private authService: AuthService,
    private logService: LogService,
    private notify: NotificationService,
    private themeService: ThemeService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadNotifications();
    // Rafraîchissement automatique des notifications toutes les 60 secondes
    setInterval(() => this.loadNotifications(), 60000);
  }

  /** Vérifie si le thème sombre est activé */
  isDark(): boolean {
    return this.themeService.isDark();
  }

  /** Bascule entre le mode clair et le mode sombre */
  toggleTheme(): void {
    this.themeService.toggleTheme();
  }

  /** Vérifie si l'utilisateur possède les droits administrateur */
  isAdmin(): boolean {
    return this.authService.isAdmin();
  }

  /** Vérifie s'il s'agit de la première connexion de l'utilisateur */
  isFirstLogin(): boolean {
    return this.authService.isFirstLogin();
  }

  /** Charge les alertes et notifications depuis le backend Flask */
  loadNotifications(): void {
    this.logService.getNotifications().subscribe({
      next: (res) => {
        this.notifications = res.notifications;
        this.unreadCount = this.notifications.filter(n => !n.is_read).length;
      }
    });
  }

  /** Affiche ou masque le menu déroulant des notifications */
  toggleNotifications(): void {
    this.showNotifications = !this.showNotifications;
  }

  /** Gère le clic sur une notification (marquer comme lue + redirection) */
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

  /** Déconnexion sécurisée de l'utilisateur */
  logout(): void {
    this.authService.logout().subscribe({
      next: () => {
        this.router.navigate(['/login']);
      }
    });
  }

  getUserRole(): string {
    return localStorage.getItem('role') || 'USER';
  }

  getUsername(): string {
    return localStorage.getItem('firstName') || 'Abdelfattah';
  }
}
