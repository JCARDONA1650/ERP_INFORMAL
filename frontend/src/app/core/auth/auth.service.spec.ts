import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { User } from './auth.models';
import { AuthService } from './auth.service';

const USER: User = { id: 1, username: 'sup', full_name: 'Sara Sup', roles: ['Supervisor'] };

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('login guarda tokens y usuario', () => {
    service.login('sup', 'x').subscribe();
    const req = http.expectOne('/api/auth/login/');
    expect(req.request.body).toEqual({ username: 'sup', password: 'x' });
    req.flush({ access: 'A', refresh: 'R', user: USER });

    expect(service.isAuthenticated()).toBe(true);
    expect(service.accessToken()).toBe('A');
    expect(localStorage.getItem('informal.refresh')).toBe('R');
  });

  it('hasAnyRole respeta roles y el SuperAdmin pasa todo', () => {
    service.login('sup', 'x').subscribe();
    http.expectOne('/api/auth/login/').flush({ access: 'A', refresh: 'R', user: USER });
    expect(service.hasAnyRole(['Supervisor'])).toBe(true);
    expect(service.hasAnyRole(['Administrador'])).toBe(false);

    service.login('root', 'x').subscribe();
    http
      .expectOne('/api/auth/login/')
      .flush({ access: 'A', refresh: 'R', user: { ...USER, roles: ['SuperAdmin'] } });
    expect(service.hasAnyRole(['RRHH'])).toBe(true);
  });

  it('logout limpia la sesión', () => {
    service.login('sup', 'x').subscribe();
    http.expectOne('/api/auth/login/').flush({ access: 'A', refresh: 'R', user: USER });
    service.logout(false);
    expect(service.isAuthenticated()).toBe(false);
    expect(service.accessToken()).toBeNull();
    expect(localStorage.getItem('informal.refresh')).toBeNull();
  });

  it('restoreSession sin refresh token no llama a la API', () => {
    let result: boolean | undefined;
    service.restoreSession().subscribe((r) => (result = r));
    expect(result).toBe(false);
  });

  it('restoreSession renueva el token y carga el usuario', () => {
    localStorage.setItem('informal.refresh', 'R');
    let result: boolean | undefined;
    service.restoreSession().subscribe((r) => (result = r));
    http.expectOne('/api/auth/refresh/').flush({ access: 'A2', refresh: 'R2' });
    http.expectOne('/api/auth/me/').flush(USER);
    expect(result).toBe(true);
    expect(service.user()?.username).toBe('sup');
    expect(localStorage.getItem('informal.refresh')).toBe('R2');
  });

  it('restoreSession con refresh inválido limpia y devuelve false', () => {
    localStorage.setItem('informal.refresh', 'vencido');
    let result: boolean | undefined;
    service.restoreSession().subscribe((r) => (result = r));
    http.expectOne('/api/auth/refresh/').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(result).toBe(false);
    expect(localStorage.getItem('informal.refresh')).toBeNull();
  });

  it('refrescos simultáneos comparten una sola petición', () => {
    localStorage.setItem('informal.refresh', 'R');
    service.refreshAccessToken().subscribe();
    service.refreshAccessToken().subscribe();
    http.expectOne('/api/auth/refresh/').flush({ access: 'A2' });
  });
});
