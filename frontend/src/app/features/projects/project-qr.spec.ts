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

  it('copia el enlace de marcación del día', async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: write } });
    const fixture = TestBed.createComponent(ProjectQr);
    fixture.detectChanges();
    http.expectOne('/api/projects/').flush({
      count: 1, next: null, previous: null, results: [{ id: 1, name: 'Montego', slug: 'montego', active: true }],
    });
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    (el.querySelector('.list__item') as HTMLButtonElement).click();
    http.expectOne('/api/projects/1/qr/').flush(new Blob(['x'], { type: 'image/png' }));
    fixture.detectChanges();
    (Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes('Copiar enlace')) as HTMLButtonElement).click();
    http.expectOne('/api/projects/1/qr-link/').flush({ url: 'http://x/marcar/montego?t=abc' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(write).toHaveBeenCalledWith('http://x/marcar/montego?t=abc');
    expect((el.querySelector('input.link') as HTMLInputElement).value).toContain('/marcar/montego');
  });

  it('informa si el usuario no tiene proyectos', () => {
    const fixture = TestBed.createComponent(ProjectQr);
    fixture.detectChanges();
    http.expectOne('/api/projects/').flush({ count: 0, next: null, previous: null, results: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No tienes proyectos activos');
  });
});
