import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, MatIconModule, MatTooltipModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent implements OnInit {
  // Définition du formulaire réactif pour la connexion
  loginForm!: FormGroup;
  loading = false;
  errorMessage = '';
  showPassword = false;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private themeService: ThemeService,
    private router: Router
  ) {}

  /**
   * Bascule le thème de l'application (Mode Sombre / Mode Clair)
   */
  toggleTheme(): void {
    this.themeService.toggleTheme();
  }

  /**
   * Vérifie si le thème actuel est le mode sombre
   */
  isDark(): boolean {
    return this.themeService.isDark();
  }

  ngOnInit(): void {
    // Si l'utilisateur est déjà authentifié, redirection directe vers le dashboard
    if (this.authService.isLoggedIn()) {
      this.router.navigate(['/dashboard']);
    }

    this.initForm();
  }

  /**
   * Initialise les validateurs du formulaire de connexion
   */
  private initForm(): void {
    this.loginForm = this.fb.group({
      username: ['', [Validators.required]],
      password: ['', [Validators.required, Validators.minLength(4)]]
    });
  }

  /**
   * Gère la soumission du formulaire et l'appel à l'API d'authentification Flask
   */
  onSubmit(): void {
    if (this.loginForm.invalid) {
      return;
    }

    this.loading = true;
    this.errorMessage = '';

    const { username, password } = this.loginForm.value;

    // Appel au service d'authentification réel via HTTP
    this.authService.login({ username, password }).subscribe({
      next: (res) => {
        this.loading = false;
        if (res.status === 'success') {
          // Redirection vers le centre de commande SOC après succès
          this.router.navigate(['/dashboard']);
        } else {
          this.errorMessage = res.message || 'Identifiants incorrects';
        }
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.error?.message || 'Erreur de connexion. Veuillez vérifier vos identifiants.';
        console.error('Login error:', err);
      }
    });
  }

  /**
   * Affiche ou masque le mot de passe dans le champ de saisie
   */
  togglePassword(): void {
    this.showPassword = !this.showPassword;
  }
}
