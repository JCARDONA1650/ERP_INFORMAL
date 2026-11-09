import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';

import { authGuard, guestGuard, roleGuard, safeReturnUrl } from './auth.guards';
import { AuthService } from './auth.service';

const state = (url: string) => ({ url }) as RouterStateSnapshot;
const route = {} as ActivatedRouteSnapshot;

describe('guards', () => {
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  const setUser = (roles: string[]) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (auth as any)._user.set({ id: 1, username: 'u', full_name: 'U', roles });

  const run = (guard: ReturnType<typeof roleGuard>, url = '/x') =>
    TestBed.runInInjectionContext(() => guard(route, state(url)));

  it('authGuard envía al login con returnUrl si no hay sesión', () => {
    const result = run(authGuard, '/proyectos') as UrlTree;
    expect(router.serializeUrl(result)).toBe('/login?returnUrl=%2Fproyectos');
  });

  it('authGuard deja pasar con sesión', () => {
    setUser(['Supervisor']);
    expect(run(authGuard)).toBe(true);
  });

  it('guestGuard redirige al inicio si ya hay sesión', () => {
    expect(run(guestGuard)).toBe(true);
    setUser(['Supervisor']);
    expect(router.serializeUrl(run(guestGuard) as UrlTree)).toBe('/');
  });

  it('roleGuard permite el rol, bloquea otros y deja pasar al SuperAdmin', () => {
    setUser(['Supervisor']);
    expect(run(roleGuard('Supervisor'))).toBe(true);
    expect(router.serializeUrl(run(roleGuard('Administrador')) as UrlTree)).toBe('/forbidden');
    setUser(['SuperAdmin']);
    expect(run(roleGuard('RRHH'))).toBe(true);
  });

  it('safeReturnUrl solo acepta rutas internas', () => {
    expect(safeReturnUrl('/proyectos')).toBe('/proyectos');
    expect(safeReturnUrl('//malo.com')).toBe('/');
    expect(safeReturnUrl('https://malo.com')).toBe('/');
    expect(safeReturnUrl(null)).toBe('/');
  });
});
