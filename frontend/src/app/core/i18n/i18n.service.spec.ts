import { TestBed } from '@angular/core/testing';

import { I18n } from './i18n.service';

describe('I18n', () => {
  let i18n: I18n;
  let host: HTMLElement;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    i18n = TestBed.inject(I18n);
    host = document.createElement('div');
    document.body.appendChild(host);
  });

  afterEach(() => {
    host.remove();
    localStorage.clear();
    document.documentElement.lang = 'es';
  });

  it('traduce textos exactos y con datos variables, conservando espacios', () => {
    expect(i18n.toEn('Guardar')).toBe('Save');
    expect(i18n.toEn('  Guardar\n')).toBe('  Save\n');
    expect(i18n.toEn('Hola, Ana')).toBe('Hello, Ana');
    expect(i18n.toEn('Estás fuera de la zona de obra (a 120 m; el máximo es 50 m).')).toBe(
      'You are outside the site zone (120 m away; the maximum is 50 m).',
    );
    expect(i18n.toEn('Texto sin traducción')).toBe('Texto sin traducción');
  });

  it('cambia el DOM a inglés (texto y atributos), lo restaura y recuerda el idioma', () => {
    host.innerHTML = '<p>Guardar</p><input placeholder="Buscar" aria-label="Contraseña" />';
    i18n.start();

    i18n.set('en');
    expect(host.querySelector('p')!.textContent).toBe('Save');
    const input = host.querySelector('input')!;
    expect(input.getAttribute('placeholder')).toBe('Search');
    expect(input.getAttribute('aria-label')).toBe('Password');
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem('informal.lang')).toBe('en');

    i18n.set('es');
    expect(host.querySelector('p')!.textContent).toBe('Guardar');
    expect(input.getAttribute('placeholder')).toBe('Buscar');
    expect(document.documentElement.lang).toBe('es');
  });

  it('traduce lo que Angular renderice después de cambiar el idioma', async () => {
    i18n.start();
    i18n.set('en');
    const p = document.createElement('p');
    p.textContent = 'Cancelar';
    host.appendChild(p);
    await new Promise((r) => setTimeout(r));
    expect(p.textContent).toBe('Cancel');

    p.firstChild!.nodeValue = 'Cerrar';
    await new Promise((r) => setTimeout(r));
    expect(p.textContent).toBe('Close');
  });
});
