import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';
import { Page } from '../models/page';

export type PeriodStatus = 'OPEN' | 'CLOSED';

export interface PayrollPeriod {
  id: number;
  start_date: string;
  end_date: string;
  project: number | null;
  project_name: string | null;
  status: PeriodStatus;
  created_at: string;
  closed_at: string | null;
  closed_by: string | null;
}

export interface PayrollLine {
  id: number;
  employee: { id: number; full_name: string; document_id: string | null };
  minutes: number;
  hours: string;
  days: number;
  hourly_rate: string;
  currency: string;
  base_amount: string;
  adjustment: string;
  notes: string;
  total: string;
}

export interface PayrollPeriodDetail extends PayrollPeriod {
  lines: PayrollLine[];
  totals: Record<string, string>;
}

export interface NewPeriod {
  start_date: string;
  end_date: string;
  project: number | null;
}

@Injectable({ providedIn: 'root' })
export class PayrollService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/payroll`;

  list(status?: PeriodStatus | '', page = 1): Observable<Page<PayrollPeriod>> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (page > 1) params = params.set('page', page);
    return this.http.get<Page<PayrollPeriod>>(`${this.base}/periods/`, { params });
  }

  create(body: NewPeriod): Observable<PayrollPeriod> {
    return this.http.post<PayrollPeriod>(`${this.base}/periods/`, body);
  }

  detail(id: number): Observable<PayrollPeriodDetail> {
    return this.http.get<PayrollPeriodDetail>(`${this.base}/periods/${id}/`);
  }

  recalculate(id: number): Observable<PayrollPeriodDetail> {
    return this.http.post<PayrollPeriodDetail>(`${this.base}/periods/${id}/recalculate/`, {});
  }

  close(id: number): Observable<PayrollPeriodDetail> {
    return this.http.post<PayrollPeriodDetail>(`${this.base}/periods/${id}/close/`, {});
  }

  reopen(id: number): Observable<PayrollPeriodDetail> {
    return this.http.post<PayrollPeriodDetail>(`${this.base}/periods/${id}/reopen/`, {});
  }

  adjust(lineId: number, amount: string, reason: string): Observable<PayrollLine> {
    return this.http.post<PayrollLine>(`${this.base}/lines/${lineId}/adjust/`, { amount, reason });
  }
}
