import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Attendance } from '../../core/attendance/attendance.service';
import { Role } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { AttendanceList } from './attendance-list';

const ROW: Attendance = {
  id: 5, date: '2026-11-02',
  project: { id: 1, name: 'Montego' }, employee: { id: 9, full_name: 'Ana Gomez' },
  check_in: '2026-11-02T12:00:00Z', check_out: '2026-11-02T21:00:00Z',
  check_in_source: 'qr', check_out_source: 'qr', in_zone: false, needs_review: true,
  reviewed_by: null, reviewed_at: null, manual_minutes: null, manual_note: '',
  worked_minutes: 480, photo_url: '/api/attendance/5/photo/', notes: '',
};
const page = (results: Attendance[], count = results.length) => ({ count, next: null, previous: null, results });

describe('AttendanceList', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<AttendanceList>;
  let el: HTMLElement;

  const setup = (roles: Role[]) => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [AttendanceList],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (TestBed.inject(AuthService) as any)._user.set({ id: 1, username: 'u', full_name: 'U', roles });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AttendanceList);
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/projects/').flush(page([]));
    http.expectOne((r) => r.url === '/api/attendance/').flush(page([ROW]));
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };

  const open = () => {
    (el.querySelector('tbody button') as HTMLButtonElement).click();
    http.expectOne('/api/attendance/5/photo/').flush(new Blob(['x'], { type: 'image/jpeg' }));
    fixture.detectChanges();
  };

  beforeEach(() => {
    // jsdom no implementa createObjectURL
    URL.createObjectURL = () => 'blob:test';
    URL.revokeObjectURL = () => undefined;
  });

  afterEach(() => http.verify());

  it('lista las jornadas con su estado', () => {
    setup(['Supervisor']);
    expect(el.querySelectorAll('tbody tr').length).toBe(1);
    expect(el.textContent).toContain('Ana Gomez');
    expect(el.textContent).toContain('08:00');
    expect(el.textContent).toContain('Pendiente');
  });

  it('envía los filtros a la API', () => {
    setup(['Supervisor']);
    const check = el.querySelector('input[type="checkbox"]') as HTMLInputElement;
    check.click();
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne((r) => r.url === '/api/attendance/');
    expect(req.request.params.get('needs_review')).toBe('true');
    req.flush(page([]));
    fixture.detectChanges();
    expect(el.textContent).toContain('No hay jornadas');
  });

  it('abre el detalle con la foto protegida y permite revisar', () => {
    setup(['Supervisor']);
    open();
    expect(el.querySelector('.detail img')).not.toBeNull();
    expect(el.textContent).toContain('Fuera de la zona');

    const reviewBtn = [...el.querySelectorAll('.detail__actions button')][0] as HTMLButtonElement;
    reviewBtn.click();
    const req = http.expectOne('/api/attendance/5/review/');
    expect(req.request.method).toBe('POST');
    req.flush({ ...ROW, needs_review: false, reviewed_by: 'sup', reviewed_at: '2026-11-02T22:00:00Z' });
    fixture.detectChanges();
    expect(el.textContent).toContain('Revisada');
    expect(el.querySelector('.detail__actions button')).toBeNull();
  });

  it('el Supervisor no ve el formulario de ajuste', () => {
    setup(['Supervisor']);
    open();
    expect(el.querySelector('.adjust')).toBeNull();
  });

  it('Administrador ajusta con motivo y se actualiza la fila', () => {
    setup(['Administrador']);
    open();
    const time = el.querySelector('.adjust input[type="time"]') as HTMLInputElement;
    const reason = el.querySelector('.adjust input[type="text"]') as HTMLInputElement;
    time.value = '05:00';
    time.dispatchEvent(new Event('input'));
    reason.value = 'Salió temprano';
    reason.dispatchEvent(new Event('input'));
    (el.querySelector('.adjust') as HTMLFormElement).dispatchEvent(new Event('submit'));

    const req = http.expectOne('/api/attendance/5/adjust/');
    expect(req.request.body).toEqual({ minutes: 300, reason: 'Salió temprano' });
    req.flush({ ...ROW, manual_minutes: 300, manual_note: 'Salió temprano', worked_minutes: 300 });
    fixture.detectChanges();
    expect(el.querySelector('tbody')?.textContent).toContain('05:00');
  });

  it('no envía el ajuste sin motivo', () => {
    setup(['RRHH']);
    open();
    (el.querySelector('.adjust') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectNone('/api/attendance/5/adjust/');
    fixture.detectChanges();
    expect(el.querySelector('.detail [role="alert"]')?.textContent).toContain('motivo');
  });

  it('muestra el mensaje del servidor si la nómina está cerrada (409)', () => {
    setup(['Administrador']);
    open();
    const time = el.querySelector('.adjust input[type="time"]') as HTMLInputElement;
    const reason = el.querySelector('.adjust input[type="text"]') as HTMLInputElement;
    time.value = '05:00';
    time.dispatchEvent(new Event('input'));
    reason.value = 'x';
    reason.dispatchEvent(new Event('input'));
    (el.querySelector('.adjust') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http
      .expectOne('/api/attendance/5/adjust/')
      .flush({ detail: 'La jornada pertenece a una nómina cerrada.' }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(el.querySelector('.detail [role="alert"]')?.textContent).toContain('nómina cerrada');
  });
});
