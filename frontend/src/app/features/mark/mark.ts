import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { ScanContext, ScanService } from '../../core/scan/scan.service';
import { haversineM } from '../../core/util/geo';
import { compressImage } from '../../core/util/image';
import { RouterLink } from '@angular/router';

import { AppFooter } from '../../shared/footer/app-footer';
import { Logo } from '../../shared/logo/logo';
import { MapMarker, SiteMap } from '../../shared/site-map/site-map';

type Status = 'loading' | 'ready' | 'invalid';

@Component({
  selector: 'app-mark',
  imports: [ReactiveFormsModule, SiteMap, Logo, AppFooter, RouterLink],
  templateUrl: './mark.html',
  styleUrl: './mark.scss',
})
export class Mark implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly scans = inject(ScanService);

  // Llegan de la ruta /marcar/:slug?t=... (withComponentInputBinding).
  readonly slug = input.required<string>();
  readonly t = input<string>('');

  protected readonly status = signal<Status>('loading');
  protected readonly context = signal<ScanContext | null>(null);
  protected readonly sending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly photoName = signal<string | null>(null);

  protected readonly form = this.fb.group({
    employee: this.fb.control<number | null>(null, Validators.required),
    action: this.fb.nonNullable.control<'in' | 'out'>('in'),
  });

  private photo: File | null = null;
  /** Se conserva entre reintentos fallidos para que el servidor no duplique la marcación. */
  private clientUuid: string | null = null;

  ngOnInit(): void {
    this.scans.context(this.slug(), this.t()).subscribe({
      next: (ctx) => {
        this.context.set(ctx);
        this.status.set('ready');
      },
      error: (err: unknown) => {
        this.status.set('invalid');
        this.error.set(this.messageFor(err));
      },
    });
  }

  /** Dónde está el trabajador respecto de la zona de obra (solo informativo; el servidor valida). */
  protected readonly zone = signal<{
    inside: boolean;
    distance: number;
    lat: number;
    lng: number;
  } | null>(null);
  protected readonly zoneChecking = signal(false);
  protected readonly zoneError = signal<string | null>(null);

  protected readonly workerMarkers = computed<MapMarker[]>(() => {
    const z = this.zone();
    return z ? [{ lat: z.lat, lng: z.lng, label: 'Tú estás aquí', ok: z.inside }] : [];
  });

  protected async checkZone(): Promise<void> {
    const site = this.context()?.site;
    if (!site || this.zoneChecking()) return;
    this.zoneChecking.set(true);
    this.zoneError.set(null);
    const { latitude, longitude } = await this.locate();
    this.zoneChecking.set(false);
    if (latitude === undefined || longitude === undefined) {
      this.zone.set(null);
      this.zoneError.set('No pudimos obtener tu ubicación. Activa el GPS y permite el acceso en el navegador.');
      return;
    }
    const distance = Math.round(haversineM(site.latitude, site.longitude, latitude, longitude));
    this.zone.set({ inside: distance <= site.radius_m, distance, lat: latitude, lng: longitude });
  }

  protected onPhoto(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.photo = file;
    this.photoName.set(file?.name ?? null);
  }

  protected async submit(): Promise<void> {
    this.error.set(null);
    this.success.set(null);
    if (this.form.invalid || !this.photo) {
      this.form.markAllAsTouched();
      this.error.set(!this.photo ? 'Toma la foto de constancia.' : 'Selecciona tu nombre.');
      return;
    }
    if (this.sending()) return;
    this.sending.set(true);

    const [photo, coords] = await Promise.all([compressImage(this.photo), this.locate()]);
    this.clientUuid ??= crypto.randomUUID();
    const { employee, action } = this.form.getRawValue();

    this.scans
      .submit(this.slug(), this.t(), {
        employee: employee!,
        action,
        photo,
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
          this.photoName.set(null);
          this.form.reset({ employee: null, action: 'in' });
        },
        error: (err: unknown) => {
          this.sending.set(false);
          this.error.set(this.messageFor(err));
        },
      });
  }

  /** Ubicación opcional: si se niega o no hay GPS, se marca igual (sin ubicación). */
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
        return 'El código QR venció o no es válido. Pide al supervisor que lo muestre de nuevo.';
      case 404:
        return 'El proyecto no existe o está inactivo.';
      case 409:
        return err.error?.detail ?? 'No se pudo registrar la marcación.';
      case 429:
        return 'Demasiados intentos. Espera un momento e inténtalo de nuevo.';
      case 400: {
        const first = Object.values(err.error ?? {}).flat()[0];
        return typeof first === 'string' ? first : 'Revisa los datos e inténtalo de nuevo.';
      }
      default:
        return 'No se pudo registrar la marcación. Inténtalo de nuevo.';
    }
  }
}
