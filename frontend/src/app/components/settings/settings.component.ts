import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { LogService, SettingsPayload } from '../../services/log.service';
import { CommonDialogService } from '../../services/common-dialog.service';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, MatIconModule],
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.css']
})
export class SettingsComponent implements OnInit {
  settings: SettingsPayload = {
    emailNotifications: false,
    notificationEmail: '',
    smtpServer: 'smtp.gmail.com',
    smtpPort: 587,
    smtpUser: '',
    smtpPassword: ''
  };

  loading: boolean = false;
  showAdvanced: boolean = false;
  username: string = 'analyste';

  constructor(
    private logService: LogService, 
    private http: HttpClient,
    private dialogService: CommonDialogService
  ) {}

  ngOnInit(): void {
    this.loadSettings();
    this.loadProfile();
  }

  loadSettings(): void {
    this.logService.getSettings().subscribe({
      next: (response: any) => {
        if (response.status === 'success' && response.settings) {
          this.settings = {
            ...response.settings,
            smtpPassword: ''
          };
        }
      },
      error: (err: any) => console.error('Settings load error:', err)
    });
  }

  loadProfile(): void {
    const apiUrl = environment.apiUrl;
    this.http.get<any>(`${apiUrl}/profile`).subscribe({
      next: (res: any) => {
        this.username = res.username || 'analyste';
      },
      error: (err: any) => console.error('Profile load error:', err)
    });
  }

  saveSettings(): void {
    this.loading = true;
    this.logService.saveSettings(this.settings).subscribe({
      next: (response: any) => {
        this.loading = false;
        this.dialogService.alert('Succès', response.message || 'Paramètres enregistrés avec succès !').subscribe();
      },
      error: (err: any) => {
        this.loading = false;
        const message = err?.error?.message || 'Erreur lors de la sauvegarde des paramètres';
        this.dialogService.alert('Erreur', message).subscribe();
      }
    });
  }
}
