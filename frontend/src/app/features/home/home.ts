import { Component, inject } from '@angular/core';

import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-home',
  template: `
    <h1>Hola, {{ user()?.full_name }}</h1>
    <p class="muted">Bienvenido a INFORMAL ERP. Las secciones se irán habilitando según tu rol.</p>
  `,
  styles: `
    h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
    .muted { margin: 0; color: var(--muted); }
  `,
})
export class Home {
  protected readonly user = inject(AuthService).user;
}
