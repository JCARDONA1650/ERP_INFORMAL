import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Home } from './home';

const BASE = {
  role_scope: 'backoffice',
  today: '2026-11-10',
  attendance: { present_today: 3, open_shifts: 1, out_of_zone_today: 1, pending_review: 2 },
  projects: [
    { id: 1, name: 'UNAD', workers: 2, present_today: 3, pending_review: 2,
      site: { latitude: 28.5, longitude: -81.4, radius_m: 150, out_of_zone_policy: 'block' } },
  ],
  marks_today: [{ employee: 'Ana', project: 'UNAD', action: 'in', time: '07:00', latitude: 28.5, longitude: -81.4, in_zone: true }],
  hours_last_days: [{ date: '2026-11-09', hours: 8 }, { date: '2026-11-10', hours: 4 }],
};

describe('Home (dashboard)', () => {
  const setup = (payload: object) => {
    TestBed.configureTestingModule({ imports: [Home], providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();
    http.expectOne('/api/dashboard/').flush(payload);
    fixture.detectChanges();
    return { el: fixture.nativeElement as HTMLElement, http };
  };

  it('administrador: indicadores, finanzas, barras y mapa', () => {
    const { el, http } = setup({
      ...BASE,
      workers: { active: 2, inactive: 0 },
      payroll: { open_periods: 1 },
      finance: { incomes: { USD: '500.00' }, expenses: { USD: '120.00' } },
    });
    expect(el.textContent).toContain('Presentes hoy');
    expect(el.textContent).toContain('Trabajadores activos');
    expect(el.textContent).toContain('Finanzas');
    expect(el.querySelectorAll('.bars__col').length).toBe(2);
    expect(el.querySelector('app-site-map .leaflet-container')).not.toBeNull();
    http.verify();
  });

  it('supervisor: sin finanzas ni nómina', () => {
    const { el } = setup({ ...BASE, role_scope: 'supervisor' });
    expect(el.textContent).not.toContain('Finanzas');
    expect(el.textContent).not.toContain('Nóminas abiertas');
    expect(el.textContent).toContain('de tus proyectos');
  });

  it('sin zonas muestra el aviso en lugar del mapa', () => {
    const { el } = setup({ ...BASE, projects: [{ ...BASE.projects[0], site: null }], marks_today: [] });
    expect(el.querySelector('app-site-map')).toBeNull();
    expect(el.textContent).toContain('Ningún proyecto tiene zona');
  });
});
