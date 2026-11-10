import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { Dashboard, DashboardService } from '../../core/dashboard/dashboard.service';
import { apiErrorMessage } from '../../core/util/http-error';
import { formatMoney } from '../../core/util/money';
import { MapMarker, MapZone, SiteMap } from '../../shared/site-map/site-map';

@Component({
  selector: 'app-home',
  imports: [RouterLink, SiteMap],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class Home implements OnInit {
  private readonly api = inject(DashboardService);

  protected readonly user = inject(AuthService).user;
  protected readonly data = signal<Dashboard | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly money = formatMoney;

  protected readonly zones = computed<MapZone[]>(() =>
    (this.data()?.projects ?? [])
      .filter((p) => p.site !== null)
      .map((p) => ({ lat: p.site!.latitude, lng: p.site!.longitude, radius: p.site!.radius_m, label: p.name })),
  );

  protected readonly markers = computed<MapMarker[]>(() =>
    (this.data()?.marks_today ?? []).map((m) => ({
      lat: m.latitude,
      lng: m.longitude,
      ok: m.in_zone,
      label: `${m.employee} · ${m.action === 'in' ? 'Ingreso' : 'Salida'} ${m.time}`,
    })),
  );

  /** Alto de cada barra (0–100 %) respecto del día con más horas. */
  protected readonly bars = computed(() => {
    const days = this.data()?.hours_last_days ?? [];
    const max = Math.max(1, ...days.map((d) => d.hours));
    return days.map((d) => ({
      label: this.dayLabel(d.date),
      hours: d.hours,
      pct: Math.round((d.hours / max) * 100),
    }));
  });

  protected readonly currencies = computed(() => {
    const f = this.data()?.finance;
    return f ? Array.from(new Set([...Object.keys(f.incomes), ...Object.keys(f.expenses)])).sort() : [];
  });

  protected readonly isBackoffice = computed(() => this.data()?.role_scope === 'backoffice');

  ngOnInit(): void {
    this.api.get().subscribe({
      next: (d) => this.data.set(d),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  protected amount(map: Record<string, string> | undefined, currency: string): string {
    return formatMoney(map?.[currency] ?? '0', currency);
  }

  private dayLabel(iso: string): string {
    const [y, m, d] = iso.split('-').map(Number);
    const names = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
    return `${names[new Date(y, m - 1, d).getDay()]} ${d}`;
  }
}
