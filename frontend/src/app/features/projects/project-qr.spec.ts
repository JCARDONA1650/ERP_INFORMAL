import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ProjectQr } from './project-qr';

describe('ProjectQr', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    URL.createObjectURL = () => 'blob:qr';
    URL.revokeObjectURL = () => undefined;
    TestBed.configureTestingModule({
      imports: [ProjectQr],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista solo proyectos activos y muestra el QR al elegir uno', () => {
    const fixture = TestBed.createComponent(ProjectQr);
    fixture.detectChanges();
    http.expectOne('/api/projects/').flush({
      count: 2, next: null, previous: null,
      results: [
        { id: 1, name: 'Montego', slug: 'montego', active: true },
        { id: 2, name: 'Cerrada', slug: 'cerrada', active: false },
      ],
    });
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const buttons = el.querySelectorAll('.list__item');
    expect(buttons.length).toBe(1);

    (buttons[0] as HTMLButtonElement).click();
    http.expectOne('/api/projects/1/qr/').flush(new Blob(['x'], { type: 'image/png' }));
    fixture.detectChanges();
    expect(el.querySelector('.qr img')?.getAttribute('src')).toBe('blob:qr');
  });

  it('informa si el usuario no tiene proyectos', () => {
    const fixture = TestBed.createComponent(ProjectQr);
    fixture.detectChanges();
    http.expectOne('/api/projects/').flush({ count: 0, next: null, previous: null, results: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No tienes proyectos activos');
  });
});
