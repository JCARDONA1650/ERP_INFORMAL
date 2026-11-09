import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ScanService } from './scan.service';

describe('ScanService', () => {
  let service: ScanService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ScanService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('pide el contexto con el token en query', () => {
    service.context('montego', 'tok').subscribe();
    const req = http.expectOne((r) => r.url === '/api/scan/montego/context/');
    expect(req.request.params.get('t')).toBe('tok');
    req.flush({ project: { name: 'M', slug: 'montego' }, employees: [] });
  });

  it('envía la marcación como multipart con ubicación opcional', () => {
    const photo = new File(['x'], 'f.jpg', { type: 'image/jpeg' });
    service
      .submit('montego', 'tok', {
        employee: 3, action: 'in', photo, clientUuid: 'u-1', deviceTs: '2026-11-09T12:00:00Z',
        latitude: 28.5, longitude: -81.4,
      })
      .subscribe();
    const req = http.expectOne((r) => r.url === '/api/scan/montego/');
    const body = req.request.body as FormData;
    expect(body.get('employee')).toBe('3');
    expect(body.get('action')).toBe('in');
    expect(body.get('client_uuid')).toBe('u-1');
    expect(body.get('latitude')).toBe('28.5');
    expect((body.get('photo') as File).name).toBe('f.jpg');
    req.flush({ message: 'ok', duplicate: false, in_zone: true });
  });

  it('omite latitud y longitud cuando no hay ubicación', () => {
    const photo = new File(['x'], 'f.jpg');
    service
      .submit('montego', 'tok', { employee: 3, action: 'out', photo, clientUuid: 'u', deviceTs: 't' })
      .subscribe();
    const req = http.expectOne((r) => r.url === '/api/scan/montego/');
    expect((req.request.body as FormData).has('latitude')).toBe(false);
    req.flush({});
  });
});
