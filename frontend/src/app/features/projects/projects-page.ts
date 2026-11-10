import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Employee, EmployeesService } from '../../core/employees/employees.service';
import { MapPoint, SiteMap } from '../../shared/site-map/site-map';
import {
  OutOfZonePolicy,
  Project,
  ProjectBody,
  ProjectsService,
  SupervisorOption,
} from '../../core/projects/projects.service';
import { apiErrorMessage } from '../../core/util/http-error';
import { formatMoney } from '../../core/util/money';

@Component({
  selector: 'app-projects-page',
  imports: [ReactiveFormsModule, SiteMap],
  templateUrl: './projects-page.html',
  styleUrl: './projects-page.scss',
})
export class ProjectsPage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ProjectsService);
  private readonly employeesApi = inject(EmployeesService);

  protected readonly money = formatMoney;
  protected readonly projects = signal<Project[]>([]);
  protected readonly supervisors = signal<SupervisorOption[]>([]);
  protected readonly employees = signal<Employee[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Project | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly locating = signal(false);

  protected readonly selectedSupervisors = signal<number[]>([]);
  protected readonly selectedEmployees = signal<number[]>([]);
  protected readonly employeeFilter = signal('');
  protected readonly visibleEmployees = computed(() => {
    const q = this.employeeFilter().trim().toLowerCase();
    return this.employees().filter((e) => !q || e.full_name.toLowerCase().includes(q));
  });

  protected readonly form = this.fb.nonNullable.group({
    name: '',
    contract_value: this.fb.nonNullable.control<string | number>('0'),
    contract_currency: 'USD',
    hasSite: false,
    latitude: this.fb.nonNullable.control<string | number>(''),
    longitude: this.fb.nonNullable.control<string | number>(''),
    radius_m: this.fb.nonNullable.control<string | number>(150),
    out_of_zone_policy: this.fb.nonNullable.control<OutOfZonePolicy>('block'),
  });

  // Valores del formulario como signals: alimentan el mapa en vivo.
  private readonly formValue = toSignal(this.form.valueChanges, { initialValue: this.form.getRawValue() });
  protected readonly mapLat = computed(() => this.toCoord(this.formValue().latitude, 90));
  protected readonly mapLng = computed(() => this.toCoord(this.formValue().longitude, 180));
  protected readonly mapRadius = computed(() => {
    const r = Number(this.formValue().radius_m);
    return Number.isFinite(r) && r > 0 ? r : 150;
  });

  ngOnInit(): void {
    this.load();
    this.api.supervisors().subscribe((s) => this.supervisors.set(s));
    this.employeesApi.list({ pageSize: 200 }).subscribe((p) => this.employees.set(p.results));
  }

  protected openNew(): void {
    this.editing.set(null);
    this.formError.set(null);
    this.form.reset({ name: '', contract_value: '0', contract_currency: 'USD', hasSite: false, latitude: '', longitude: '', radius_m: 150, out_of_zone_policy: 'block' });
    this.selectedSupervisors.set([]);
    this.selectedEmployees.set([]);
    this.employeeFilter.set('');
    this.formOpen.set(true);
  }

  protected edit(p: Project): void {
    this.editing.set(p);
    this.formError.set(null);
    this.form.reset({
      name: p.name,
      contract_value: p.contract_value,
      contract_currency: p.contract_currency,
      hasSite: p.site !== null,
      latitude: p.site?.latitude ?? '',
      longitude: p.site?.longitude ?? '',
      radius_m: p.site?.radius_m ?? 150,
      out_of_zone_policy: p.site?.out_of_zone_policy ?? 'block',
    });
    this.selectedSupervisors.set([...p.supervisors]);
    this.selectedEmployees.set([...p.employees]);
    this.employeeFilter.set('');
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
  }

  protected toggle(list: 'supervisors' | 'employees', id: number): void {
    const target = list === 'supervisors' ? this.selectedSupervisors : this.selectedEmployees;
    target.update((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  protected isChecked(list: 'supervisors' | 'employees', id: number): boolean {
    return (list === 'supervisors' ? this.selectedSupervisors() : this.selectedEmployees()).includes(id);
  }

  protected setFilter(event: Event): void {
    this.employeeFilter.set((event.target as HTMLInputElement).value);
  }

  /** Toma la ubicación del dispositivo (útil estando en la obra). */
  protected useMyLocation(): void {
    if (!('geolocation' in navigator)) {
      this.formError.set('Este dispositivo no permite obtener la ubicación.');
      return;
    }
    this.locating.set(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.locating.set(false);
        this.form.patchValue({
          hasSite: true,
          latitude: Number(pos.coords.latitude.toFixed(6)), // la API acepta 6 decimales
          longitude: Number(pos.coords.longitude.toFixed(6)),
        });
      },
      () => {
        this.locating.set(false);
        this.formError.set('No se pudo obtener la ubicación. Revisa el permiso del navegador.');
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  /** El pin del mapa movió el punto: se refleja en los campos de latitud/longitud. */
  protected onMapPoint(point: MapPoint): void {
    this.form.patchValue({ hasSite: true, latitude: point.lat, longitude: point.lng });
  }

  private toCoord(value: string | number | undefined, limit: number): number | null {
    const text = String(value ?? '').trim();
    if (text === '' || Number.isNaN(Number(text)) || Math.abs(Number(text)) > limit) return null;
    return Number(text);
  }

  protected save(): void {
    if (this.saving()) return;
    const v = this.form.getRawValue();
    if (!v.name.trim()) return this.formError.set('Ingresa el nombre del proyecto.');
    const contract = String(v.contract_value).trim();
    if (contract === '' || Number.isNaN(Number(contract)) || Number(contract) < 0) {
      return this.formError.set('El valor del contrato debe ser cero o mayor.');
    }

    let site: ProjectBody['site'] = null;
    if (v.hasSite) {
      const radius = Number(v.radius_m);
      if (!this.validCoords(v.latitude, v.longitude)) {
        return this.formError.set('Latitud (−90 a 90) y longitud (−180 a 180) no son válidas.');
      }
      if (!Number.isInteger(radius) || radius < 10 || radius > 5000) {
        return this.formError.set('El radio debe estar entre 10 y 5000 metros.');
      }
      site = {
        latitude: Number(Number(v.latitude).toFixed(6)),
        longitude: Number(Number(v.longitude).toFixed(6)),
        radius_m: radius,
        out_of_zone_policy: v.out_of_zone_policy,
      };
    }

    const body: ProjectBody = {
      name: v.name.trim(),
      contract_value: contract,
      contract_currency: v.contract_currency,
      site,
      supervisors: this.selectedSupervisors(),
      employees: this.selectedEmployees(),
    };
    const editing = this.editing();
    this.saving.set(true);
    this.formError.set(null);
    (editing ? this.api.update(editing.id, body) : this.api.create(body)).subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.load();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(err));
      },
    });
  }

  protected toggleActive(p: Project): void {
    this.api.update(p.id, { active: !p.active }).subscribe({
      next: (updated) => this.projects.update((list) => list.map((x) => (x.id === updated.id ? updated : x))),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private validCoords(lat: string | number, lng: string | number): boolean {
    const la = String(lat).trim();
    const lo = String(lng).trim();
    if (la === '' || lo === '' || Number.isNaN(Number(la)) || Number.isNaN(Number(lo))) return false;
    return Math.abs(Number(la)) <= 90 && Math.abs(Number(lo)) <= 180;
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listFull().subscribe({
      next: (res) => {
        this.projects.set(res.results);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
