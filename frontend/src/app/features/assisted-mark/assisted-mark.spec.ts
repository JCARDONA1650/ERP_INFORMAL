import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import { CameraCapture } from '../../shared/camera-capture/camera-capture';
import { AssistedMark } from './assisted-mark';

const PROJECTS = [
  {
    id: 1, name: 'Montego', photo_required: true,
    site: { latitude: 28.5, longitude: -81.4, radius_m: 150, out_of_zone_policy: 'block', address: 'Orlando, FL' },
    employees: [{ id: 7, full_name: 'Ana Gomez' }, { id: 8, full_name: 'Beto Ruiz' }],
  },
];

describe('AssistedMark', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<AssistedMark>;
  let el: HTMLElement;

  const setup = (projects: unknown[] = PROJECTS) => {
    TestBed.configureTestingModule({
      imports: [AssistedMark],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AssistedMark);
    fixture.detectChanges();
    http.expectOne('/api/attendance/manual/context/').flush(projects);
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };
  const choose = (selector: string, text: string) => {
    const select = el.querySelector(selector) as HTMLSelectElement;
    select.selectedIndex = [...select.options].findIndex((o) => o.textContent?.includes(text));
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  };
  const takePhoto = () => {
    const cam = fixture.debugElement.query(By.directive(CameraCapture)).componentInstance as CameraCapture;
    cam.photo.emit(new File(['x'], 'constancia.jpg', { type: 'image/jpeg' }));
  };
  const submit = async () => {
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r));
    fixture.detectChanges();
  };

  afterEach(() => http.verify());

  it('con un solo proyecto lo preselecciona y lista a sus trabajadores', () => {
    setup();
    expect(el.textContent).toContain('Ana Gomez');
    expect(el.textContent).toContain('Orlando, FL');
    expect(el.querySelector('input[type="file"]')).toBeNull(); // la foto solo sale de la cámara
  });

  it('avisa si no hay proyectos asignados', () => {
    setup([]);
    expect(el.textContent).toContain('No tienes proyectos activos asignados.');
  });

  it('filtra trabajadores por nombre', () => {
    setup();
    const q = el.querySelector('input[type="search"]') as HTMLInputElement;
    q.value = 'beto';
    q.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const names = Array.from(el.querySelectorAll('select[formControlName="employee"] option')).map((o) => o.textContent?.trim());
    expect(names).toContain('Beto Ruiz');
    expect(names).not.toContain('Ana Gomez');
  });

  it('exige trabajador y foto antes de enviar', async () => {
    setup();
    await submit();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('trabajador');
    choose('select[formControlName="employee"]', 'Ana');
    await submit();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('foto');
  });

  it('envía la marcación con foto, proyecto y trabajador', async () => {
    setup();
    choose('select[formControlName="employee"]', 'Ana');
    takePhoto();
    await submit();
    const req = http.expectOne('/api/attendance/manual/');
    const body = req.request.body as FormData;
    expect(body.get('project')).toBe('1');
    expect(body.get('employee')).toBe('7');
    expect(body.get('action')).toBe('in');
    expect(body.get('photo')).toBeTruthy();
    expect(body.get('client_uuid')).toBeTruthy();
    req.flush({ message: 'Ingreso registrado: Ana Gomez a las 07:00.', duplicate: false, in_zone: true });
    fixture.detectChanges();
    expect(el.querySelector('[role="status"]')?.textContent).toContain('Ingreso registrado');
  });

  it('muestra el rechazo del servidor (fuera de zona)', async () => {
    setup();
    choose('select[formControlName="employee"]', 'Ana');
    takePhoto();
    await submit();
    http.expectOne('/api/attendance/manual/').flush(
      { detail: 'Estás fuera de la zona de obra (a 900 m; el máximo es 150 m). No se registró la marcación.' },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('fuera de la zona');
  });

  it('si el proyecto no exige foto, marca sin ella', async () => {
    setup([{ ...PROJECTS[0], photo_required: false }]);
    expect(el.textContent).toContain('(opcional)');
    choose('select[formControlName="employee"]', 'Ana');
    await submit();
    const req = http.expectOne('/api/attendance/manual/');
    expect((req.request.body as FormData).has('photo')).toBe(false);
    req.flush({ message: 'ok', duplicate: false, in_zone: null });
  });
});
