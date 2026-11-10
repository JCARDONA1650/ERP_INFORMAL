import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LangSwitch } from '../lang-switch/lang-switch';

@Component({
  selector: 'app-footer',
  imports: [RouterLink, LangSwitch],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <footer class="app-footer">
      <span>© 2026 ERP INFORMAL · Jorge Cardona · Ing. Sistemas</span>
      <a routerLink="/privacidad">Política de datos</a>
      <app-lang-switch />
    </footer>
  `,
  styles: `
    .app-footer {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 0.4rem 1rem;
      padding: 1rem;
      color: var(--muted);
      font-size: 0.8rem;
    }

    a {
      color: var(--muted);
      text-decoration: underline;
    }

    a:hover {
      color: var(--accent);
    }
  `,
})
export class AppFooter {}
