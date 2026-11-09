import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Employee } from '../../core/employees/employees.service';
import { EmployeesPage } from './employees-page';

const ANA: Employee = {
  id: 3, document_id: 'A-1', full_name: 'Ana Gomez', position: 'Oficial', pay_type: 'hourly',
  hourly_rate: '20.00', daily_rate: '0.00', currency: 'USD', active: true,
};
const page = (results: Employee[]) => ({ count: results.length, next: null, previous: null, results });

describe('EmployeesPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<EmployeesPage>;
  let el: HTMLElement;

  const listReq = () => http.expectOne((r) => r.url === '/api/employees/' && r.method === 'GET');
  const setup = () => {
    TestBed.configureTestingModule({
      imports: [EmployeesPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(EmployeesPage);
    fixture.detectChanges();
    listReq().flush(page([ANA]));
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };
  const btn = (text: string) =>
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.trim() === text) as HTMLButtonElement;
  const fill = (selector: string, value: string) => {
    const input = el.querySelector(selector) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };
  const submitForm = (selector: string) =>
    (el.querySelector(selector) as HTMLFormElement).dispatchEvent(new Event('submit'));

  afterEach(() => http.verify());

  it('lista trabajadores con tarifa vigente y estado', () => {
    setup();
    expect(el.textContent).toContain('Ana Gomez');
    expect(el.textContent).toContain('USD');
    expect(el.textContent).toContain('Activo');
  });

  it('crea un trabajador por hora con tarifa inicial', () => {
    setup();
    btn('Nuevo trabajador').click();
    fixture.detectChanges();
    fill('.employee-form input[formControlName="full_name"]', '  Carlos Diaz ');
    fill('.employee-form input[formControlName="initial_rate"]', '25.5');
    submitForm('.employee-form');
    const req = http.expectOne((r) => r.method === 'POST');
    expect(req.request.body).toMatchObject({
      full_name: 'Carlos Diaz', document_id: null, pay_type: 'hourly', currency: 'USD', initial_rate: '25.5',
    });
    expect(req.request.body.confirm_duplicate).toBeUndefined();
    req.flush({ ...ANA, id: 9, full_name: 'Carlos Diaz' });
    listReq().flush(page([ANA]));
  });

  it('nombre repetido: muestra coincidencias y solo crea tras confirmar', () => {
    setup();
    btn('Nuevo trabajador').click();
    fixture.detectChanges();
    fill('.employee-form input[formControlName="full_name"]', 'Ana Gomez');
    submitForm('.employee-form');
    http.expectOne((r) => r.method === 'POST').flush(
      { detail: 'Ya existe', similar: [{ id: 3, full_name: 'Ana Gomez', document_id: 'A-1' }] },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();
    expect(el.querySelector('[role="alertdialog"]')?.textContent).toContain('A-1');

    btn('Es otra persona, crear de todos modos').click();
    const retry = http.expectOne((r) => r.method === 'POST');
    expect(retry.request.body.confirm_duplicate).toBe(true);
    retry.flush({ ...ANA, id: 10 });
    listReq().flush(page([ANA]));
  });

  it('edita sin enviar tarifa inicial y exige nombre', () => {
    setup();
    btn('Editar').click();
    fixture.detectChanges();
    fill('.employee-form input[formControlName="full_name"]', '');
    submitForm('.employee-form');
    fixture.detectChanges();
    http.expectNone((r) => r.method === 'PATCH');
    expect(el.querySelector('.employee-form [role="alert"]')?.textContent).toContain('nombre');

    fill('.employee-form input[formControlName="full_name"]', 'Ana G. Gomez');
    submitForm('.employee-form');
    const req = http.expectOne('/api/employees/3/');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body.initial_rate).toBeUndefined();
    req.flush({ ...ANA, full_name: 'Ana G. Gomez' });
    listReq().flush(page([ANA]));
  });

  it('desactiva y refleja el estado sin recargar', () => {
    setup();
    btn('Desactivar').click();
    http.expectOne('/api/employees/3/deactivate/').flush({ ...ANA, active: false });
    fixture.detectChanges();
    expect(el.textContent).toContain('Inactivo');
    expect(btn('Activar')).toBeDefined();
  });

  it('muestra el historial y agrega una tarifa con vigencia', () => {
    setup();
    btn('Tarifas').click();
    http.expectOne('/api/employees/3/rates/').flush([{ id: 1, rate: '20.00', effective_from: '2026-01-01', created_at: '' }]);
    fixture.detectChanges();
    expect(el.querySelector('[aria-label="Tarifas"]')?.textContent).toContain('01/01/2026');

    fill('.rate-form input[formControlName="rate"]', '30');
    fill('.rate-form input[formControlName="effective_from"]', '2026-11-05');
    submitForm('.rate-form');
    const req = http.expectOne((r) => r.method === 'POST');
    expect(req.request.body).toEqual({ rate: '30', effective_from: '2026-11-05' });
    req.flush({ id: 2, rate: '30.00', effective_from: '2026-11-05', created_at: '' });
    http.expectOne((r) => r.method === 'GET' && r.url === '/api/employees/3/rates/').flush([]);
    listReq().flush(page([{ ...ANA, hourly_rate: '30.00' }]));
  });

  it('no envía una tarifa inválida', () => {
    setup();
    btn('Tarifas').click();
    http.expectOne('/api/employees/3/rates/').flush([]);
    fixture.detectChanges();
    submitForm('.rate-form');
    fixture.detectChanges();
    http.expectNone((r) => r.method === 'POST');
    expect(el.querySelector('[aria-label="Tarifas"] [role="alert"]')?.textContent).toContain('tarifa');
  });
});
