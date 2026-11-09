import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { Login } from './login';

describe('Login', () => {
  let http: HttpTestingController;

  const setup = () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(Login);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const fill = (user: string, pass: string) => {
      (el.querySelector('#username') as HTMLInputElement).value = user;
      (el.querySelector('#username') as HTMLInputElement).dispatchEvent(new Event('input'));
      (el.querySelector('#password') as HTMLInputElement).value = pass;
      (el.querySelector('#password') as HTMLInputElement).dispatchEvent(new Event('input'));
    };
    const submit = async () => {
      (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
      fixture.detectChanges();
      await fixture.whenStable();
    };
    return { fixture, el, fill, submit };
  };

  afterEach(() => http.verify());

  it('no envía si el formulario está vacío y muestra avisos', async () => {
    const { fixture, el, submit } = setup();
    await submit();
    fixture.detectChanges();
    http.expectNone('/api/auth/login/');
    expect(el.textContent).toContain('Ingresa tu usuario.');
  });

  it('muestra mensaje genérico ante credenciales inválidas', async () => {
    const { fixture, el, fill, submit } = setup();
    fill('sup', 'mala');
    await submit();
    http.expectOne('/api/auth/login/').flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('Usuario o contraseña inválidos.');
  });

  it('informa cuando se superó el límite de intentos', async () => {
    const { fixture, el, fill, submit } = setup();
    fill('sup', 'mala');
    await submit();
    http.expectOne('/api/auth/login/').flush({}, { status: 429, statusText: 'Too Many Requests' });
    fixture.detectChanges();
    expect(el.textContent).toContain('Demasiados intentos');
  });

  it('con credenciales correctas navega a la ruta segura', async () => {
    const { fill, submit } = setup();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    fill('sup', 'ok');
    await submit();
    http.expectOne('/api/auth/login/').flush({
      access: 'A',
      refresh: 'R',
      user: { id: 1, username: 'sup', full_name: 'S', roles: ['Supervisor'] },
    });
    expect(navigate).toHaveBeenCalledWith('/');
  });
});
