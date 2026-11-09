import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Page } from '../../core/models/page';
import { PayrollPeriod, PayrollService, PeriodStatus } from '../../core/payroll/payroll.service';
import { ProjectSummary, ProjectsService } from '../../core/projects/projects.service';
import { apiErrorMessage } from '../../core/util/http-error';

const PAGE_SIZE = 25;

@Component({
  selector: 'app-period-list',
  imports: [ReactiveFormsModule, RouterLink, DatePipe],
  templateUrl: './period-list.html',
})
export class PeriodList implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(PayrollService);
  private readonly projectsApi = inject(ProjectsService);
  private readonly router = inject(Router);

  protected readonly data = signal<Page<PayrollPeriod> | null>(null);
  protected readonly projects = signal<ProjectSummary[]>([]);
  protected readonly page = signal(1);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly createError = signal<string | null>(null);
  protected readonly creating = signal(false);
  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil((this.data()?.count ?? 0) / PAGE_SIZE)),
  );

  protected readonly filter = this.fb.nonNullable.control<PeriodStatus | ''>('');
  protected readonly form = this.fb.group({
    start_date: this.fb.nonNullable.control(''),
    end_date: this.fb.nonNullable.control(''),
    project: this.fb.control<number | null>(null),
  });

  ngOnInit(): void {
    this.projectsApi.list().subscribe((p) => this.projects.set(p.results));
    this.load();
  }

  protected applyFilter(): void {
    this.page.set(1);
    this.load();
  }

  protected goTo(page: number): void {
    this.page.set(page);
    this.load();
  }

  protected create(): void {
    const { start_date, end_date, project } = this.form.getRawValue();
    if (!start_date || !end_date) {
      this.createError.set('Indica la fecha inicial y la final.');
      return;
    }
    this.creating.set(true);
    this.createError.set(null);
    this.api.create({ start_date, end_date, project }).subscribe({
      next: (period) => {
        this.creating.set(false);
        void this.router.navigate(['/nomina', period.id]);
      },
      error: (err: unknown) => {
        this.creating.set(false);
        this.createError.set(apiErrorMessage(err));
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.list(this.filter.value, this.page()).subscribe({
      next: (res) => {
        this.data.set(res);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
