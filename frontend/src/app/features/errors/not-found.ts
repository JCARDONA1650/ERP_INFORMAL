import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  imports: [RouterLink],
  template: `
    <main class="wrap">
      <h1>Página no encontrada</h1>
      <p class="muted">La dirección no existe o fue movida.</p>
      <a class="btn btn--ghost" routerLink="/">Ir al inicio</a>
    </main>
  `,
  styles: `
    .wrap { min-height: 100dvh; display: grid; place-content: center; justify-items: start; padding: 1.5rem; }
    h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
    .muted { margin: 0 0 1rem; color: var(--muted); }
  `,
})
export class NotFound {}
