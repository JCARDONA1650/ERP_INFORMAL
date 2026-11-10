import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ReportsService } from './reports.service';

describe('ReportsService', () => {
  let service: ReportsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ReportsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('pide los archivos a los endpoints correctos', () => {
    service.payroll(4, 'pdf').subscribe();
    http.expectOne('/api/reports/payroll/4/pdf/').flush(new Blob(['x']));

    service.attendance('xlsx', { date_from: '2026-11-01', date_to: '2026-11-30', project: 2 }).subscribe();
    const att = http.expectOne((r) => r.url === '/api/reports/attendance/xlsx/');
    expect(att.request.params.get('project')).toBe('2');
    expect(att.request.responseType).toBe('blob');
    att.flush(new Blob(['x']));

    service.finance(3, 'xlsx', '2026-11-01').subscribe();
    const fin = http.expectOne((r) => r.url === '/api/reports/finance/3/xlsx/');
    expect(fin.request.params.get('date_from')).toBe('2026-11-01');
    expect(fin.request.params.has('date_to')).toBe(false);
    fin.flush(new Blob(['x']));
  });

  it('descarga el registro financiero global, con proyecto y fechas opcionales', () => {
    service.financeLedger('xlsx').subscribe();
    const all = http.expectOne((r) => r.url === '/api/reports/finance/ledger/xlsx/');
    expect(all.request.params.keys().length).toBe(0);
    expect(all.request.responseType).toBe('blob');
    all.flush(new Blob(['x']));

    service.financeLedger('pdf', { project: 2, date_from: '2026-11-01', date_to: '2026-11-30' }).subscribe();
    const one = http.expectOne((r) => r.url === '/api/reports/finance/ledger/pdf/');
    expect(one.request.params.get('project')).toBe('2');
    expect(one.request.params.get('date_to')).toBe('2026-11-30');
    one.flush(new Blob(['x']));
  });

  it('convierte el error en Blob de nuevo a JSON legible', async () => {
    let received: HttpErrorResponse | undefined;
    service.payroll(4, 'xlsx').subscribe({ error: (e) => (received = e) });
    http
      .expectOne('/api/reports/payroll/4/xlsx/')
      .flush(new Blob([JSON.stringify({ detail: 'Formato no soportado.' })]), { status: 400, statusText: 'Bad Request' });
    await new Promise((r) => setTimeout(r, 20));
    expect(received?.status).toBe(400);
    expect(received?.error).toEqual({ detail: 'Formato no soportado.' });
  });
});
