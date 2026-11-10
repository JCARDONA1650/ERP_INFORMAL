import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Logo de ERP INFORMAL: pin de ubicación con visto (obra + marcación validada) y su zona. */
@Component({
  selector: 'app-logo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      role="img"
      aria-label="ERP INFORMAL"
      [attr.width]="size()"
      [attr.height]="size()"
    >
      <rect width="64" height="64" rx="14" fill="#0b0f14" />
      <rect x="1.5" y="1.5" width="61" height="61" rx="12.5" fill="none" stroke="#c9a84c" stroke-opacity=".45" stroke-width="3" />
      <ellipse cx="32" cy="55" rx="17" ry="4.2" fill="none" stroke="#c9a84c" stroke-opacity=".6" stroke-width="2.5" />
      <path d="M32 8c-9.4 0-17 7.4-17 16.5C15 37 32 53 32 53s17-16 17-28.5C49 15.4 41.4 8 32 8z" fill="#c9a84c" />
      <path d="M24 24.5l5.7 5.7L40.5 19" fill="none" stroke="#0b0f14" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `,
  styles: `
    :host {
      display: inline-flex;
      line-height: 0;
    }
  `,
})
export class Logo {
  readonly size = input(40);
}
