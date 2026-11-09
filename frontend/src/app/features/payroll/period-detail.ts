import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { PayrollLine, PayrollPeriodDetail, PayrollService } from '../../core/payroll/payroll.service';
import { apiErrorMessage } from '../../core/util/http-error';
import { formatMoney } from '../../core/util/money';

@Component({
  selector: 'app-period-detail',
  imports: [ReactiveFormsModule, RouterLink, DatePipe],
  templateUrl: './period-detail.html',
})
export class PeriodDetail implements OnInit {
  private readonly api = inject(PayrollService);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  /** Viene de la ruta /nomina/:id (withComponentInputBinding). */
  readonly id = input.required<string>();

  protected readonly money = formatMoney;
  protected readonly period = signal<PayrollPeriodDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly confirmingClose = signal(false);
  protected readonly adjusting = signal<PayrollLine | null>(null);

  protected readonly isOpen = computed(() => this.period()?.status === 'OPEN');
  /** Solo el Administrador (o SuperAdmin) cierra: es irreversible. */
  protected readonly canClose = computed(() => this.auth.hasAnyRole(['Administrador']));
  protected readonly totals = computed(() => Object.entries(this.period()?.totals ?? {}));

  // Un <input type="number"> entrega number al editarlo y string al precargarlo.
  protected readonly adjustForm = this.fb.nonNullable.group({
    amount: this.fb.nonNullable.control<string | number>(''),
    reason: '',
  });

  ngOnInit(): void {
    this.api.detail(Number(this.id())).subscribe({
      next: (p) => {
        this.period.set(p);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo cargar el periodo.'));
      },
    });
  }

  protected recalculate(): void {
    this.run(this.api.recalculate(Number(this.id())));
  }

  protected askClose(): void {
    this.confirmingClose.set(true);
  }

  protected cancelClose(): void {
    this.confirmingClose.set(false);
  }

  protected confirmClose(): void {
    this.confirmingClose.set(false);
    this.run(this.api.close(Number(this.id())));
  }

  protected openAdjust(line: PayrollLine): void {
    this.adjusting.set(line);
    this.adjustForm.reset({ amount: line.adjustment, reason: line.notes });
    this.error.set(null);
  }

  protected closeAdjust(): void {
    this.adjusting.set(null);
  }

  protected saveAdjust(): void {
    const line = this.adjusting();
    if (!line || this.busy()) return;
    const { amount: rawAmount, reason } = this.adjustForm.getRawValue();
    const amount = String(rawAmount ?? '').trim();
    if (amount === '' || Number.isNaN(Number(amount))) {
      this.error.set('Ingresa un monto válido (positivo o negativo).');
      return;
    }
    if (Number(amount) !== 0 && !reason.trim()) {
      this.error.set('Todo ajuste requiere un motivo.');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.api.adjust(line.id, amount, reason.trim()).subscribe({
      next: () => {
        this.adjusting.set(null);
        this.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private run(request: ReturnType<PayrollService['recalculate']>): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: (p) => {
        this.busy.set(false);
        this.period.set(p);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private reload(): void {
    this.api.detail(Number(this.id())).subscribe({
      next: (p) => {
        this.busy.set(false);
        this.period.set(p);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
