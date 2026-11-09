import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Role } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { ReportsPage } from './reports-page';

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const PERIOD = {
  id: 4, start_date: '2026-11-02', end_date: '2026-11-08', project: null, project_name: null,
  status: 'OPEN', created_at: '', closed_at: null, closed_by: null,
};

describe('ReportsPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<ReportsPage>;
  let el: HTMLElement;
  let saved: string[];

  const setup = (roles: Role[]) => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [ReportsPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (TestBed.inject(AuthService) as any)._user.set({ id: 1, username: 'u', full_name: 'U', roles });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ReportsPage);
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/projects/').flush(page([{ id: 1, name: 'Montego', slug: 'm', active: true }]));
    if (roles.includes('Administrador') || roles.includes('RRHH')) {
      http.expectOne((r) => r.url === '/api/payroll/periods/').flush(page([PERIOD]));
    }
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };

  const section = (id: string) => el.querySelector(`[aria-labelledby="${id}"]`) as HTMLElement;
  const btn = (root: HTMLElement, text: string) =>
    Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === text) as HTMLButtonElement;
  const setValue = (root: HTMLElement, selector: string, value: string) => {
    const input = root.querySelector(selector) as HTMLInputElement | HTMLSelectElement;
    input.value = value;
    input.dispatchEvent(new Event(input instanceof HTMLSelectElement ? 'change' : 'input'));
  };

  beforeEach(() => {
    saved = [];
    URL.createObjectURL = () => 'blob:r';
    URL.revokeObjectURL = () => undefined;
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
  });

  afterEach(() => {
    http.verify();
    vi.restoreAllMocks();
  });

  it('el Supervisor solo ve el reporte de asistencia', () => {
    setup(['Supervisor']);
    expect(section('rep-att')).not.toBeNull();
    expect(section('rep-pay')).toBeNull();
    expect(section('rep-fin')).toBeNull();
  });

  it('RRHH ve asistencia y nómina; el Administrador, los tres', () => {
    setup(['RRHH']);
    expect(section('rep-pay')).not.toBeNull();
    expect(section('rep-fin')).toBeNull();
    TestBed.resetTestingModule();
    setup(['Administrador']);
    expect(section('rep-fin')).not.toBeNull();
  });

  it('exige el rango de fechas de asistencia antes de pedir el archivo', () => {
    setup(['Supervisor']);
    btn(section('rep-att'), 'Excel').click();
    fixture.detectChanges();
    http.expectNone((r) => r.url.includes('/reports/'));
    expect(section('rep-att').querySelector('[role="alert"]')?.textContent).toContain('fecha');
  });

  it('descarga asistencia en Excel con el nombre esperado', () => {
    setup(['Supervisor']);
    const root = section('rep-att');
    setValue(root, 'input[formControlName="date_from"]', '2026-11-01');
    setValue(root, 'input[formControlName="date_to"]', '2026-11-30');
    btn(root, 'Excel').click();
    const req = http.expectOne((r) => r.url === '/api/reports/attendance/xlsx/');
    expect(req.request.params.get('date_from')).toBe('2026-11-01');
    req.flush(new Blob(['x']));
    expect(saved).toEqual(['asistencia_2026-11-01_2026-11-30.xlsx']);
  });

  it('descarga la nómina del periodo elegido en PDF', () => {
    setup(['RRHH']);
    const root = section('rep-pay');
    btn(root, 'PDF').click();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Elige un periodo');

    const select = root.querySelector('select') as HTMLSelectElement;
    select.selectedIndex = 1; // 0 es el marcador «Selecciona…»
    select.dispatchEvent(new Event('change'));
    btn(root, 'PDF').click();
    http.expectOne('/api/reports/payroll/4/pdf/').flush(new Blob(['x']));
    expect(saved).toEqual(['nomina_4.pdf']);
  });

  it('muestra el mensaje del servidor si el reporte falla', async () => {
    setup(['Supervisor']);
    const root = section('rep-att');
    setValue(root, 'input[formControlName="date_from"]', '2020-01-01');
    setValue(root, 'input[formControlName="date_to"]', '2026-11-30');
    btn(root, 'PDF').click();
    http
      .expectOne((r) => r.url === '/api/reports/attendance/pdf/')
      .flush(new Blob([JSON.stringify({ detail: 'El rango máximo es de 366 días.' })]), { status: 400, statusText: 'Bad Request' });
    await new Promise((r) => setTimeout(r, 20));
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('366 días');
    expect(saved).toEqual([]);
  });
});
