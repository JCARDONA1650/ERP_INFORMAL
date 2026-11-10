import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import { Project } from '../../core/projects/projects.service';
import { SiteMap } from '../../shared/site-map/site-map';
import { ProjectsPage } from './projects-page';

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const MONTEGO: Project = {
  id: 1, name: 'Montego', slug: 'montego', active: true, contract_value: '1000.00', contract_currency: 'USD', photo_required: true,
  site: { latitude: '28.500000', longitude: '-81.400000', radius_m: 200, out_of_zone_policy: 'block', address: '' },
  supervisors: [5], employees: [3],
};
const SUPERVISORS = [{ id: 5, username: 'sup', full_name: 'Sara Sup' }, { id: 6, username: 'otro', full_name: 'Otro Sup' }];
const EMPLOYEES = [
  { id: 3, document_id: null, full_name: 'Ana Gomez', position: '', pay_type: 'hourly', hourly_rate: '20.00', daily_rate: '0.00', currency: 'USD', active: true },
  { id: 4, document_id: null, full_name: 'Beto Ruiz', position: '', pay_type: 'hourly', hourly_rate: '10.00', daily_rate: '0.00', currency: 'USD', active: true },
];

describe('ProjectsPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<ProjectsPage>;
  let el: HTMLElement;

  const listReq = () => http.expectOne((r) => r.url === '/api/projects/' && r.method === 'GET');
  const setup = (projects: Project[] = [MONTEGO]) => {
    TestBed.configureTestingModule({
      imports: [ProjectsPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ProjectsPage);
    fixture.detectChanges();
    listReq().flush(page(projects));
    http.expectOne('/api/users/supervisors/').flush(SUPERVISORS);
    http.expectOne((r) => r.url === '/api/employees/').flush(page(EMPLOYEES));
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };
  const btn = (text: string) =>
    Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.trim() === text) as HTMLButtonElement;
  const fill = (selector: string, value: string) => {
    const input = el.querySelector(selector) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  };
  const submit = () => (el.querySelector('.project-form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  const check = (label: string) => {
    const box = Array.from(el.querySelectorAll('label.check')).find((l) => l.textContent?.includes(label))!.querySelector('input') as HTMLInputElement;
    box.click();
  };

  afterEach(() => http.verify());

  it('lista proyectos con contrato, zona y conteos', () => {
    setup();
    expect(el.querySelectorAll('tbody tr').length).toBe(1);
    expect(el.textContent).toContain('200 m');
    expect(el.textContent).toContain('USD');
  });

  it('pide listas completas (page_size=200) para los selectores', () => {
    TestBed.configureTestingModule({ imports: [ProjectsPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ProjectsPage);
    fixture.detectChanges();
    expect(listReq().request.params.get('page_size')).toBe('200');
    http.expectOne('/api/users/supervisors/').flush([]);
    expect(http.expectOne((r) => r.url === '/api/employees/').request.params.get('page_size')).toBe('200');
  });

  it('crea un proyecto con zona, supervisor y trabajadores', () => {
    setup([]);
    btn('Nuevo proyecto').click();
    fixture.detectChanges();
    fill('.project-form input[formControlName="name"]', ' Torre Norte ');
    check('Definir zona');
    fixture.detectChanges();
    fill('.project-form input[formControlName="latitude"]', '28.5');
    fill('.project-form input[formControlName="longitude"]', '-81.4');
    check('Sara Sup');
    check('Ana Gomez');
    submit();
    const req = http.expectOne((r) => r.method === 'POST');
    expect(req.request.body).toEqual({
      name: 'Torre Norte', contract_value: '0', contract_currency: 'USD', photo_required: true,
      site: { latitude: 28.5, longitude: -81.4, radius_m: 150, out_of_zone_policy: 'block', address: '' },
      supervisors: [5], employees: [3],
    });
    req.flush({ ...MONTEGO, id: 2 });
    listReq().flush(page([MONTEGO]));
  });

  it('al editar precarga las asignaciones y puede quitar la zona', () => {
    setup();
    btn('Editar').click();
    fixture.detectChanges();
    expect((el.querySelector('input[formControlName="name"]') as HTMLInputElement).value).toBe('Montego');
    const sara = Array.from(el.querySelectorAll('label.check')).find((l) => l.textContent?.includes('Sara'))!.querySelector('input') as HTMLInputElement;
    expect(sara.checked).toBe(true);

    check('Definir zona'); // desmarca
    check('Otro Sup');
    submit();
    const req = http.expectOne('/api/projects/1/');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body.site).toBeNull();
    expect(req.request.body.supervisors).toEqual([5, 6]);
    req.flush(MONTEGO);
    listReq().flush(page([MONTEGO]));
  });

  it('valida nombre, contrato, coordenadas y radio antes de enviar', () => {
    setup([]);
    btn('Nuevo proyecto').click();
    fixture.detectChanges();
    const alertText = () => el.querySelector('.project-form [role="alert"]')?.textContent ?? '';

    submit(); fixture.detectChanges();
    expect(alertText()).toContain('nombre');

    fill('.project-form input[formControlName="name"]', 'X');
    fill('.project-form input[formControlName="contract_value"]', '-5');
    submit(); fixture.detectChanges();
    expect(alertText()).toContain('contrato');

    fill('.project-form input[formControlName="contract_value"]', '10');
    check('Definir zona'); fixture.detectChanges();
    fill('.project-form input[formControlName="latitude"]', '95');
    fill('.project-form input[formControlName="longitude"]', '0');
    submit(); fixture.detectChanges();
    expect(alertText()).toContain('Latitud');

    fill('.project-form input[formControlName="latitude"]', '28.5');
    fill('.project-form input[formControlName="radius_m"]', '5');
    submit(); fixture.detectChanges();
    expect(alertText()).toContain('radio');
    http.expectNone((r) => r.method === 'POST');
  });

  it('muestra el error del servidor (nombre repetido)', () => {
    setup([]);
    btn('Nuevo proyecto').click();
    fixture.detectChanges();
    fill('.project-form input[formControlName="name"]', 'Montego');
    submit();
    http.expectOne((r) => r.method === 'POST').flush({ name: ['Ya existe un proyecto con ese nombre.'] }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();
    expect(el.querySelector('.project-form [role="alert"]')?.textContent).toContain('Ya existe');
  });

  it('permite marcar la foto como opcional y lo envía a la API', () => {
    setup();
    btn('Editar').click();
    fixture.detectChanges();
    check('Foto obligatoria');
    submit();
    const req = http.expectOne('/api/projects/1/');
    expect(req.request.body.photo_required).toBe(false);
    req.flush({ ...MONTEGO, photo_required: false });
    listReq().flush(page([MONTEGO]));
  });

  it('desactiva un proyecto sin borrarlo', () => {
    setup();
    btn('Desactivar').click();
    const req = http.expectOne('/api/projects/1/');
    expect(req.request.body).toEqual({ active: false });
    req.flush({ ...MONTEGO, active: false });
    fixture.detectChanges();
    expect(el.textContent).toContain('Inactivo');
  });

  it('muestra el mapa con la zona y permite elegir la política fuera de zona', () => {
    setup();
    btn('Editar').click();
    fixture.detectChanges();
    expect(el.querySelector('app-site-map .leaflet-container')).not.toBeNull();
    const policy = el.querySelector('select[formControlName="out_of_zone_policy"]') as HTMLSelectElement;
    expect(policy.value).toBe('block');

    policy.value = 'review';
    policy.dispatchEvent(new Event('change'));
    submit();
    const req = http.expectOne('/api/projects/1/');
    expect(req.request.body.site.out_of_zone_policy).toBe('review');
    req.flush(MONTEGO);
    listReq().flush(page([MONTEGO]));
  });

  it('el punto movido en el mapa actualiza latitud, longitud y la dirección aproximada', () => {
    setup();
    btn('Editar').click();
    fixture.detectChanges();
    const map = fixture.debugElement.query(By.directive(SiteMap)).componentInstance as SiteMap;
    map.pointChange.emit({ lat: 28.6, lng: -81.3 });
    fixture.detectChanges();
    expect((el.querySelector('input[formControlName="latitude"]') as HTMLInputElement).value).toBe('28.6');
    expect((el.querySelector('input[formControlName="longitude"]') as HTMLInputElement).value).toBe('-81.3');
    http.expectOne((r) => r.url === '/api/geocode/reverse/' && r.params.get('lat') === '28.6')
      .flush({ address: 'Calle Falsa 123, Orlando, FL' });
    fixture.detectChanges();
    expect(el.querySelector('.address__saved')?.textContent).toContain('Calle Falsa 123');
  });

  it('busca una dirección, muestra opciones y al elegir una apunta el mapa y guarda la dirección', () => {
    setup([]);
    btn('Nuevo proyecto').click();
    fixture.detectChanges();
    fill('.project-form input[formControlName="name"]', 'Torre Norte');
    check('Definir zona');
    fixture.detectChanges();
    const q = el.querySelector('#address-q') as HTMLInputElement;
    q.value = '400 S Orange Ave Orlando';
    q.dispatchEvent(new Event('input'));
    btn('Buscar dirección').click();
    http.expectOne((r) => r.url === '/api/geocode/search/' && r.params.get('q') === '400 S Orange Ave Orlando').flush({
      results: [{ label: '400 South Orange Avenue, Orlando, Florida', latitude: 28.538336, longitude: -81.379234 }],
    });
    fixture.detectChanges();
    (el.querySelector('.address__list button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect((el.querySelector('input[formControlName="latitude"]') as HTMLInputElement).value).toBe('28.538336');
    expect(el.querySelector('.address__saved')?.textContent).toContain('400 South Orange Avenue');
    submit();
    const req = http.expectOne((r) => r.method === 'POST');
    expect(req.request.body.site.address).toBe('400 South Orange Avenue, Orlando, Florida');
    req.flush({ ...MONTEGO, id: 3 });
    listReq().flush(page([MONTEGO]));
  });

  it('avisa si la dirección no se encuentra o el servicio falla', () => {
    setup([]);
    btn('Nuevo proyecto').click();
    fixture.detectChanges();
    check('Definir zona');
    fixture.detectChanges();
    const q = el.querySelector('#address-q') as HTMLInputElement;
    q.value = 'zzzz no existe';
    q.dispatchEvent(new Event('input'));
    btn('Buscar dirección').click();
    http.expectOne((r) => r.url === '/api/geocode/search/').flush({ results: [] });
    fixture.detectChanges();
    expect(el.textContent).toContain('No encontramos esa dirección');
    btn('Buscar dirección').click();
    http.expectOne((r) => r.url === '/api/geocode/search/').flush({ detail: 'No se pudo consultar el servicio de direcciones.' }, { status: 502, statusText: 'Bad Gateway' });
    fixture.detectChanges();
    expect(el.textContent).toContain('servicio de direcciones');
  });
});
