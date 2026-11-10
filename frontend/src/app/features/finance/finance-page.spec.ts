import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FinanceOverview } from '../../core/finance/finance.service';
import { FinancePage } from './finance-page';

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const ROW = {
  project: { id: 1, name: 'Montego', active: true },
  contract: { value: '1000.00', currency: 'USD', billed_pct: '40.0' },
  incomes: { USD: '400.00' }, expenses: { USD: '150.00' }, balance: { USD: '250.00' },
};
const POINTS = [
  { period: '2026-11-02', income: '400.00', expense: '100.00', net: '300.00', cumulative: '300.00' },
  { period: '2026-11-03', income: '0.00', expense: '0.00', net: '0.00', cumulative: '300.00' },
  { period: '2026-11-04', income: '0.00', expense: '50.00', net: '-50.00', cumulative: '250.00' },
];
const GLOBAL: FinanceOverview = {
  scope: null,
  currencies: ['USD'],
  totals: { incomes: { USD: '400.00' }, expenses: { USD: '150.00' }, balance: { USD: '250.00' } },
  projects: [ROW, { ...ROW, project: { id: 2, name: 'Beta', active: true }, incomes: {}, expenses: {}, balance: {} }],
  expenses_by_category: [{ category: 'materials', currency: 'USD', total: '150.00' }],
  series: { currency: 'USD', group: 'day', points: POINTS },
};
const ONE: FinanceOverview = { ...GLOBAL, scope: { id: 1, name: 'Montego' }, projects: [ROW] };
const INCOME = {
  id: 7, project: 1, date: '2026-11-02', amount: '400.00', currency: 'USD',
  description: 'Anticipo', created_by: 'adm', created_at: '',
};

