import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { EmployeesService } from './employees.service';

describe('EmployeesService', () => {
  let service: EmployeesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(EmployeesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista con búsqueda, estado y página', () => {
    service.list({ search: ' ana ', active: 'true', page: 2 }).subscribe();
    const req = http.expectOne((r) => r.url === '/api/employees/');
    expect(req.request.params.get('search')).toBe('ana');
    expect(req.request.params.get('active')).toBe('true');
    expect(req.request.params.get('page')).toBe('2');
    req.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('usa los endpoints de activar/desactivar y de tarifas', () => {
    service.setActive(5, false).subscribe();
    http.expectOne('/api/employees/5/deactivate/').flush({});
    service.setActive(5, true).subscribe();
    http.expectOne('/api/employees/5/activate/').flush({});
    service.rates(5).subscribe();
    http.expectOne('/api/employees/5/rates/').flush([]);
    service.addRate(5, '30', '2026-11-05').subscribe();
    const req = http.expectOne('/api/employees/5/rates/');
    expect(req.request.body).toEqual({ rate: '30', effective_from: '2026-11-05' });
    req.flush({});
  });
});
