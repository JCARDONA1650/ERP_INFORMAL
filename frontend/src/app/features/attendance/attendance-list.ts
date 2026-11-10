import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Attendance, AttendanceService } from '../../core/attendance/attendance.service';
import { AuthService } from '../../core/auth/auth.service';
import { Page } from '../../core/models/page';
import { ProjectSummary, ProjectsService } from '../../core/projects/projects.service';
import { monthRange } from '../../core/util/month';
import { hhmmToMinutes, minutesToHhmm } from '../../core/util/time';

const PAGE_SIZE = 25;

@Component({
  selector: 'app-attendance-list',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './attendance-list.html',
  styleUrl: './attendance-list.scss',
})
export class AttendanceList implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly attendance = inject(AttendanceService);
  private readonly projectsApi = inject(ProjectsService);
  private readonly auth = inject(AuthService);

  protected readonly hhmm = minutesToHhmm;
  /** Solo Administrador y RRHH pueden ajustar minutos (afecta el pago). */
  protected readonly canAdjust = computed(() => this.auth.hasAnyRole(['Administrador', 'RRHH']));

  protected readonly projects = signal<ProjectSummary[]>([]);
  protected readonly data = signal<Page<Attendance> | null>(null);
  protected readonly page = signal(1);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil((this.data()?.count ?? 0) / PAGE_SIZE)),
  );

  // Detalle de una jornada (foto, revisión, ajuste)
  protected readonly selected = signal<Attendance | null>(null);
  protected readonly photoUrl = signal<string | null>(null);
  protected readonly photoState = signal<'idle' | 'loading' | 'none' | 'error'>('idle');
  protected readonly actionError = signal<string | null>(null);
  protected readonly busy = signal(false);

  protected readonly filters = this.fb.group({
    project: this.fb.control<number | null>(null),
    month: this.fb.nonNullable.control(''),
    date_from: this.fb.nonNullable.control(''),
    date_to: this.fb.nonNullable.control(''),
    needs_review: this.fb.nonNullable.control(false),
  });

  protected readonly adjustForm = this.fb.nonNullable.group({
    time: '',
    reason: '',
  });

  ngOnInit(): void {
    this.projectsApi.list().subscribe((p) => this.projects.set(p.results));
    this.load();
  }

  ngOnDestroy(): void {
    this.revokePhoto();
  }

  protected search(): void {
    this.page.set(1);
    this.load();
  }

  /** Elegir un mes llena Desde/Hasta con el rango del mes y busca; vaciarlo limpia el rango. */
  protected onMonth(): void {
    const range = monthRange(this.filters.controls.month.value);
    this.filters.patchValue({ date_from: range?.from ?? '', date_to: range?.to ?? '' });
    this.search();
  }

  protected clearMonth(): void {
    this.filters.controls.month.setValue('');
  }

  protected goTo(page: number): void {
    this.page.set(page);
    this.load();
  }

  protected select(row: Attendance): void {
    this.selected.set(row);
    this.actionError.set(null);
    this.adjustForm.reset({ time: minutesToHhmm(row.worked_minutes), reason: '' });
    this.loadPhoto(row);
  }

  protected close(): void {
    this.selected.set(null);
    this.revokePhoto();
  }

  protected review(): void {
    const row = this.selected();
    if (!row || this.busy()) return;
    this.runAction(this.attendance.review(row.id));
  }

  protected adjust(): void {
    const row = this.selected();
    if (!row || this.busy()) return;
    const { time, reason } = this.adjustForm.getRawValue();
    const minutes = hhmmToMinutes(time);
    if (minutes === null) return this.actionError.set('Ingresa las horas netas como HH:MM.');
    if (!reason.trim()) return this.actionError.set('El ajuste requiere un motivo.');
    this.runAction(this.attendance.adjust(row.id, minutes, reason.trim()));
  }

  private runAction(request: ReturnType<AttendanceService['review']>): void {
    this.busy.set(true);
    this.actionError.set(null);
    request.subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.selected.set(updated);
        this.adjustForm.patchValue({ time: minutesToHhmm(updated.worked_minutes), reason: '' });
        this.data.update((d) =>
          d ? { ...d, results: d.results.map((r) => (r.id === updated.id ? updated : r)) } : d,
        );
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.actionError.set(this.messageFor(err));
      },
    });
  }

  private load(): void {
    const f = this.filters.getRawValue();
    this.loading.set(true);
    this.error.set(null);
    this.attendance
      .list({ ...f, project: f.project, page: this.page() })
      .subscribe({
        next: (res) => {
          this.data.set(res);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.loading.set(false);
          this.error.set(this.messageFor(err));
        },
      });
  }

  private loadPhoto(row: Attendance): void {
    this.revokePhoto();
    if (!row.photo_url) {
      this.photoState.set('none');
      return;
    }
    this.photoState.set('loading');
    this.attendance.photo(row.id).subscribe({
      next: (blob) => {
        if (this.selected()?.id !== row.id) return; // el usuario ya eligió otra jornada
        this.photoUrl.set(URL.createObjectURL(blob));
        this.photoState.set('idle');
      },
      error: () => this.photoState.set('error'),
    });
  }

  private revokePhoto(): void {
    const url = this.photoUrl();
    if (url) URL.revokeObjectURL(url);
    this.photoUrl.set(null);
    this.photoState.set('idle');
  }

  private messageFor(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 409) return err.error?.detail ?? 'La operación no está permitida.';
      if (err.status === 403) return 'No tienes permisos para esta acción.';
      if (err.status === 400) {
        const first = Object.values(err.error ?? {}).flat()[0];
        if (typeof first === 'string') return first;
      }
    }
    return 'No se pudo completar la operación. Inténtalo de nuevo.';
  }
}
