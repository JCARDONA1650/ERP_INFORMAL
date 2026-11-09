import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Page } from '../../core/models/page';
import {
  EXPENSE_CATEGORIES,
  FinanceService,
  FinanceSummary,
  Movement,
  MovementBody,
  MovementKind,
} from '../../core/finance/finance.service';
import { ProjectSummary, ProjectsService } from '../../core/projects/projects.service';
import { apiErrorMessage } from '../../core/util/http-error';
import { formatMoney } from '../../core/util/money';

const PAGE_SIZE = 25;

@Component({
  selector: 'app-finance-page',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './finance-page.html',
  styleUrl: './finance-page.scss',
})
export class FinancePage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(FinanceService);
  private readonly projectsApi = inject(ProjectsService);

  protected readonly money = formatMoney;
  protected readonly categories = EXPENSE_CATEGORIES;
  protected readonly categoryLabel = (v?: string) =>
    EXPENSE_CATEGORIES.find((c) => c.value === v)?.label ?? v ?? '';

  protected readonly projects = signal<ProjectSummary[]>([]);
  protected readonly summary = signal<FinanceSummary | null>(null);
  protected readonly list = signal<Page<Movement> | null>(null);
  protected readonly kind = signal<MovementKind>('incomes');
  protected readonly page = signal(1);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Movement | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil((this.list()?.count ?? 0) / PAGE_SIZE)),
  );
  protected readonly currencies = computed(() => {
    const s = this.summary();
    return s ? [...new Set([...Object.keys(s.incomes), ...Object.keys(s.expenses)])].sort() : [];
  });

  protected readonly filters = this.fb.group({
    project: this.fb.control<number | null>(null),
    date_from: this.fb.nonNullable.control(''),
    date_to: this.fb.nonNullable.control(''),
  });

  // amount es string al precargar y number al editar un <input type="number">.
  protected readonly form = this.fb.nonNullable.group({
    date: '',
    amount: this.fb.nonNullable.control<string | number>(''),
    currency: '',
    description: '',
    category: 'other',
  });

  ngOnInit(): void {
    this.projectsApi.list().subscribe((p) => this.projects.set(p.results));
  }

  protected search(): void {
    if (!this.filters.value.project) {
      this.error.set('Elige un proyecto.');
      return;
    }
    this.page.set(1);
    this.closeForm();
    this.loadAll();
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
      date: new Date().toISOString().slice(0, 10),
      amount: '',
      currency: this.summary()?.contract.currency ?? 'USD',
      description: '',
      category: 'other',
    });
    this.formOpen.set(true);
  }

  protected edit(m: Movement): void {
    this.editing.set(m);
    this.formError.set(null);
    this.form.reset({
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
    const project = this.filters.value.project;
    if (!project || this.saving()) return;
    const v = this.form.getRawValue();
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

    const editing = this.editing();
    this.saving.set(true);
    this.formError.set(null);
    const request = editing
      ? this.api.update(this.kind(), editing.id, body) // el proyecto no se envía: no se puede mover
      : this.api.create(this.kind(), { ...body, project });
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
    const { project, date_from, date_to } = this.filters.getRawValue();
    if (!project) return;
    this.loading.set(true);
    this.error.set(null);
    this.api.summary(project, date_from, date_to).subscribe({
      next: (s) => this.summary.set(s),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
    this.loadList();
  }

  private loadList(): void {
    const { project, date_from, date_to } = this.filters.getRawValue();
    if (!project) return;
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
