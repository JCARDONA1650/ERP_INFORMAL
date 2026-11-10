import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { ManagedUser, UsersService } from '../../core/users/users.service';
import { apiErrorMessage } from '../../core/util/http-error';

const PAGE_SIZE = 25;

interface TempCredential {
  username: string;
  password: string;
}

@Component({
  selector: 'app-users-page',
  imports: [ReactiveFormsModule],
  templateUrl: './users-page.html',
  styleUrl: './users-page.scss',
})
export class UsersPage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(UsersService);

  protected readonly users = signal<ManagedUser[]>([]);
  protected readonly page = signal(1);
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.users().length / PAGE_SIZE)));
  protected readonly pageItems = computed(() => {
    const start = (Math.min(this.page(), this.totalPages()) - 1) * PAGE_SIZE;
    return this.users().slice(start, start + PAGE_SIZE);
  });
  protected readonly roles = signal<string[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly formOpen = signal(false);
  protected readonly editing = signal<ManagedUser | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  /** Contraseña temporal recién generada: se muestra una sola vez. */
  protected readonly credential = signal<TempCredential | null>(null);
  protected readonly copied = signal(false);

  protected readonly form = this.fb.nonNullable.group({
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    role: '',
  });

  ngOnInit(): void {
    this.load();
  }

  protected openNew(): void {
    this.editing.set(null);
    this.formError.set(null);
    this.form.reset({ username: '', first_name: '', last_name: '', email: '', role: this.roles()[0] ?? '' });
    this.form.controls.username.enable();
    this.formOpen.set(true);
  }

  protected edit(u: ManagedUser): void {
    this.editing.set(u);
    this.formError.set(null);
    this.form.reset({
      username: u.username,
      first_name: u.first_name,
      last_name: u.last_name,
      email: u.email,
      role: u.role ?? '',
    });
    this.form.controls.username.disable(); // el usuario no se renombra
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
  }

  protected save(): void {
    if (this.saving()) return;
    const v = this.form.getRawValue();
    const editing = this.editing();
    if (!editing && !v.username.trim()) return this.formError.set('Ingresa el nombre de usuario.');
    if (!v.role) return this.formError.set('Selecciona un rol.');

    this.saving.set(true);
    this.formError.set(null);
    const done = (): void => {
      this.saving.set(false);
      this.closeForm();
      this.load();
    };
    const fail = (err: unknown): void => {
      this.saving.set(false);
      this.formError.set(apiErrorMessage(err));
    };
    if (editing) {
      this.api
        .update(editing.id, { first_name: v.first_name, last_name: v.last_name, email: v.email, role: v.role })
        .subscribe({ next: done, error: fail });
    } else {
      this.api.create({ ...v, username: v.username.trim() }).subscribe({
        next: (res) => {
          this.showCredential(res.username, res.temp_password);
          done();
        },
        error: fail,
      });
    }
  }

  protected toggleActive(u: ManagedUser): void {
    this.api.update(u.id, { is_active: !u.is_active }).subscribe({
      next: () => this.load(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  protected resetPassword(u: ManagedUser): void {
    if (!confirm(`¿Restablecer la contraseña de ${u.username}? Se generará una temporal y tendrá que cambiarla al ingresar.`)) {
      return;
    }
    this.api.resetPassword(u.id).subscribe({
      next: (res) => {
        this.showCredential(u.username, res.temp_password);
        this.load();
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  protected async copyPassword(): Promise<void> {
    const c = this.credential();
    if (!c) return;
    try {
      await navigator.clipboard.writeText(c.password);
      this.copied.set(true);
    } catch {
      this.copied.set(false); // sin permiso de portapapeles: se puede copiar a mano
    }
  }

  protected dismissCredential(): void {
    this.credential.set(null);
    this.copied.set(false);
  }

  private showCredential(username: string, password: string): void {
    this.copied.set(false);
    this.credential.set({ username, password });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.list().subscribe({
      next: (res) => {
        this.users.set(res.results);
        this.roles.set(res.roles);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
