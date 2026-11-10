import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { I18n } from '../../core/i18n/i18n.service';
import { AppFooter } from '../../shared/footer/app-footer';
import { Logo } from '../../shared/logo/logo';

/** Política de tratamiento de datos (pública: la lee el trabajador antes de marcar). */
@Component({
  selector: 'app-privacy',
  imports: [RouterLink, AppFooter, Logo],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './privacy.html',
  styleUrl: './privacy.scss',
})
export class Privacy {
  private readonly i18n = inject(I18n);
  protected readonly en = computed(() => this.i18n.lang() === 'en');
}
