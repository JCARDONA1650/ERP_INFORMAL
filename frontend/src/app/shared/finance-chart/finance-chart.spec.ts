import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SeriesGroup, SeriesPoint } from '../../core/finance/finance.service';
import { FinanceChart } from './finance-chart';

const POINTS: SeriesPoint[] = [
  { period: '2026-11-02', income: '400.00', expense: '100.00', net: '300.00', cumulative: '300.00' },
  { period: '2026-11-03', income: '0.00', expense: '0.00', net: '0.00', cumulative: '300.00' },
  { period: '2026-11-04', income: '0.00', expense: '500.00', net: '-500.00', cumulative: '-200.00' },
];

@Component({
  imports: [FinanceChart],
  template: '<app-finance-chart [points]="points" currency="USD" [group]="group" />',
})
class Host {
  points: SeriesPoint[] = POINTS;
  group: SeriesGroup = 'day';
}

describe('FinanceChart', () => {
  let fixture: ComponentFixture<Host>;
  let el: HTMLElement;

  const setup = (points: SeriesPoint[] = POINTS, group: SeriesGroup = 'day') => {
    TestBed.configureTestingModule({ imports: [Host] });
    fixture = TestBed.createComponent(Host);
    fixture.componentInstance.points = points;
    fixture.componentInstance.group = group;
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  };

  const hoverAt = (fraction: number) => {
    const svg = el.querySelector('svg') as SVGElement;
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 820, height: 380, right: 820, bottom: 380, x: 0, y: 0, toJSON: () => ({}) });
    const event = new Event('pointermove') as PointerEvent;
    Object.defineProperty(event, 'clientX', { value: 70 + fraction * (820 - 70 - 16) });
    svg.dispatchEvent(event);
    fixture.detectChanges();
  };

  it('dibuja la línea del balance, el área y una barra de ingresos y de gastos por periodo', () => {
    setup();
    expect(el.querySelector('path.chart__line')).not.toBeNull();
    expect(el.querySelectorAll('rect.chart__bar--in').length).toBe(3);
    expect(el.querySelectorAll('rect.chart__bar--out').length).toBe(3);
  });

  it('la línea es roja cuando el balance termina en negativo', () => {
    setup();
    expect(el.querySelector('path.chart__line--down')).not.toBeNull();
  });

  it('la línea es verde cuando el balance termina en positivo', () => {
    setup(POINTS.slice(0, 2));
    expect(el.querySelector('path.chart__line--down')).toBeNull();
  });

  it('muestra la cruz y el tooltip del periodo bajo el cursor', () => {
    setup();
    expect(el.querySelector('.chart__tip')).toBeNull();
    hoverAt(0.05); // primer periodo
    const tip = el.querySelector('.chart__tip') as HTMLElement;
    expect(tip.textContent).toContain('400,00');
    expect(tip.textContent).toContain('Acumulado');
    expect(el.querySelector('line.chart__cross')).not.toBeNull();

    hoverAt(0.95); // último periodo
    expect(el.querySelector('.chart__tip')?.textContent).toContain('500,00');
    el.querySelector('svg')!.dispatchEvent(new Event('pointerleave'));
    fixture.detectChanges();
    expect(el.querySelector('.chart__tip')).toBeNull();
  });

  it('sin movimientos muestra un aviso y no dibuja', () => {
    setup([]);
    expect(el.querySelector('svg')).toBeNull();
    expect(el.textContent).toContain('Sin movimientos');
  });

  it('ofrece una tabla accesible con los periodos', () => {
    setup(POINTS, 'month');
    expect(el.querySelectorAll('table.sr-only tbody tr').length).toBe(3);
  });
});
