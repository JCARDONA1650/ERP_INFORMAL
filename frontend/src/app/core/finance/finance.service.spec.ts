import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { FinanceService } from './finance.service';

describe('FinanceService', () => {
  let service: FinanceService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(FinanceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('pide el resumen con rango de fechas', () => {
    service.overview({ project: null, group: 'week', currency: 'USD' }).subscribe();
    const ov = http.expectOne((r) => r.url === '/api/finance/overview/');
    expect(ov.request.params.has('project')).toBe(false); // sin proyecto = todos
    expect(ov.request.params.get('group')).toBe('week');
    expect(ov.request.params.get('currency')).toBe('USD');
    service.list('incomes', { project: null }).subscribe();
    expect(http.expectOne((r) => r.url === '/api/finance/incomes/').request.params.has('project')).toBe(false);

    service.summary(3, '2026-11-01', '2026-11-30').subscribe();
    const req = http.expectOne((r) => r.url === '/api/projects/3/finance/');
    expect(req.request.params.get('date_from')).toBe('2026-11-01');
    expect(req.request.params.get('date_to')).toBe('2026-11-30');
    req.flush({});
  });

  it('lista por tipo con filtros y crea/edita en el endpoint del tipo', () => {
    service.list('expenses', { project: 3, date_from: '2026-11-01', page: 2 }).subscribe();
    const list = http.expectOne((r) => r.url === '/api/finance/expenses/');
    expect(list.request.params.get('project')).toBe('3');
    expect(list.request.params.get('page')).toBe('2');
    list.flush({ count: 0, next: null, previous: null, results: [] });

    service.create('incomes', { project: 3, date: '2026-11-02', amount: '10', description: '' }).subscribe();
    expect(http.expectOne('/api/finance/incomes/').request.method).toBe('POST');

    service.update('expenses', 9, { date: '2026-11-02', amount: '10', description: '' }).subscribe();
    const patch = http.expectOne('/api/finance/expenses/9/');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body.project).toBeUndefined();
  });
});
