import { Component, inject } from '@angular/core';

import { I18n, Lang } from '../../core/i18n/i18n.service';

/** Selector de idioma ES | EN. Los rótulos no se traducen (son los nombres de cada idioma). */
@Component({
  selector: 'app-lang-switch',
  template: `
    <div class="lang" role="group" aria-label="Idioma / Language">
      @for (l of langs; track l.code) {
        <button
          type="button"
          class="lang__btn"
          [class.is-active]="i18n.lang() === l.code"
          [attr.aria-pressed]="i18n.lang() === l.code"
          [attr.lang]="l.code"
          [attr.title]="l.name"
          (click)="i18n.set(l.code)"
        >
          {{ l.code.toUpperCase() }}
        </button>
      }
    </div>
  `,
  styles: `
    .lang {
      display: inline-flex;
      border: 1px solid var(--border);
      border-radius: 999px;
      overflow: hidden;
    }
    .lang__btn {
      min-width: 2.4rem;
      padding: 0.3rem 0.7rem;
      background: transparent;
      color: var(--muted);
      border: 0;
      font: inherit;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
    }
    .lang__btn.is-active {
      background: var(--accent);
      color: #111;
    }
    .lang__btn:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: -2px;
    }
  `,
})
export class LangSwitch {
  protected readonly i18n = inject(I18n);
  protected readonly langs: { code: Lang; name: string }[] = [
    { code: 'es', name: 'Español' },
    { code: 'en', name: 'English' },
  ];
}
