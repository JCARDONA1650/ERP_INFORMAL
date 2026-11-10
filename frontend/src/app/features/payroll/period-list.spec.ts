import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { PeriodList } from './period-list';

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const PERIOD = {
  id: 4, start_date: '2026-11-02', end_date: '2026-11-08', project: null, project_name: null,
  status: 'OPEN', created_at: '', closed_at: null, closed_by: null,
};

describe('PeriodList', () => {
  let http: HttpTestingController;

  const setup = () => {
    TestBed.configureTestingModule({
      imports: [PeriodList],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(PeriodList);
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/projects/').flush(page([]));
    http.expectOne((r) => r.url === '/api/payroll/periods/').flush(page([PERIOD]));
    fixture.detectChanges();
    return { fixture, el: fixture.nativeElement as HTMLElement };
  };

  afterEach(() => http.verify());

  it('lista los periodos con su estado', () => {
    const { el } = setup();
    expect(el.querySelectorAll('tbody tr').length).toBe(1);
    expect(el.textContent).toContain('Abierto');
    expect(el.textContent).toContain('Todos');
  });

  it('filtrar por mes pide los periodos de ese mes desde la primera página', () => {
    const { fixture, el } = setup();
    const month = el.querySelector('input[type="month"]') as HTMLInputElement;
    month.value = '2026-11'; month.dispatchEvent(new Event('input')); month.dispatchEvent(new Event('change'));
    const req = http.expectOne((r) => r.url === '/api/payroll/periods/');
    expect(req.request.params.get('month')).toBe('2026-11');
    expect(req.request.params.has('page')).toBe(false);
    req.flush(page([PERIOD]));
    fixture.detectChanges();
  });

  it('exige ambas fechas antes de crear', () => {
    const { fixture, el } = setup();
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    http.expectNone((r) => r.method === 'POST');
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('fecha');
  });

  it('crea el periodo y navega a su detalle', () => {
    const { fixture, el } = setup();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const [from, to] = Array.from(el.querySelectorAll('input[type="date"]')) as HTMLInputElement[];
    from.value = '2026-11-09'; from.dispatchEvent(new Event('input'));
    to.value = '2026-11-15'; to.dispatchEvent(new Event('input'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne((r) => r.method === 'POST');
    expect(req.request.body).toEqual({ start_date: '2026-11-09', end_date: '2026-11-15', project: null });
    req.flush({ ...PERIOD, id: 8 });
    fixture.detectChanges();
    expect(navigate).toHaveBeenCalledWith(['/nomina', 8]);
  });

  it('muestra el error del servidor al duplicar un periodo', () => {
    const { fixture, el } = setup();
    const [from, to] = Array.from(el.querySelectorAll('input[type="date"]')) as HTMLInputElement[];
    from.value = '2026-11-02'; from.dispatchEvent(new Event('input'));
    to.value = '2026-11-08'; to.dispatchEvent(new Event('input'));
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectOne((r) => r.method === 'POST')
      .flush({ __all__: ['Ya existe un periodo para ese rango.'] }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();
    expect(el.textContent).toContain('Ya existe un periodo');
  });
});
