import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import {
  Employee,
  EmployeeBody,
  EmployeesService,
  PayType,
  RateEntry,
} from '../../core/employees/employees.service';
import { Page } from '../../core/models/page';
import { apiErrorMessage } from '../../core/util/http-error';
import { formatMoney } from '../../core/util/money';

const PAGE_SIZE = 25;

interface SimilarEmployee {
  id: number;
  full_name: string;
  document_id: string | null;
}

@Component({
  selector: 'app-employees-page',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './employees-page.html',
})
export class EmployeesPage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(EmployeesService);

  protected readonly money = formatMoney;
  protected readonly data = signal<Page<Employee> | null>(null);
  protected readonly page = signal(1);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil((this.data()?.count ?? 0) / PAGE_SIZE)),
  );

  // Crear / editar
  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Employee | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly similar = signal<SimilarEmployee[]>([]);

  // Tarifas
  protected readonly ratesFor = signal<Employee | null>(null);
  protected readonly rates = signal<RateEntry[]>([]);
  protected readonly rateError = signal<string | null>(null);

  protected readonly filters = this.fb.nonNullable.group({
    search: '',
    active: '' as 'true' | 'false' | '',
  });

  protected readonly form = this.fb.nonNullable.group({
    full_name: '',
    document_id: '',
    position: '',
    pay_type: 'hourly' as PayType,
    daily_rate: this.fb.nonNullable.control<string | number>(''),
    currency: 'USD',
    initial_rate: this.fb.nonNullable.control<string | number>(''),
  });

  protected readonly rateForm = this.fb.nonNullable.group({
    rate: this.fb.nonNullable.control<string | number>(''),
    effective_from: '',
  });

  ngOnInit(): void {
    this.load();
  }

  protected search(): void {
    this.page.set(1);
    this.load();
  }

  protected goTo(page: number): void {
    this.page.set(page);
    this.load();
  }

  // ───────── crear / editar ─────────
  protected openNew(): void {
    this.editing.set(null);
    this.ratesFor.set(null);
    this.similar.set([]);
    this.formError.set(null);
    this.form.reset({ full_name: '', document_id: '', position: '', pay_type: 'hourly', daily_rate: '', currency: 'USD', initial_rate: '' });
    this.formOpen.set(true);
  }

  protected edit(e: Employee): void {
    this.editing.set(e);
    this.ratesFor.set(null);
    this.similar.set([]);
    this.formError.set(null);
    this.form.reset({
      full_name: e.full_name,
      document_id: e.document_id ?? '',
      position: e.position,
      pay_type: e.pay_type,
      daily_rate: e.daily_rate,
      currency: e.currency,
      initial_rate: '',
    });
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
    this.similar.set([]);
  }

  protected save(confirmDuplicate = false): void {
    if (this.saving()) return;
    const v = this.form.getRawValue();
    if (!v.full_name.trim()) return this.formError.set('Ingresa el nombre completo.');

    const body: EmployeeBody = {
      full_name: v.full_name.trim(),
      document_id: v.document_id.trim() || null,
      position: v.position.trim(),
      pay_type: v.pay_type,
      currency: v.currency,
    };
    if (v.pay_type === 'daily' && String(v.daily_rate).trim() !== '') body.daily_rate = String(v.daily_rate);
    const editing = this.editing();
    if (!editing && v.pay_type === 'hourly' && String(v.initial_rate).trim() !== '') {
      body.initial_rate = String(v.initial_rate);
    }
    if (confirmDuplicate) body.confirm_duplicate = true;

    this.saving.set(true);
    this.formError.set(null);
    const request = editing ? this.api.update(editing.id, body) : this.api.create(body);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.load();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        if (err instanceof HttpErrorResponse && err.status === 409 && Array.isArray(err.error?.similar)) {
          this.similar.set(err.error.similar); // posible homónimo: pide confirmar
          return;
        }
        this.formError.set(apiErrorMessage(err));
      },
    });
  }

  protected confirmDuplicate(): void {
    this.save(true);
  }

  // ───────── activar / desactivar ─────────
  protected toggleActive(e: Employee): void {
    this.api.setActive(e.id, !e.active).subscribe({
      next: (updated) =>
        this.data.update((d) =>
          d ? { ...d, results: d.results.map((r) => (r.id === updated.id ? updated : r)) } : d,
        ),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  // ───────── tarifas ─────────
  protected openRates(e: Employee): void {
    this.formOpen.set(false);
    this.ratesFor.set(e);
    this.rateError.set(null);
    this.rateForm.reset({ rate: '', effective_from: new Date().toISOString().slice(0, 10) });
    this.api.rates(e.id).subscribe((r) => this.rates.set(r));
  }

  protected closeRates(): void {
    this.ratesFor.set(null);
  }

  protected addRate(): void {
    const e = this.ratesFor();
    if (!e) return;
    const { rate, effective_from } = this.rateForm.getRawValue();
    const value = String(rate).trim();
    if (value === '' || Number.isNaN(Number(value)) || Number(value) < 0) {
      return this.rateError.set('Ingresa una tarifa válida (cero o mayor).');
    }
    if (!effective_from) return this.rateError.set('Indica desde qué fecha rige.');
    this.rateError.set(null);
    this.api.addRate(e.id, value, effective_from).subscribe({
      next: () => {
        this.api.rates(e.id).subscribe((r) => this.rates.set(r));
        this.rateForm.patchValue({ rate: '' });
        this.load();
      },
      error: (err: unknown) => this.rateError.set(apiErrorMessage(err)),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    const { search, active } = this.filters.getRawValue();
    this.api.list({ search, active, page: this.page() }).subscribe({
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
