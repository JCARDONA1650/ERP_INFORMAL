import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { PayrollService } from './payroll.service';

describe('PayrollService', () => {
  let service: PayrollService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PayrollService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista con filtro de estado y página', () => {
    service.list('CLOSED', 2).subscribe();
    const req = http.expectOne((r) => r.url === '/api/payroll/periods/');
    expect(req.request.params.get('status')).toBe('CLOSED');
    expect(req.request.params.get('page')).toBe('2');
    req.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('crea, recalcula y cierra con los endpoints correctos', () => {
    service.create({ start_date: '2026-11-02', end_date: '2026-11-08', project: null }).subscribe();
    expect(http.expectOne('/api/payroll/periods/').request.method).toBe('POST');
    service.recalculate(3).subscribe();
    http.expectOne('/api/payroll/periods/3/recalculate/').flush({});
    service.close(3).subscribe();
    http.expectOne('/api/payroll/periods/3/close/').flush({});
  });

  it('ajusta una línea', () => {
    service.adjust(9, '-10.00', 'Anticipo').subscribe();
    const req = http.expectOne('/api/payroll/lines/9/adjust/');
    expect(req.request.body).toEqual({ amount: '-10.00', reason: 'Anticipo' });
    req.flush({});
  });
});
