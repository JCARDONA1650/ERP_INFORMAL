import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

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
export class Privacy {}
