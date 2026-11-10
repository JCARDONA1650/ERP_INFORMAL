import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';
import { apiErrorMessage } from '../../../core/util/http-error';

import { Logo } from '../../../shared/logo/logo';

@Component({
  selector: 'app-change-password',
  imports: [ReactiveFormsModule, RouterLink, Logo],
  templateUrl: './change-password.html',
  styleUrl: '../login/login.scss',
})
export class ChangePassword {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly forced = () => this.auth.user()?.must_change_password === true;
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.nonNullable.group({
    current: ['', Validators.required],
    next: ['', [Validators.required, Validators.minLength(8)]],
    confirm: ['', Validators.required],
  });

  protected submit(): void {
    if (this.saving()) return;
    const { current, next, confirm } = this.form.getRawValue();
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.error.set('La contraseña nueva debe tener al menos 8 caracteres.');
      return;
    }
    if (next !== confirm) {
      this.error.set('La confirmación no coincide con la contraseña nueva.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    this.auth.changePassword(current, next).subscribe({
      next: () => void this.router.navigateByUrl('/inicio'),
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected logout(): void {
    this.auth.logout();
  }
}
