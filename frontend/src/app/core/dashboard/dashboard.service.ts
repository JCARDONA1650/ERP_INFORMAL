import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';

export interface DashboardProject {
  id: number;
  name: string;
  workers: number;
  present_today: number;
  pending_review: number;
  site: {
    latitude: number;
    longitude: number;
    radius_m: number;
    out_of_zone_policy: 'block' | 'review';
    address: string;
  } | null;
}

export interface DashboardMark {
  employee: string;
  project: string;
  action: 'in' | 'out';
  time: string;
  latitude: number;
  longitude: number;
  in_zone: boolean | null;
}

export interface Dashboard {
  role_scope: 'backoffice' | 'supervisor';
  today: string;
  attendance: {
    present_today: number;
    open_shifts: number;
    out_of_zone_today: number;
    pending_review: number;
  };
  projects: DashboardProject[];
  marks_today: DashboardMark[];
  hours_last_days: { date: string; hours: number }[];
  /** Solo Administrador / RRHH. */
  workers?: { active: number; inactive: number };
  payroll?: { open_periods: number };
  /** Solo Administrador. Totales por moneda. */
  finance?: { incomes: Record<string, string>; expenses: Record<string, string> };
}

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  get(): Observable<Dashboard> {
    return this.http.get<Dashboard>(`${API_URL}/dashboard/`);
  }
}
