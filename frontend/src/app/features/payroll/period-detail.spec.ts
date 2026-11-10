import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Role } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { PeriodDetail } from './period-detail';

const LINE = {
  id: 11, employee: { id: 1, full_name: 'Ana Gomez', document_id: null },
  minutes: 420, hours: '07:00', days: 1, hourly_rate: '20.00', currency: 'USD',
  base_amount: '140.00', adjustment: '0.00', notes: '', total: '140.00',
};
const PERIOD = {
  id: 4, start_date: '2026-11-02', end_date: '2026-11-08', project: null, project_name: null,
  status: 'OPEN', created_at: '', closed_at: null, closed_by: null,
  lines: [LINE], totals: { USD: '140.00' },
};

describe('PeriodDetail', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<PeriodDetail>;
  let el: HTMLElement;

  const setup = (roles: Role[], period: object = PERIOD) => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [PeriodDetail],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (TestBed.inject(AuthService) as any)._user.set({ id: 1, username: 'u', full_name: 'U', roles });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(PeriodDetail);
    fixture.componentRef.setInput('id', '4');
    fixture.detectChanges();
    http.expectOne('/api/payroll/periods/4/').flush(period);
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };

  const buttonByText = (text: string) =>
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes(text)) as HTMLButtonElement | undefined;

  afterEach(() => http.verify());

  it('muestra líneas y totales por moneda', () => {
    setup(['RRHH']);
    expect(el.textContent).toContain('Ana Gomez');
    expect(el.textContent).toContain('07:00');
    expect(el.textContent).toContain('Total a pagar (USD)');
  });

  it('RRHH no ve el botón de cerrar; Administrador sí', () => {
    setup(['RRHH']);
    expect(buttonByText('Cerrar periodo')).toBeUndefined();
    TestBed.resetTestingModule();
    setup(['Administrador']);
    expect(buttonByText('Cerrar periodo')).toBeDefined();
  });

  it('recalcula y actualiza la tabla', () => {
    setup(['RRHH']);
    buttonByText('Recalcular')!.click();
    const req = http.expectOne('/api/payroll/periods/4/recalculate/');
    req.flush({ ...PERIOD, lines: [], totals: {} });
    fixture.detectChanges();
    expect(el.textContent).toContain('Sin líneas');
  });

  it('el cierre pide confirmación explícita y no cierra al cancelar', () => {
    setup(['Administrador']);
    buttonByText('Cerrar periodo')!.click();
    fixture.detectChanges();
    expect(el.textContent).toContain('gasto «Nómina» en Finanzas');
    http.expectNone('/api/payroll/periods/4/close/');
    buttonByText('Cancelar')!.click();
    fixture.detectChanges();
    expect(el.querySelector('[role="alertdialog"]')).toBeNull();
  });

  it('cierra tras confirmar y oculta las acciones del periodo cerrado', () => {
    setup(['Administrador']);
    buttonByText('Cerrar periodo')!.click();
    fixture.detectChanges();
    buttonByText('Sí, cerrar')!.click();
    http.expectOne('/api/payroll/periods/4/close/').flush({
      ...PERIOD, status: 'CLOSED', closed_by: 'adm', closed_at: '2026-11-09T12:00:00Z',
    });
    fixture.detectChanges();
    expect(el.textContent).toContain('Cerrado');
    expect(buttonByText('Recalcular')).toBeUndefined();
    expect(buttonByText('Ajustar')).toBeUndefined();
  });

  it('solo el Administrador reabre un periodo cerrado, con confirmación', () => {
    const closed = { ...PERIOD, status: 'CLOSED', closed_by: 'adm', closed_at: '2026-11-09T12:00:00Z' };
    setup(['RRHH'], closed);
    expect(buttonByText('Reabrir')).toBeUndefined();
    TestBed.resetTestingModule();
    setup(['Administrador'], closed);
    buttonByText('Reabrir periodo')!.click();
    fixture.detectChanges();
    http.expectNone('/api/payroll/periods/4/reopen/');
    buttonByText('Sí, reabrir')!.click();
    http.expectOne('/api/payroll/periods/4/reopen/').flush(PERIOD);
    fixture.detectChanges();
    expect(el.textContent).toContain('Abierto');
    expect(buttonByText('Recalcular')).toBeDefined();
  });

  it('ajusta una línea con motivo y recarga el periodo', () => {
    setup(['RRHH']);
    buttonByText('Ajustar')!.click();
    fixture.detectChanges();
    const amount = el.querySelector('input[type="number"]') as HTMLInputElement;
    const reason = el.querySelector('input[type="text"]') as HTMLInputElement;
    amount.value = '-10'; amount.dispatchEvent(new Event('input'));
    reason.value = 'Anticipo'; reason.dispatchEvent(new Event('input'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne('/api/payroll/lines/11/adjust/');
    expect(req.request.body).toEqual({ amount: '-10', reason: 'Anticipo' });
    req.flush({ ...LINE, adjustment: '-10.00', total: '130.00' });
    http.expectOne('/api/payroll/periods/4/').flush({ ...PERIOD, lines: [{ ...LINE, adjustment: '-10.00', total: '130.00', notes: 'Anticipo' }], totals: { USD: '130.00' } });
    fixture.detectChanges();
    expect(el.textContent).toContain('Anticipo');
  });

  it('no envía un ajuste sin motivo', () => {
    setup(['RRHH']);
    buttonByText('Ajustar')!.click();
    fixture.detectChanges();
    const amount = el.querySelector('input[type="number"]') as HTMLInputElement;
    amount.value = '5'; amount.dispatchEvent(new Event('input'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectNone('/api/payroll/lines/11/adjust/');
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('motivo');
  });

  it('muestra el 409 del servidor si el periodo ya estaba cerrado', () => {
    setup(['RRHH']);
    buttonByText('Recalcular')!.click();
    http.expectOne('/api/payroll/periods/4/recalculate/')
      .flush({ detail: 'El periodo está cerrado y no admite cambios.' }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('cerrado');
  });
});
