import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { ManualProject, ManualScanService } from '../../core/attendance/manual-scan.service';
import { haversineM } from '../../core/util/geo';
import { CameraCapture } from '../../shared/camera-capture/camera-capture';

/**
 * Marcación asistida: el Supervisor (de sus proyectos) o el Administrador registra ingreso
 * o salida de un trabajador que no tiene celular. Exige foto tomada en el momento (si el
 * proyecto la pide) y usa el GPS de quien marca con la política de zona del proyecto.
 */
@Component({
  selector: 'app-assisted-mark',
  imports: [ReactiveFormsModule, CameraCapture],
  templateUrl: './assisted-mark.html',
  styleUrl: './assisted-mark.scss',
})
export class AssistedMark implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ManualScanService);

  protected readonly projects = signal<ManualProject[]>([]);
  protected readonly loading = signal(true);
  protected readonly sending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly zoneMessage = signal<{ ok: boolean; text: string } | null>(null);
  protected readonly checking = signal(false);
  protected readonly filter = signal('');

  protected readonly form = this.fb.group({
    project: this.fb.control<number | null>(null),
    employee: this.fb.control<number | null>(null),
    action: this.fb.nonNullable.control<'in' | 'out'>('in'),
  });

  private readonly camera = viewChild(CameraCapture);
  private photo: File | null = null;
  private clientUuid: string | null = null;

  protected readonly selected = computed(() => {
    const id = this.projectId();
    return this.projects().find((p) => p.id === id) ?? null;
  });
  protected readonly projectId = signal<number | null>(null);
  protected readonly photoRequired = computed(() => this.selected()?.photo_required ?? true);
  protected readonly visibleEmployees = computed(() => {
    const q = this.filter().trim().toLowerCase();
    return (this.selected()?.employees ?? []).filter((e) => !q || e.full_name.toLowerCase().includes(q));
  });

  ngOnInit(): void {
    this.api.projects().subscribe({
      next: (list) => {
        this.projects.set(list);
        this.loading.set(false);
        if (list.length === 1) this.pickProject(list[0].id);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('No se pudieron cargar los proyectos.');
      },
    });
  }

  protected onProject(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.pickProject(value ? Number(value) : null);
  }

  protected onPhoto(file: File | null): void {
    this.photo = file;
  }

  protected onFilter(event: Event): void {
    this.filter.set((event.target as HTMLInputElement).value);
  }

  protected async checkZone(): Promise<void> {
    const site = this.selected()?.site;
    if (!site || this.checking()) return;
    this.checking.set(true);
    const { latitude, longitude } = await this.locate();
    this.checking.set(false);
    if (latitude === undefined || longitude === undefined) {
      this.zoneMessage.set({
        ok: false,
        text: 'No pudimos obtener tu ubicación. Activa el GPS y permite el acceso en el navegador.',
      });
      return;
    }
    const distance = Math.round(haversineM(site.latitude, site.longitude, latitude, longitude));
    this.zoneMessage.set(
      distance <= site.radius_m
        ? { ok: true, text: `Estás dentro de la zona de obra (${distance} m del punto).` }
        : {
            ok: false,
            text: `Estás fuera de la zona de obra (a ${distance} m; el máximo es ${site.radius_m} m).`,
          },
    );
  }

  protected async submit(): Promise<void> {
    this.error.set(null);
    this.success.set(null);
    const { project, employee, action } = this.form.getRawValue();
    if (!project) return this.error.set('Elige un proyecto.');
    if (!employee) return this.error.set('Elige al trabajador.');
    if (this.photoRequired() && !this.photo) return this.error.set('Toma la foto de constancia.');
    if (this.sending()) return;
    this.sending.set(true);

    const coords = await this.locate();
    this.clientUuid ??= crypto.randomUUID();
    this.api
      .submit({
        project,
        employee,
        action,
        photo: this.photo,
        clientUuid: this.clientUuid,
        deviceTs: new Date().toISOString(),
        ...coords,
      })
      .subscribe({
        next: (res) => {
          this.sending.set(false);
          this.success.set(
            res.in_zone === false
              ? `${res.message} Quedó fuera de la zona de la obra y el supervisor la revisará.`
              : res.message,
          );
          this.clientUuid = null;
          this.photo = null;
          this.camera()?.reset();
          this.form.patchValue({ employee: null, action: 'in' });
          this.filter.set('');
        },
        error: (err: unknown) => {
          this.sending.set(false);
          this.error.set(this.messageFor(err));
        },
      });
  }

  private pickProject(id: number | null): void {
    this.projectId.set(id);
    this.form.patchValue({ project: id, employee: null });
    this.zoneMessage.set(null);
    this.filter.set('');
  }

  private locate(): Promise<{ latitude?: number; longitude?: number }> {
    if (!('geolocation' in navigator)) return Promise.resolve({});
    return new Promise((resolve) =>
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
        () => resolve({}),
        { enableHighAccuracy: true, timeout: 10_000, maximumAge: 30_000 },
      ),
    );
  }

  private messageFor(err: unknown): string {
    if (!(err instanceof HttpErrorResponse)) return 'Ocurrió un error inesperado.';
    switch (err.status) {
      case 0:
        return 'Sin conexión. Revisa tu internet y vuelve a intentar: tu marcación no se duplicará.';
      case 403:
        return 'No tienes permisos para esta acción.';
      case 409:
        return err.error?.detail ?? 'No se pudo registrar la marcación.';
      case 400: {
        const first = Object.values(err.error ?? {}).flat()[0];
        return typeof first === 'string' ? first : 'Revisa los datos e inténtalo de nuevo.';
      }
      default:
        return 'No se pudo registrar la marcación. Inténtalo de nuevo.';
    }
  }
}
