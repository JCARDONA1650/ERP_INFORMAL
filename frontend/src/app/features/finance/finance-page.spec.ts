import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FinancePage } from './finance-page';

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const SUMMARY = {
  project: { id: 1, name: 'Montego' },
  contract: { value: '1000.00', currency: 'USD', billed_pct: '40.0' },
  incomes: { USD: '400.00' }, expenses: { USD: '150.00' }, balance: { USD: '250.00' },
  expenses_by_category: [{ category: 'materials', currency: 'USD', total: '150.00' }],
};
const INCOME = {
  id: 7, project: 1, date: '2026-11-02', amount: '400.00', currency: 'USD',
  description: 'Anticipo', created_by: 'adm', created_at: '',
};

describe('FinancePage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<FinancePage>;
  let el: HTMLElement;

  const flushLoad = (movements: unknown[] = [INCOME]) => {
    http.expectOne((r) => r.url === '/api/projects/1/finance/').flush(SUMMARY);
    http.expectOne((r) => r.url === '/api/finance/incomes/').flush(page(movements));
    fixture.detectChanges();
  };

  const setup = () => {
    TestBed.configureTestingModule({
      imports: [FinancePage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(FinancePage);
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/projects/').flush(page([{ id: 1, name: 'Montego', slug: 'montego', active: true }]));
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };

  const selectProject = () => {
    const select = el.querySelector('select') as HTMLSelectElement;
    select.selectedIndex = 1;
    select.dispatchEvent(new Event('change'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };
  const btn = (text: string) =>
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes(text)) as HTMLButtonElement;
  const fill = (selector: string, value: string) => {
    const input = el.querySelector(selector) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };

  afterEach(() => http.verify());

  it('sin proyecto elegido pide seleccionarlo y no llama a la API', () => {
    setup();
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('Elige un proyecto');
    http.expectNone((r) => r.url.includes('/finance'));
  });

  it('muestra resumen, balance por moneda y movimientos', () => {
    setup();
    selectProject();
    flushLoad();
    expect(el.textContent).toContain('Facturado: 40.0%');
    expect(el.textContent).toContain('Balance USD');
    expect(el.textContent).toContain('Materiales');
    expect(el.querySelectorAll('tbody tr').length).toBeGreaterThanOrEqual(1);
    expect(el.textContent).toContain('Anticipo');
  });

  it('registra un gasto con categoría y recarga', () => {
    setup();
    selectProject();
    flushLoad();
    btn('Gastos').click();
    http.expectOne((r) => r.url === '/api/finance/expenses/').flush(page([]));
    fixture.detectChanges();
    btn('Nuevo gasto').click();
    fixture.detectChanges();
    fill('.movement-form input[type="number"]', '150');
    fill('.movement-form input[type="text"]', 'Cemento');
    (el.querySelector('.movement-form') as HTMLFormElement).dispatchEvent(new Event('submit'));

    const req = http.expectOne((r) => r.url === '/api/finance/expenses/' && r.method === 'POST');
    expect(req.request.body).toMatchObject({
      project: 1, amount: '150', description: 'Cemento', category: 'other', currency: 'USD',
    });
    req.flush({ ...INCOME, id: 9, category: 'other' });
    http.expectOne((r) => r.url === '/api/projects/1/finance/').flush(SUMMARY);
    http.expectOne((r) => r.url === '/api/finance/expenses/' && r.method === 'GET').flush(page([]));
  });

  it('al editar no envía el proyecto (no se puede mover)', () => {
    setup();
    selectProject();
    flushLoad();
    btn('Editar').click();
    fixture.detectChanges();
    fill('.movement-form input[type="number"]', '450');
    (el.querySelector('.movement-form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne('/api/finance/incomes/7/');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body.project).toBeUndefined();
    expect(req.request.body.amount).toBe('450');
    req.flush({ ...INCOME, amount: '450.00' });
    http.expectOne((r) => r.url === '/api/projects/1/finance/').flush(SUMMARY);
    http.expectOne((r) => r.url === '/api/finance/incomes/' && r.method === 'GET').flush(page([INCOME]));
  });

  it('valida monto y muestra errores del servidor', () => {
    setup();
    selectProject();
    flushLoad();
    btn('Nuevo ingreso').click();
    fixture.detectChanges();
    (el.querySelector('.movement-form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(el.querySelector('.movement-form [role="alert"]')?.textContent).toContain('monto');
    http.expectNone((r) => r.method === 'POST');

    fill('.movement-form input[type="number"]', '5');
    (el.querySelector('.movement-form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectOne((r) => r.method === 'POST')
      .flush({ amount: ['El monto no puede ser negativo.'] }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();
    expect(el.querySelector('.movement-form [role="alert"]')?.textContent).toContain('no puede ser negativo');
  });
});
