import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { CameraCapture } from '../../shared/camera-capture/camera-capture';
import { Mark } from './mark';

const CONTEXT = {
  project: { name: 'Montego', slug: 'montego', photo_required: true },
  employees: [{ id: 7, full_name: 'Ana Gomez' }],
};

describe('Mark', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<Mark>;
  let el: HTMLElement;

  const ctxReq = () => http.expectOne((r) => r.url === '/api/scan/montego/context/');
  const postReq = () => http.expectOne((r) => r.url === '/api/scan/montego/' && r.method === 'POST');

  const setup = async (contextStatus?: number) => {
    TestBed.configureTestingModule({
      imports: [Mark],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Mark);
    fixture.componentRef.setInput('slug', 'montego');
    fixture.componentRef.setInput('t', 'tok');
    fixture.detectChanges();
    if (contextStatus) {
      ctxReq().flush({}, { status: contextStatus, statusText: 'x' });
    } else {
      ctxReq().flush(CONTEXT);
    }
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };

  const chooseAna = () => {
    const select = el.querySelector('#employee') as HTMLSelectElement;
    select.selectedIndex = [...select.options].findIndex((o) => o.textContent?.includes('Ana'));
    select.dispatchEvent(new Event('change'));
  };
  /** La foto solo puede venir de la cámara en vivo: se simula lo que emite el componente. */
  const attachPhoto = () => {
    const cam = fixture.debugElement.query(By.directive(CameraCapture)).componentInstance as CameraCapture;
    cam.photo.emit(new File(['x'], 'constancia.jpg', { type: 'image/jpeg' }));
  };
  const submit = async () => {
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r));
  };

  afterEach(() => http.verify());

  it('muestra el proyecto y solo los trabajadores que devuelve la API', async () => {
    await setup();
    expect(el.textContent).toContain('Montego');
    expect(el.querySelectorAll('#employee option').length).toBe(2); // placeholder + Ana
  });

  it('con zona de obra indica si el trabajador está dentro o fuera', async () => {
    TestBed.configureTestingModule({ imports: [Mark], providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Mark);
    fixture.componentRef.setInput('slug', 'montego');
    fixture.componentRef.setInput('t', 'tok');
    fixture.detectChanges();
    ctxReq().flush({
      ...CONTEXT,
      site: { latitude: 28.5, longitude: -81.4, radius_m: 150, out_of_zone_policy: 'block', address: '' },
    });
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;

    // jsdom no trae geolocalización: se simula la posición del dispositivo.
    const at = (lat: number, lng: number) =>
      Object.defineProperty(navigator, 'geolocation', {
        configurable: true,
        value: {
          getCurrentPosition: (ok: (p: GeolocationPosition) => void) =>
            ok({ coords: { latitude: lat, longitude: lng } } as GeolocationPosition),
        },
      });
    const verify = async () => {
      (Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes('Verificar')) as HTMLButtonElement).click();
      await fixture.whenStable();
      fixture.detectChanges();
    };

    at(28.5005, -81.4); // ~55 m
    await verify();
    expect(el.textContent).toContain('dentro de la zona');

    at(28.52, -81.4); // ~2 km
    await verify();
    expect(el.textContent).toContain('fuera de la zona');
    expect(el.textContent).toContain('No podrás registrar');
  });

  it('con QR vencido muestra un mensaje claro y no el formulario', async () => {
    await setup(403);
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('venció');
    expect(el.querySelector('form')).toBeNull();
  });

  it('exige foto y nombre antes de enviar', async () => {
    await setup();
    await submit();
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('foto');
  });

  it('no ofrece subir archivos: la foto solo viene de la cámara', async () => {
    await setup();
    expect(el.querySelector('input[type="file"]')).toBeNull();
    expect(el.querySelector('app-camera-capture')).not.toBeNull();
  });

  it('si el proyecto no exige foto, marca sin ella', async () => {
    TestBed.configureTestingModule({ imports: [Mark], providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Mark);
    fixture.componentRef.setInput('slug', 'montego');
    fixture.componentRef.setInput('t', 'tok');
    fixture.detectChanges();
    ctxReq().flush({ ...CONTEXT, project: { ...CONTEXT.project, photo_required: false } });
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('(opcional)');
    chooseAna();
    await submit();
    const req = postReq();
    expect((req.request.body as FormData).has('photo')).toBe(false);
    req.flush({ message: 'ok', duplicate: false, in_zone: null });
  });

  it('envía la marcación y muestra la confirmación', async () => {
    await setup();
    chooseAna();
    attachPhoto();
    await submit();
    const req = postReq();
    const body = req.request.body as FormData;
    expect(body.get('employee')).toBe('7');
    expect(body.get('action')).toBe('in');
    expect(body.get('client_uuid')).toBeTruthy();
    req.flush({ message: 'Ingreso registrado: Ana Gomez.', duplicate: false, in_zone: true });
    fixture.detectChanges();
    expect(el.querySelector('[role="status"]')?.textContent).toContain('Ingreso registrado');
  });

  it('avisa cuando quedó fuera de zona', async () => {
    await setup();
    chooseAna();
    attachPhoto();
    await submit();
    postReq().flush({ message: 'Ingreso registrado.', duplicate: false, in_zone: false });
    fixture.detectChanges();
    expect(el.textContent).toContain('fuera de la zona');
  });

  it('tras un fallo de red el reintento conserva el client_uuid (no duplica)', async () => {
    await setup();
    chooseAna();
    attachPhoto();
    await submit();
    const first = postReq();
    const uuid = (first.request.body as FormData).get('client_uuid');
    first.error(new ProgressEvent('error'), { status: 0 });
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('Sin conexión');

    await submit();
    const retry = postReq();
    expect((retry.request.body as FormData).get('client_uuid')).toBe(uuid);
    retry.flush({ message: 'ok', duplicate: false, in_zone: null });
  });

  it('muestra el detalle cuando la salida no tiene ingreso (409)', async () => {
    await setup();
    chooseAna();
    attachPhoto();
    await submit();
    postReq().flush({ detail: 'No hay ingreso previo.' }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('No hay ingreso previo.');
  });
});