describe('FinancePage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<FinancePage>;
  let el: HTMLElement;

  const overviewReq = () => http.expectOne((r) => r.url === '/api/finance/overview/');
  const listReq = (kind = 'incomes') => http.expectOne((r) => r.url === `/api/finance/${kind}/` && r.method === 'GET');
  const flushLoad = (ov: FinanceOverview = GLOBAL, movements: unknown[] = [INCOME], kind = 'incomes') => {
    overviewReq().flush(ov);
    listReq(kind).flush(page(movements));
    fixture.detectChanges();
  };

  /** Carga inicial: proyectos + registro global. */
  const setup = () => {
    TestBed.configureTestingModule({
      imports: [FinancePage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(FinancePage);
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/projects/').flush(
      page([{ id: 1, name: 'Montego', slug: 'montego', active: true }, { id: 2, name: 'Beta', slug: 'beta', active: true }]),
    );
    el = fixture.nativeElement as HTMLElement;
  };

  const btn = (text: string) =>
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.trim().includes(text)) as HTMLButtonElement;
  const fill = (selector: string, value: string) => {
    const input = el.querySelector(selector) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };
  const submitMovement = () =>
    (el.querySelector('.movement-form') as HTMLFormElement).dispatchEvent(new Event('submit'));

  afterEach(() => http.verify());

  it('al abrir muestra el registro global de todos los proyectos', () => {
    setup();
    const req = overviewReq();
    expect(req.request.params.has('project')).toBe(false);
    req.flush(GLOBAL);
    listReq().flush(page([INCOME]));
    fixture.detectChanges();

    expect(el.textContent).toContain('Todos los proyectos');
    expect(el.textContent).toContain('Balance USD');
    expect(el.textContent).toContain('Beta'); // detalle por proyecto
    expect(el.textContent).toContain('Materiales');
    expect(el.querySelector('app-finance-chart svg')).not.toBeNull();
    expect(el.textContent).toContain('Anticipo');
  });

  it('en el registro global la lista muestra la columna Proyecto', () => {
    setup();
    flushLoad();
    const headers = Array.from(el.querySelectorAll('thead th')).map((h) => h.textContent?.trim());
    expect(headers).toContain('Proyecto');
  });

  it('elegir un proyecto filtra resumen y movimientos y muestra el contrato', () => {
    setup();
    flushLoad();
    const select = el.querySelector('select') as HTMLSelectElement;
    select.selectedIndex = 1; // Montego
    select.dispatchEvent(new Event('change'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const ov = overviewReq();
    expect(ov.request.params.get('project')).toBe('1');
    ov.flush(ONE);
    expect(listReq().request.params.get('project')).toBe('1');
    http.verify();
    fixture.detectChanges();
    expect(el.textContent).toContain('Facturado: 40.0%');
    const headers = Array.from(el.querySelectorAll('thead th')).map((h) => h.textContent?.trim());
    expect(headers).not.toContain('Contrato'); // sin tabla por proyecto
  });

  it('cambia la agrupación de la gráfica (día, semana, mes)', () => {
    setup();
    flushLoad();
    btn('Semana').click();
    const req = overviewReq();
    expect(req.request.params.get('group')).toBe('week');
    req.flush({ ...GLOBAL, series: { ...GLOBAL.series, group: 'week' } });
    fixture.detectChanges();
    expect(btn('Semana').getAttribute('aria-pressed')).toBe('true');
  });

  it('con dos monedas permite elegir la de la gráfica', () => {
    setup();
    flushLoad({ ...GLOBAL, currencies: ['COP', 'USD'] });
    const select = el.querySelector('.chart-currency select') as HTMLSelectElement;
    select.value = 'COP';
    select.dispatchEvent(new Event('change'));
    expect(overviewReq().request.params.get('currency')).toBe('COP');
  });

  it('registra un gasto en un proyecto elegido y recarga', () => {
    setup();
    flushLoad();
    btn('Gastos').click();
    listReq('expenses').flush(page([]));
    fixture.detectChanges();
    btn('Nuevo gasto').click();
    fixture.detectChanges();

    // En el registro global el formulario pide el proyecto.
    fill('.movement-form input[type="number"]', '150');
    fill('.movement-form input[type="text"]', 'Cemento');
    submitMovement();
    fixture.detectChanges();
    expect(el.querySelector('.movement-form [role="alert"]')?.textContent).toContain('Elige un proyecto');
    http.expectNone((r) => r.method === 'POST');

    const projectSelect = el.querySelector('.movement-form select') as HTMLSelectElement;
    projectSelect.selectedIndex = 1; // Montego
    projectSelect.dispatchEvent(new Event('change'));
    submitMovement();
    const req = http.expectOne((r) => r.url === '/api/finance/expenses/' && r.method === 'POST');
    expect(req.request.body).toMatchObject({
      project: 1, amount: '150', description: 'Cemento', category: 'other', currency: 'USD',
    });
    req.flush({ ...INCOME, id: 9, category: 'other' });
    overviewReq().flush(GLOBAL);
    listReq('expenses').flush(page([]));
  });

  it('al editar no envía el proyecto (no se puede mover)', () => {
    setup();
    flushLoad();
    btn('Editar').click();
    fixture.detectChanges();
    expect(el.querySelector('.movement-form select[formControlName="project"]')).toBeNull();
    fill('.movement-form input[type="number"]', '450');
    submitMovement();
    const req = http.expectOne('/api/finance/incomes/7/');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body.project).toBeUndefined();
    expect(req.request.body.amount).toBe('450');
    req.flush({ ...INCOME, amount: '450.00' });
    overviewReq().flush(GLOBAL);
    listReq().flush(page([INCOME]));
  });

  it('valida monto y muestra errores del servidor', () => {
    setup();
    flushLoad(ONE);
    // Con un proyecto elegido no hace falta indicarlo en el formulario.
    const select = el.querySelector('select') as HTMLSelectElement;
    select.selectedIndex = 1;
    select.dispatchEvent(new Event('change'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    overviewReq().flush(ONE);
    listReq().flush(page([INCOME]));
    fixture.detectChanges();

    btn('Nuevo ingreso').click();
    fixture.detectChanges();
    submitMovement();
    fixture.detectChanges();
    expect(el.querySelector('.movement-form [role="alert"]')?.textContent).toContain('monto');
    http.expectNone((r) => r.method === 'POST');

    fill('.movement-form input[type="number"]', '5');
    submitMovement();
    http.expectOne((r) => r.method === 'POST')
      .flush({ amount: ['El monto no puede ser negativo.'] }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();
    expect(el.querySelector('.movement-form [role="alert"]')?.textContent).toContain('no puede ser negativo');
  });
});
