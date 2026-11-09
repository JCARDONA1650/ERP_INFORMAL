import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-forbidden',
  imports: [RouterLink],
  template: `
    <h1>Sin permisos</h1>
    <p class="muted">Tu rol no tiene acceso a esta sección.</p>
    <a class="btn btn--ghost" routerLink="/inicio">Volver al inicio</a>
  `,
  styles: `
    h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
    .muted { margin: 0 0 1rem; color: var(--muted); }
  `,
})
export class Forbidden {}
