import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Role } from './auth.models';
import { AuthService } from './auth.service';

/** Exige sesión; si no hay, envía al login recordando la ruta pedida. */
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated()) {
    return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  }
  // Con contraseña temporal, lo único permitido es cambiarla.
  return auth.user()?.must_change_password ? router.createUrlTree(['/cambiar-clave']) : true;
};

/** Solo exige sesión (para la pantalla de cambio de contraseña obligatorio). */
export const sessionGuard: CanActivateFn = (_route, state) =>
  inject(AuthService).isAuthenticated()
    ? true
    : inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });

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
