import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Role } from './auth.models';
import { AuthService } from './auth.service';

/** Exige sesión; si no hay, envía al login recordando la ruta pedida. */
export const authGuard: CanActivateFn = (_route, state) => {
  if (inject(AuthService).isAuthenticated()) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

/** Para el login: si ya hay sesión, va al inicio. */
export const guestGuard: CanActivateFn = () =>
  inject(AuthService).isAuthenticated() ? inject(Router).createUrlTree(['/']) : true;

/** Exige alguno de los roles dados (el SuperAdmin siempre pasa). */
export const roleGuard =
  (...roles: Role[]): CanActivateFn =>
  () =>
    inject(AuthService).hasAnyRole(roles) ? true : inject(Router).createUrlTree(['/forbidden']);

/** Solo acepta rutas internas como destino tras el login (evita open redirect). */
export const safeReturnUrl = (url: string | null): string =>
  url && url.startsWith('/') && !url.startsWith('//') ? url : '/';
