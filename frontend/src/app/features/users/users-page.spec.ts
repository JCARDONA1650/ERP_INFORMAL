import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UsersPage } from './users-page';

const ROW = (over: object = {}) => ({
  id: 2, username: 'sara', first_name: 'Sara', last_name: 'Ruiz', email: '', role: 'Supervisor',
  is_active: true, must_change_password: false, can_manage: true, ...over,
});
const LIST = { roles: ['RRHH', 'Supervisor'], results: [ROW(), ROW({ id: 3, username: 'adm2', role: 'Administrador', can_manage: false })] };

describe('UsersPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<UsersPage>;
  let el: HTMLElement;

  const setup = () => {
    TestBed.configureTestingModule({ imports: [UsersPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(UsersPage);
    fixture.detectChanges();
    http.expectOne('/api/users/').flush(LIST);
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };
  const btn = (text: string) =>
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.trim() === text) as HTMLButtonElement;

  afterEach(() => http.verify());

  it('lista usuarios y solo ofrece acciones sobre los gestionables', () => {
    setup();
    expect(el.querySelectorAll('tbody tr').length).toBe(2);
    expect(el.querySelectorAll('tbody tr')[0].textContent).toContain('Restablecer clave');
    expect(el.querySelectorAll('tbody tr')[1].textContent).not.toContain('Restablecer clave');
  });

  it('crea un usuario con los roles permitidos y muestra la clave temporal una vez', () => {
    setup();
    btn('Nuevo usuario').click();
    fixture.detectChanges();
    const roles = Array.from(el.querySelectorAll('select[formControlName="role"] option')).map((o) => o.textContent?.trim());
    expect(roles).toEqual(['RRHH', 'Supervisor']); // sin Administrador
    const user = el.querySelector('input[formControlName="username"]') as HTMLInputElement;
    user.value = ' nuevo ';
    user.dispatchEvent(new Event('input'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne((r) => r.method === 'POST' && r.url === '/api/users/');
    expect(req.request.body.username).toBe('nuevo');
    expect(req.request.body.role).toBe('RRHH');
    req.flush({ ...ROW({ id: 9, username: 'nuevo', role: 'RRHH' }), temp_password: 'Abc123xyz456' });
    http.expectOne('/api/users/').flush(LIST);
    fixture.detectChanges();
    expect(el.querySelector('.credential')?.textContent).toContain('Abc123xyz456');
    btn('Listo, ya la anoté').click();
    fixture.detectChanges();
    expect(el.querySelector('.credential')).toBeNull();
  });

  it('restablece la clave tras confirmar y muestra la temporal', () => {
    setup();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    btn('Restablecer clave').click();
    http.expectOne('/api/users/2/reset-password/').flush({ temp_password: 'Zz9yy8xx7ww6' });
    http.expectOne('/api/users/').flush(LIST);
    fixture.detectChanges();
    expect(el.querySelector('.credential')?.textContent).toContain('Zz9yy8xx7ww6');
  });

  it('no restablece si se cancela la confirmación', () => {
    setup();
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    btn('Restablecer clave').click();
    http.expectNone((r) => r.url.includes('reset-password'));
  });

  it('cambia el rol con PATCH y muestra el error del servidor', () => {
    setup();
    btn('Editar').click();
    fixture.detectChanges();
    const role = el.querySelector('select[formControlName="role"]') as HTMLSelectElement;
    role.value = 'RRHH';
    role.dispatchEvent(new Event('change'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne('/api/users/2/');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body.role).toBe('RRHH');
    req.flush({ detail: 'No puedes cambiar tu propio rol.' }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();
    expect(el.querySelector('form [role="alert"]')?.textContent).toContain('propio rol');
  });

  it('desactiva un usuario', () => {
    setup();
    btn('Desactivar').click();
    const req = http.expectOne('/api/users/2/');
    expect(req.request.body).toEqual({ is_active: false });
    req.flush(ROW({ is_active: false }));
    http.expectOne('/api/users/').flush(LIST);
  });
});
