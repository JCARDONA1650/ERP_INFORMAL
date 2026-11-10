import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';

import { SeriesGroup, SeriesPoint } from '../../core/finance/finance.service';
import { I18n } from '../../core/i18n/i18n.service';
import { formatMoney } from '../../core/util/money';

// Lienzo fijo (viewBox); el SVG se escala al ancho del contenedor.
const W = 820;
const LEFT = 70;
const RIGHT = 16;
const LINE_TOP = 16;
const LINE_BOTTOM = 226;
const BARS_TOP = 262;
const BARS_BOTTOM = 346;
const AXIS_Y = 366;

interface Tick {
  y: number;
  label: string;
}

/**
 * Gráfica tipo trading, en SVG propio (sin librerías): arriba la línea/área del balance
 * acumulado con cruz y tooltip; abajo barras de ingresos (verde, hacia arriba) y gastos
 * (rojo, hacia abajo) por periodo. Es de una sola moneda: las monedas no se convierten.
 */
@Component({
  selector: 'app-finance-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './finance-chart.html',
  styleUrl: './finance-chart.scss',
})
export class FinanceChart {
  private readonly i18n = inject(I18n);

  readonly points = input.required<SeriesPoint[]>();
  readonly currency = input.required<string>();
  readonly group = input<SeriesGroup>('day');

  protected readonly W = W;
  protected readonly LEFT = LEFT;
  protected readonly RIGHT = RIGHT;
  protected readonly LINE_TOP = LINE_TOP;
  protected readonly LINE_BOTTOM = LINE_BOTTOM;
  protected readonly BARS_TOP = BARS_TOP;
  protected readonly BARS_BOTTOM = BARS_BOTTOM;
  protected readonly AXIS_Y = AXIS_Y;
  protected readonly money = formatMoney;

  protected readonly hover = signal<number | null>(null);

  private readonly data = computed(() =>
    this.points().map((p) => ({
      ...p,
      i: Number(p.income),
      e: Number(p.expense),
      c: Number(p.cumulative),
    })),
  );

  private readonly plotW = W - LEFT - RIGHT;
  private readonly step = computed(() => this.plotW / Math.max(1, this.data().length));
  protected readonly barW = computed(() => Math.max(2, Math.min(34, this.step() * 0.6)));

  protected x(index: number): number {
    return LEFT + (index + 0.5) * this.step();
  }

  // ── Línea de balance acumulado ──
  private readonly range = computed(() => {
    const values = [0, ...this.data().map((d) => d.c)];
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      max += 1;
      min -= 1;
    }
    const pad = (max - min) * 0.08;
    return { min: min - pad, max: max + pad };
  });

  protected lineY(value: number): number {
    const { min, max } = this.range();
    return LINE_BOTTOM - ((value - min) / (max - min)) * (LINE_BOTTOM - LINE_TOP);
  }

  protected readonly zeroY = computed(() => this.lineY(0));

  protected readonly linePath = computed(() =>
    this.data()
      .map((d, i) => `${i === 0 ? 'M' : 'L'}${this.x(i).toFixed(1)},${this.lineY(d.c).toFixed(1)}`)
      .join(' '),
  );

  protected readonly areaPath = computed(() => {
    const d = this.data();
    if (!d.length) return '';
    const zero = this.zeroY().toFixed(1);
    return `${this.linePath()} L${this.x(d.length - 1).toFixed(1)},${zero} L${this.x(0).toFixed(1)},${zero} Z`;
  });

  /** Verde si el balance termina en positivo; rojo si termina en negativo. */
  protected readonly positive = computed(() => (this.data().at(-1)?.c ?? 0) >= 0);

  protected readonly yTicks = computed<Tick[]>(() => {
    const { min, max } = this.range();
    return [0, 1, 2, 3].map((n) => {
      const value = min + ((max - min) * n) / 3;
      return { y: this.lineY(value), label: this.compact(value) };
    });
  });

  // ── Barras de ingresos / gastos ──
  private readonly barMax = computed(() => Math.max(1, ...this.data().flatMap((d) => [d.i, d.e])));
  protected readonly barMid = (BARS_TOP + BARS_BOTTOM) / 2;

  protected barHeight(value: number): number {
    return (value / this.barMax()) * ((BARS_BOTTOM - BARS_TOP) / 2);
  }

  protected readonly barTicks = computed<Tick[]>(() => [
    { y: BARS_TOP, label: this.compact(this.barMax()) },
    { y: this.barMid, label: '0' },
    { y: BARS_BOTTOM, label: `−${this.compact(this.barMax())}` },
  ]);

  // ── Eje X ──
  protected readonly xTicks = computed(() => {
    const d = this.data();
    const every = Math.max(1, Math.ceil(d.length / 8));
    return d
      .map((p, i) => ({ i, label: this.periodLabel(p.period) }))
      .filter(({ i }) => i % every === 0 || i === d.length - 1);
  });

  // ── Interacción ──
  protected readonly active = computed(() => {
    const index = this.hover();
    const d = this.data();
    return index === null || !d[index] ? null : { ...d[index], index };
  });

  /** Posición del tooltip en % del ancho para que siga a la cruz. */
  protected readonly tipLeft = computed(() => {
    const a = this.active();
    return a ? (this.x(a.index) / W) * 100 : 0;
  });

  protected readonly ariaLabel = computed(() => {
    const d = this.data();
    if (!d.length) return 'Sin movimientos en este rango.';
    const last = d[d.length - 1];
    return `Balance acumulado de ${this.periodLabel(d[0].period)} a ${this.periodLabel(last.period)}: ${formatMoney(last.c, this.currency())}`;
  });

  protected onMove(event: PointerEvent): void {
    const svg = event.currentTarget as SVGElement;
    const box = svg.getBoundingClientRect();
    if (!box.width || !this.data().length) return;
    const px = ((event.clientX - box.left) / box.width) * W;
    const index = Math.floor((px - LEFT) / this.step());
    this.hover.set(Math.min(this.data().length - 1, Math.max(0, index)));
  }

  protected onLeave(): void {
    this.hover.set(null);
  }

  protected periodLabel(period: string, long = false): string {
    const [y, m, d] = period.split('-').map(Number);
    const date = new Date(y, m - 1, d, 12);
    const locale = this.i18n.lang() === 'en' ? 'en-US' : 'es-US';
    const group = this.group();
    if (group === 'month') {
      return new Intl.DateTimeFormat(locale, { month: 'short', year: 'numeric' }).format(date);
    }
    const base = new Intl.DateTimeFormat(locale, long ? { day: '2-digit', month: 'short', year: 'numeric' } : { day: '2-digit', month: '2-digit' }).format(date);
    return group === 'week' && long ? `${this.weekLabel()} ${base}` : base;
  }

  private weekLabel(): string {
    return this.i18n.lang() === 'en' ? 'Week of' : 'Semana del';
  }

  private compact(value: number): string {
    return new Intl.NumberFormat(this.i18n.lang() === 'en' ? 'en-US' : 'es-US', {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }
}
