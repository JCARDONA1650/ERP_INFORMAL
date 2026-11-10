import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { AppFooter } from '../../shared/footer/app-footer';
import { Logo } from '../../shared/logo/logo';
import { NAV_ITEMS } from './nav';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Logo, AppFooter],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell {
  private readonly auth = inject(AuthService);

  protected readonly user = this.auth.user;
  protected readonly items = computed(() =>
    NAV_ITEMS.filter((item) => item.roles.length === 0 || this.auth.hasAnyRole(item.roles)),
  );

  protected logout(): void {
    this.auth.logout();
  }
}
