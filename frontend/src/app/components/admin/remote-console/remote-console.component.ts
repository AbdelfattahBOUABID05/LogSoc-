import { Component, OnInit, signal, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatIconModule } from '@angular/material/icon';
import { SidebarComponent } from '../../sidebar/sidebar.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-remote-console',
  standalone: true,
  imports: [CommonModule, FormsModule, SidebarComponent, MatIconModule],
  templateUrl: './remote-console.component.html',
  styleUrls: ['./remote-console.component.css']
})
export class RemoteConsoleComponent implements OnInit {
  @ViewChild('terminalBody') private terminalBody!: ElementRef;
  @ViewChild('cmdInput') private cmdInput!: ElementRef;

  public currentConnection: any = null;
  public ssh = signal({ host: '', username: '', password: '' });
  public commandInput = '';
  public history = signal<{ command: string; output: string }[]>([]);
  public isExecuting = signal<boolean>(false);
  public recentConnections = signal<any[]>([]);
  
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadRecent();
  }

  loadRecent(): void {
    this.http.get<any>(`${this.apiUrl}/admin/console/recent`).subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.recentConnections.set(res.connections);
          if (res.connections.length > 0 && !this.currentConnection) {
            this.fillForm(res.connections[0]);
          }
        }
      },
      error: (err) => console.error('Erreur chargement connexions admin:', err)
    });
  }

  fillForm(conn: any): void {
    this.currentConnection = conn;
    this.ssh.set({
      host: conn.host,
      username: conn.username,
      password: conn.password
    });
    // On focus l'input après un petit délai
    setTimeout(() => this.cmdInput?.nativeElement.focus(), 100);
  }

  clearConsole(): void {
    this.history.set([]);
  }

  sendCommand(): void {
    if (!this.commandInput.trim()) return;

    // Synchronisation des Signals : Récupération des données du formulaire
    const credentials = this.ssh();
    const host = credentials.host;
    const username = credentials.username;
    const password = credentials.password;

    if (!host || !username) return;

    const cmd = this.commandInput;
    this.commandInput = '';
    this.isExecuting.set(true);

    const payload = {
      host: host,
      username: username,
      password: password,
      command: cmd
    };

    console.log('JSON envoyé au Flask:', JSON.stringify(payload));

    this.http.post<any>(`${this.apiUrl}/admin/console`, payload).subscribe({
      next: (res) => {
        const newEntry = {
          command: cmd,
          output: res.output || res.error || 'Commande exécutée sans retour.'
        };
        this.history.set([...this.history(), newEntry]);
        this.isExecuting.set(false);
        this.scrollToBottom();
      },
      error: (err) => {
        const newEntry = {
          command: cmd,
          output: `ERREUR : ${err.error?.message || 'Échec de la connexion SSH'}`
        };
        this.history.set([...this.history(), newEntry]);
        this.isExecuting.set(false);
        this.scrollToBottom();
      }
    });
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      try {
        this.terminalBody.nativeElement.scrollTop = this.terminalBody.nativeElement.scrollHeight;
      } catch (err) {}
    }, 100);
  }
}
