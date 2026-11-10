import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Page } from '../../core/models/page';
import { ReportFormat, ReportsService } from '../../core/reports/reports.service';
import { saveBlob } from '../../core/util/download';
import { monthRange } from '../../core/util/month';
import {
  EXPENSE_CATEGORIES,
  FinanceOverview,
  FinanceService,
  Movement,
  MovementBody,
  MovementKind,
  SeriesGroup,
} from '../../core/finance/finance.service';
import { ProjectSummary, ProjectsService } from '../../core/projects/projects.service';
import { apiErrorMessage } from '../../core/util/http-error';
import { formatMoney } from '../../core/util/money';
import { FinanceChart } from '../../shared/finance-chart/finance-chart';

const PAGE_SIZE = 25;

@Component({
  selector: 'app-finance-page',
  imports: [ReactiveFormsModule, DatePipe, FinanceChart],
  templateUrl: './finance-page.html',
  styleUrl: './finance-page.scss',
})
export class FinancePage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(FinanceService);
  private readonly projectsApi = inject(ProjectsService);
  private readonly reports = inject(ReportsService);

  protected readonly money = formatMoney;
  protected readonly categories = EXPENSE_CATEGORIES;
  protected readonly categoryLabel = (v?: string) =>
    EXPENSE_CATEGORIES.find((c) => c.value === v)?.label ?? v ?? '';
  protected readonly groups: { value: SeriesGroup; label: string }[] = [
    { value: 'day', label: 'Día' },
    { value: 'week', label: 'Semana' },
    { value: 'month', label: 'Mes' },
  ];

  protected readonly projects = signal<ProjectSummary[]>([]);
  protected readonly overview = signal<FinanceOverview | null>(null);
  protected readonly list = signal<Page<Movement> | null>(null);
  protected readonly kind = signal<MovementKind>('incomes');
  protected readonly page = signal(1);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly exporting = signal(false);

  /** Agrupación y moneda de la gráfica; null = automático / la principal. */
  protected readonly group = signal<SeriesGroup | null>(null);
  protected readonly chartCurrency = signal<string | null>(null);

  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Movement | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil((this.list()?.count ?? 0) / PAGE_SIZE)),
  );
  protected readonly isGlobal = computed(() => this.overview()?.scope === null);
  protected readonly currencies = computed(() => this.overview()?.currencies ?? []);
  /** Contrato del proyecto elegido (solo cuando se ve un proyecto). */
  protected readonly contract = computed(() => {
    const o = this.overview();
    return o && o.scope ? (o.projects[0]?.contract ?? null) : null;
  });
  private readonly projectNames = computed(() => new Map(this.projects().map((p) => [p.id, p.name])));

  protected readonly filters = this.fb.group({
    project: this.fb.control<number | null>(null), // null = todos los proyectos
    month: this.fb.nonNullable.control(''),
    date_from: this.fb.nonNullable.control(''),
    date_to: this.fb.nonNullable.control(''),
  });

  // amount es string al precargar y number al editar un <input type="number">.
  protected readonly form = this.fb.nonNullable.group({
    project: this.fb.control<number | null>(null),
    date: '',
    amount: this.fb.nonNullable.control<string | number>(''),
    currency: '',
    description: '',
    category: 'other',
  });

  ngOnInit(): void {
    this.projectsApi.list().subscribe((p) => this.projects.set(p.results));
    this.search();
  }

  protected projectName(id: number): string {
    return this.projectNames().get(id) ?? `#${id}`;
  }

  /** "1.000,00 USD · 5,00 COP" para totales por moneda; "—" si no hay. */
  protected moneyMap(values: Record<string, string>): string {
    const parts = Object.entries(values).map(([cur, v]) => formatMoney(v, cur));
    return parts.length ? parts.join(' · ') : '—';
  }

  protected search(): void {
    this.page.set(1);
    this.group.set(null);
    this.chartCurrency.set(null);
    this.closeForm();
    this.loadAll();
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

  /** Descarga el registro detallado (todos los proyectos o el elegido) con el rango de fechas actual. */
  protected exportLedger(fmt: ReportFormat): void {
    if (this.exporting()) return;
    const { project, date_from, date_to } = this.filters.getRawValue();
    this.exporting.set(true);
    this.error.set(null);
    this.reports.financeLedger(fmt, { project, date_from, date_to }).subscribe({
      next: (blob) => {
        this.exporting.set(false);
        saveBlob(blob, `${project ? `registro_${project}` : 'finanzas_global'}.${fmt}`);
      },
      error: (err: unknown) => {
        this.exporting.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo generar el reporte.'));
      },
    });
  }

  protected viewProject(id: number): void {
    this.filters.patchValue({ project: id });
    this.search();
  }

  protected setGroup(group: SeriesGroup): void {
    this.group.set(group);
    this.loadOverview();
  }

  protected onChartCurrency(event: Event): void {
    this.chartCurrency.set((event.target as HTMLSelectElement).value);
    this.loadOverview();
  }

  protected setKind(kind: MovementKind): void {
    this.kind.set(kind);
    this.page.set(1);
    this.closeForm();
    this.loadList();
  }

  protected goTo(page: number): void {
    this.page.set(page);
    this.loadList();
  }

  protected openNew(): void {
    this.editing.set(null);
    this.formError.set(null);
    this.form.reset({
      project: this.filters.value.project ?? null,
      date: new Date().toISOString().slice(0, 10),
      amount: '',
      currency: this.contract()?.currency ?? 'USD',
      description: '',
      category: 'other',
    });
    this.formOpen.set(true);
  }

  protected edit(m: Movement): void {
    this.editing.set(m);
    this.formError.set(null);
    this.form.reset({
      project: m.project,
      date: m.date,
      amount: m.amount,
      currency: m.currency,
      description: m.description,
      category: m.category ?? 'other',
    });
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
  }

  protected save(): void {
    if (this.saving()) return;
    const v = this.form.getRawValue();
    const editing = this.editing();
    const project = this.filters.value.project ?? v.project;
    if (!editing && !project) return this.formError.set('Elige un proyecto.');
    const amount = String(v.amount ?? '').trim();
    if (!v.date) return this.formError.set('Indica la fecha.');
    if (amount === '' || Number.isNaN(Number(amount)) || Number(amount) < 0) {
      return this.formError.set('Ingresa un monto válido (cero o mayor).');
    }

    const body: MovementBody = {
      date: v.date,
      amount,
      currency: v.currency,
      description: v.description.trim(),
    };
    if (this.kind() === 'expenses') body.category = v.category;

    this.saving.set(true);
    this.formError.set(null);
    const request = editing
      ? this.api.update(this.kind(), editing.id, body) // el proyecto no se envía: no se puede mover
      : this.api.create(this.kind(), { ...body, project: project! });
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.loadAll();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(err));
      },
    });
  }

  private loadAll(): void {
    this.loading.set(true);
    this.error.set(null);
    this.loadOverview();
    this.loadList();
  }

  private loadOverview(): void {
    const { project, date_from, date_to } = this.filters.getRawValue();
    this.api
      .overview({ project, date_from, date_to, group: this.group(), currency: this.chartCurrency() })
      .subscribe({
        next: (o) => this.overview.set(o),
        error: (err: unknown) => {
          this.loading.set(false);
          this.error.set(apiErrorMessage(err));
        },
      });
  }

  private loadList(): void {
    const { project, date_from, date_to } = this.filters.getRawValue();
    this.api.list(this.kind(), { project, date_from, date_to, page: this.page() }).subscribe({
      next: (res) => {
        this.list.set(res);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
