import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'login', children: [] }]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  const login = () => {
    auth.login('sup', 'x').subscribe();
    http.expectOne('/api/auth/login/').flush({
      access: 'A',
      refresh: 'R',
      user: { id: 1, username: 'sup', full_name: 'S', roles: ['Supervisor'] },
    });
  };

  it('agrega Bearer a las llamadas de la API', () => {
    login();
    client.get('/api/projects/').subscribe();
    expect(http.expectOne('/api/projects/').request.headers.get('Authorization')).toBe('Bearer A');
  });

  it('no agrega Bearer al login ni a otros orígenes', () => {
    login();
    client.get('https://otro.com/x').subscribe();
    expect(http.expectOne('https://otro.com/x').request.headers.has('Authorization')).toBe(false);
  });

  it('ante 401 renueva el token y reintenta una vez', () => {
    login();
    let body: unknown;
    client.get('/api/projects/').subscribe((b) => (body = b));
    http.expectOne('/api/projects/').flush({}, { status: 401, statusText: 'Unauthorized' });
    http.expectOne('/api/auth/refresh/').flush({ access: 'A2' });
    const retry = http.expectOne('/api/projects/');
    expect(retry.request.headers.get('Authorization')).toBe('Bearer A2');
    retry.flush({ ok: true });
    expect(body).toEqual({ ok: true });
  });

  it('si el refresh falla cierra la sesión', () => {
    login();
    let failed = false;
    client.get('/api/projects/').subscribe({ error: () => (failed = true) });
    http.expectOne('/api/projects/').flush({}, { status: 401, statusText: 'Unauthorized' });
    http.expectOne('/api/auth/refresh/').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(failed).toBe(true);
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('otros errores pasan sin renovar', () => {
    login();
    let status = 0;
    client.get('/api/projects/').subscribe({ error: (e) => (status = e.status) });
    http.expectOne('/api/projects/').flush({}, { status: 403, statusText: 'Forbidden' });
    expect(status).toBe(403);
  });
});
