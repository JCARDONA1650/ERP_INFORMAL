import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Mark } from './mark';

const CONTEXT = {
  project: { name: 'Montego', slug: 'montego' },
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
      providers: [provideHttpClient(), provideHttpClientTesting()],
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
  const attachPhoto = () => {
    const input = el.querySelector('#photo') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'foto.jpg', { type: 'image/jpeg' })] });
    input.dispatchEvent(new Event('change'));
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
