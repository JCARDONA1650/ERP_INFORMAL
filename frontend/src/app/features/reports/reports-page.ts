import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { PayrollPeriod, PayrollService } from '../../core/payroll/payroll.service';
import { ProjectSummary, ProjectsService } from '../../core/projects/projects.service';
import { ReportFormat, ReportsService } from '../../core/reports/reports.service';
import { saveBlob } from '../../core/util/download';
import { apiErrorMessage } from '../../core/util/http-error';

@Component({
  selector: 'app-reports-page',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './reports-page.html',
  styleUrl: './reports-page.scss',
})
export class ReportsPage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly reports = inject(ReportsService);
  private readonly payrollApi = inject(PayrollService);
  private readonly projectsApi = inject(ProjectsService);

  protected readonly canPayroll = computed(() => this.auth.hasAnyRole(['Administrador', 'RRHH']));
  protected readonly canFinance = computed(() => this.auth.hasAnyRole(['Administrador']));

  protected readonly projects = signal<ProjectSummary[]>([]);
  protected readonly periods = signal<PayrollPeriod[]>([]);
  /** Clave del reporte en curso (ej. 'attendance-xlsx'), para bloquear sus botones. */
  protected readonly busy = signal<string | null>(null);
  protected readonly errors = signal<Record<string, string>>({});

  protected readonly attendance = this.fb.group({
    date_from: this.fb.nonNullable.control(''),
    date_to: this.fb.nonNullable.control(''),
    project: this.fb.control<number | null>(null),
  });
  protected readonly payroll = this.fb.group({ period: this.fb.control<number | null>(null) });
  protected readonly finance = this.fb.group({
    project: this.fb.control<number | null>(null),
    date_from: this.fb.nonNullable.control(''),
    date_to: this.fb.nonNullable.control(''),
  });

  ngOnInit(): void {
    this.projectsApi.list().subscribe((p) => this.projects.set(p.results));
    if (this.canPayroll()) {
      this.payrollApi.list().subscribe((p) => this.periods.set(p.results));
    }
  }

  protected downloadAttendance(fmt: ReportFormat): void {
    const { date_from, date_to, project } = this.attendance.getRawValue();
    if (!date_from || !date_to) return this.fail('attendance', 'Indica la fecha inicial y la final.');
    this.run('attendance', fmt, this.reports.attendance(fmt, { date_from, date_to, project }), `asistencia_${date_from}_${date_to}`);
  }

  protected downloadPayroll(fmt: ReportFormat): void {
    const id = this.payroll.getRawValue().period;
    if (!id) return this.fail('payroll', 'Elige un periodo.');
    this.run('payroll', fmt, this.reports.payroll(id, fmt), `nomina_${id}`);
  }

  protected downloadFinance(fmt: ReportFormat): void {
    const { project, date_from, date_to } = this.finance.getRawValue();
    if (!project) return this.fail('finance', 'Elige un proyecto.');
    this.run('finance', fmt, this.reports.finance(project, fmt, date_from, date_to), `finanzas_${project}`);
  }

  protected isBusy(section: string): boolean {
    return this.busy()?.startsWith(section) ?? false;
  }

  private fail(section: string, message: string): void {
    this.errors.update((e) => ({ ...e, [section]: message }));
  }

  private run(section: string, fmt: ReportFormat, request: Observable<Blob>, baseName: string): void {
    if (this.busy()) return;
    this.busy.set(`${section}-${fmt}`);
    this.errors.update((e) => ({ ...e, [section]: '' }));
    request.subscribe({
      next: (blob) => {
        this.busy.set(null);
        saveBlob(blob, `${baseName}.${fmt}`);
      },
      error: (err: unknown) => {
        this.busy.set(null);
        this.fail(section, apiErrorMessage(err, 'No se pudo generar el reporte.'));
      },
    });
  }
}
