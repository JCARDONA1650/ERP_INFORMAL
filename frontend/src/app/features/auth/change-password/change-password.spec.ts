import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';
import { ChangePassword } from './change-password';

describe('ChangePassword', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<ChangePassword>;
  let el: HTMLElement;
  let router: Router;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [ChangePassword],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (TestBed.inject(AuthService) as any)._user.set({ id: 1, username: 'u', full_name: 'U', roles: ['RRHH'], must_change_password: true });
    fixture = TestBed.createComponent(ChangePassword);
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  });

  afterEach(() => http.verify());

  const type = (id: string, value: string) => {
    const input = el.querySelector(`#${id}`) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };
  const submit = () => (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));

  it('con clave temporal explica que es obligatorio y no ofrece cancelar', () => {
    expect(el.textContent).toContain('temporal');
    expect(el.querySelector('a[href="/inicio"]')).toBeNull();
  });

  it('valida longitud y coincidencia antes de enviar', () => {
    type('current', 'tmp'); type('next', 'corta'); type('confirm', 'corta');
    submit(); fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('8 caracteres');
    type('next', 'Nueva-Clave-987'); type('confirm', 'otra-distinta');
    submit(); fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('no coincide');
    http.expectNone((r) => r.url.includes('change-password'));
  });

  it('cambia la clave, libera la sesión y va al inicio', () => {
    const nav = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    type('current', 'tmp'); type('next', 'Nueva-Clave-987'); type('confirm', 'Nueva-Clave-987');
    submit();
    const req = http.expectOne('/api/auth/change-password/');
    expect(req.request.body).toEqual({ current_password: 'tmp', new_password: 'Nueva-Clave-987' });
    req.flush({ detail: 'ok' });
    expect(TestBed.inject(AuthService).user()?.must_change_password).toBe(false);
    expect(nav).toHaveBeenCalledWith('/inicio');
  });

  it('muestra el error del servidor', () => {
    type('current', 'mal'); type('next', 'Nueva-Clave-987'); type('confirm', 'Nueva-Clave-987');
    submit();
    http.expectOne('/api/auth/change-password/').flush({ detail: 'La contraseña actual no es correcta.' }, { status: 400, statusText: 'x' });
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('actual no es correcta');
  });
});
