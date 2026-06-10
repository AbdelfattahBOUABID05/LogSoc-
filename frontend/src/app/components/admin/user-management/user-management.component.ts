import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';
import { CommonDialogService } from '../../../services/common-dialog.service';
import { MatIconModule } from '@angular/material/icon';

interface User {
  id?: number;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  password?: string;
  created_at?: string;
}

@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  templateUrl: './user-management.component.html',
  styleUrls: ['./user-management.component.css']
})
export class UserManagementComponent implements OnInit {
  users: User[] = [];
  showModal = false;
  editingUser: User | null = null;
  userForm: User = { username: '', email: '', firstName: '', lastName: '', role: 'Analyseur', password: '' };
  private apiUrl = environment.apiUrl;

  constructor(
    private http: HttpClient,
    private dialogService: CommonDialogService
  ) {}

  ngOnInit(): void {
    this.fetchUsers();
  }

  fetchUsers(): void {
    this.http.get<{ status: string; users: User[] }>(`${this.apiUrl}/admin/users`).subscribe({
      next: (res: any) => this.users = res.users,
      error: (err: any) => console.error('Error fetching users:', err)
    });
  }

  openCreateModal(): void {
    this.editingUser = null;
    this.userForm = { username: '', email: '', firstName: '', lastName: '', role: 'Analyseur', password: '' };
    this.showModal = true;
  }

  openEditModal(user: User): void {
    this.editingUser = { ...user };
    this.userForm = { ...user };
    this.showModal = true;
  }

  closeModal(): void {
    this.showModal = false;
  }

  saveUser(): void {
    if (this.editingUser?.id) {
      // Update
      this.http.put(`${this.apiUrl}/admin/users/${this.editingUser.id}`, this.userForm).subscribe({
        next: () => {
          this.fetchUsers();
          this.closeModal();
          this.dialogService.alert('Succès', 'Utilisateur mis à jour avec succès').subscribe();
        },
        error: (err: any) => this.dialogService.alert('Erreur', err.error?.message || 'Erreur lors de la mise à jour').subscribe()
      });
    } else {
      // Create
      this.http.post(`${this.apiUrl}/admin/users`, this.userForm).subscribe({
        next: () => {
          this.fetchUsers();
          this.closeModal();
          this.dialogService.alert('Succès', 'Utilisateur créé avec succès').subscribe();
        },
        error: (err: any) => this.dialogService.alert('Erreur', err.error?.message || 'Erreur lors de la création').subscribe()
      });
    }
  }

  deleteUser(user: User): void {
    this.dialogService.confirm(
      'Suppression',
      `Êtes-vous sûr de vouloir supprimer l'utilisateur ${user.username} ?`
    ).subscribe((confirmed: boolean | null) => {
      if (confirmed) {
        this.http.delete(`${this.apiUrl}/admin/users/${user.id}`).subscribe({
          next: () => {
            this.fetchUsers();
            this.dialogService.alert('Succès', 'Utilisateur supprimé avec succès').subscribe();
          },
          error: (err: any) => this.dialogService.alert('Erreur', err.error?.message || 'Erreur lors de la suppression').subscribe()
        });
      }
    });
  }

  resetPassword(user: User): void {
    this.dialogService.confirm(
      'Réinitialisation',
      `Voulez-vous réinitialiser le mot de passe de ${user.username} ? Le nouveau mot de passe sera 'Admin123*'.`
    ).subscribe((confirmed: boolean | null) => {
      if (confirmed) {
        this.http.post(`${this.apiUrl}/admin/users/${user.id}/reset-password`, {}).subscribe({
          next: () => this.dialogService.alert('Succès', 'Mot de passe réinitialisé').subscribe(),
          error: (err: any) => this.dialogService.alert('Erreur', err.error?.message || 'Erreur lors de la réinitialisation').subscribe()
        });
      }
    });
  }
}