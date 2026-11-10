import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Privacy } from './privacy';

describe('Privacy', () => {
  it('muestra la política de datos, el logo y el copyright', () => {
    TestBed.configureTestingModule({ imports: [Privacy], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(Privacy);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Política de tratamiento de datos personales');
    expect(text).toContain('únicamente en el instante de marcar');
    expect(text).toContain('© 2026 ERP INFORMAL · Jorge Cardona · Ing. Sistemas');
    expect((fixture.nativeElement as HTMLElement).querySelector('app-logo svg')).not.toBeNull();
  });
});
